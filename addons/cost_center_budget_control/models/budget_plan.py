import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_round
from datetime import date

_logger = logging.getLogger(__name__)


class BudgetPlan(models.Model):
    _name = "budget.plan"
    _description = "Budget Plan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_from desc, name"
    _check_company_auto = True

    name = fields.Char(string="Reference", required=True, tracking=True)
    cost_center_id = fields.Many2one(
        "cost.center",
        string="Cost Center",
        required=True,
        tracking=True,
        ondelete="restrict",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
    )
    date_from = fields.Date(string="Start Date", required=True, tracking=True)
    date_to = fields.Date(string="End Date", required=True, tracking=True)
    state = fields.Selection([(
        "draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("revised", "Revised"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled")],
        string="Status",
        default="draft",
        tracking=True,
        readonly=True,
        help="The status of the budget plan."
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        help="Currency for budget amounts. Defaults to the company currency, but "
             "can be overridden (e.g. a USD-denominated budget for an IDR company). "
             "Actual and PO-committed amounts are auto-converted to this currency.",
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        string="Company Currency",
        related="company_id.currency_id",
        readonly=True,
        store=True,
        help="The reporting currency of the company. Used to display the "
             "company-currency equivalent of budget amounts.",
    )
    is_multi_currency = fields.Boolean(
        string="Multi-Currency",
        compute="_compute_is_multi_currency",
        store=True,
        help="True if the budget currency differs from the company currency.",
    )
    line_ids = fields.One2many(
        "budget.plan.line",
        "plan_id",
        string="Budget Lines",
        copy=True
    )

    is_currently_active = fields.Boolean(
        string="Currently Active",
        compute="_compute_is_currently_active",
        help="Indicates if the budget is approved and within its date range."
    )

    approved_by = fields.Many2one("res.users", string="Approved By", readonly=True, copy=False)
    approved_date = fields.Datetime(string="Approved Date", readonly=True, copy=False)

    parent_revision_id = fields.Many2one(
        "budget.plan",
        string="Revised From",
        readonly=True,
        copy=False,
        ondelete="set null",
        help="The original budget that this budget revises."
    )
    child_revision_ids = fields.One2many(
        "budget.plan",
        "parent_revision_id",
        string="Revisions",
        readonly=True,
    )
    revision_number = fields.Integer(
        string="Revision #",
        default=1,
        readonly=True,
        help="1 = original budget, 2 = first revision, 3 = second revision, etc.",
    )
    is_latest_revision = fields.Boolean(
        string="Is Latest Revision",
        compute="_compute_is_latest_revision",
        store=True,
        help="True if this is the most recent revision in the chain.",
    )

    # -------------------------------------------------------------------------
    # COMPUTED FIELDS
    # -------------------------------------------------------------------------

    @api.depends("state", "date_from", "date_to")
    def _compute_is_currently_active(self):
        today = date.today()
        for rec in self:
            rec.is_currently_active = (
                rec.state == "approved"
                and rec.date_from <= today
                and rec.date_to >= today
            )

    @api.depends("child_revision_ids.revision_number", "child_revision_ids")
    def _compute_is_latest_revision(self):
        for rec in self:
            if not rec.child_revision_ids:
                rec.is_latest_revision = True
            else:
                rec.is_latest_revision = (
                    rec.revision_number
                    >= max(rec.child_revision_ids.mapped("revision_number"))
                )

    @api.depends("currency_id", "company_id.currency_id")
    def _compute_is_multi_currency(self):
        for rec in self:
            rec.is_multi_currency = (
                rec.company_id
                and rec.currency_id
                and rec.currency_id != rec.company_id.currency_id
            )

    @api.onchange("company_id")
    def _onchange_company_id(self):
        for rec in self:
            if rec.company_id and not rec.currency_id:
                rec.currency_id = rec.company_id.currency_id

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "currency_id" in fields_list and not res.get("currency_id"):
            company_id = res.get("company_id") or self.env.company.id
            company = self.env["res.company"].browse(company_id)
            if company.exists() and company.currency_id:
                res["currency_id"] = company.currency_id.id
        return res

    @api.constrains("currency_id")
    def _check_currency_active(self):
        for rec in self:
            if rec.currency_id and not rec.currency_id.active:
                raise ValidationError(
                    _("The currency '%s' is archived. Please choose an active currency.")
                    % rec.currency_id.name
                )

    @api.onchange("cost_center_id")
    def _onchange_cost_center_id(self):
        for rec in self:
            if rec.cost_center_id:
                rec.company_id = rec.cost_center_id.company_id

    # -------------------------------------------------------------------------
    # CONSTRAINTS & ORM OVERRIDES
    # -------------------------------------------------------------------------

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_("The start date of the budget plan must be before the end date."))

    @api.constrains("date_from", "date_to", "cost_center_id", "state")
    def _check_overlap(self):
        for rec in self:
            if rec.state in ("approved", "submitted") and rec.cost_center_id:
                overlap_domain = [
                    ("cost_center_id", "=", rec.cost_center_id.id),
                    ("id", "!=", rec.id),
                    ("state", "in", ("approved", "submitted")),
                    ("date_from", "<=", rec.date_to),
                    ("date_to", ">=", rec.date_from),
                ]
                if self.search_count(overlap_domain):
                    raise ValidationError(
                        _("An overlapping budget already exists for this Cost Center during the specified period.")
                    )

    # -------------------------------------------------------------------------
    # PROTECTION HELPERS
    # -------------------------------------------------------------------------

    PROTECTED_STATES = ("approved", "revised", "closed", "cancelled")
    SUBMITTED_RESTRICTED = ("submitted",)

    @staticmethod
    def _is_mail_write(vals):
        mail_fields = {
            "message_follower_ids",
            "activity_ids",
            "message_ids",
            "activity_state",
            "message_is_follower",
            "message_partner_ids",
            "message_channel_ids",
            "message_ids",
            "activity_ids",
            "activity_type_id",
            "activity_summary",
            "activity_note",
            "activity_date_deadline",
            "activity_user_id",
            "activity_state",
        }
        return all(field in mail_fields for field in vals)

    def _check_state_protection(self, vals):
        if self._is_mail_write(vals):
            return
        # Allow pure state transitions (e.g. action_cancel writes {"state": ...})
        # even on protected states. The state machine is the transition; the
        # protection is against modifying other fields of a finalized budget.
        if set(vals.keys()) <= {"state"}:
            return

        for rec in self:
            if rec.state in self.PROTECTED_STATES:
                raise UserError(
                    _("Cannot modify a budget that is in %s state.") % rec.state
                )
            if rec.state in self.SUBMITTED_RESTRICTED:
                if not self.env.user.has_group(
                    "cost_center_budget_control.group_budget_manager"
                ):
                    raise UserError(
                        _("Only Budget Managers can modify a submitted budget.")
                    )

    def _filter_protected_fields(self, vals):
        if self.env.su:
            return vals

        if self._is_mail_write(vals):
            return vals

        protected_fields = {
            "name",
            "cost_center_id",
            "date_from",
            "date_to",
            "line_ids",
            "approved_by",
            "approved_date",
        }

        for rec in self:
            if rec.state in self.PROTECTED_STATES:
                for field in protected_fields:
                    vals.pop(field, None)
            elif rec.state in self.SUBMITTED_RESTRICTED:
                if not self.env.user.has_group(
                    "cost_center_budget_control.group_budget_manager"
                ):
                    for field in protected_fields:
                        vals.pop(field, None)

        return vals

    # -------------------------------------------------------------------------
    # ORM OVERRIDES
    # -------------------------------------------------------------------------

    def write(self, vals):
        if self.env.context.get("bypass_state_protection"):
            return super().write(vals)
        self._check_state_protection(vals)
        vals = self._filter_protected_fields(vals)
        if vals:
            return super().write(vals)
        return True

    # -------------------------------------------------------------------------
    # WORKFLOW ACTIONS
    # -------------------------------------------------------------------------

    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft budgets can be submitted."))
            rec.with_context(bypass_state_protection=True).write({"state": "submitted"})
            rec.message_post(body=_("Budget submitted for approval."))

    def action_approve(self):
        self.ensure_one()
        if self.state != "submitted":
            raise UserError(_("Only submitted budgets can be approved."))
        self.with_context(bypass_state_protection=True).write({
            "state": "approved",
            "approved_by": self.env.user.id,
            "approved_date": fields.Datetime.now(),
        })
        self.message_post(body=_("Budget approved by %s." % self.env.user.name))

    def action_reset_to_draft(self):
        self.ensure_one()
        if self.state not in ("submitted", "approved"):
            raise UserError(_("Only submitted or approved budgets can be reset to draft."))
        self.with_context(bypass_state_protection=True).write({
            "state": "draft",
            "approved_by": False,
            "approved_date": False,
        })
        self.message_post(body=_("Budget reset to draft."))

    def action_cancel(self):
        for rec in self:
            if rec.state in ("closed", "cancelled"):
                raise UserError(_("Cannot cancel a closed or already cancelled budget."))
            rec.with_context(bypass_state_protection=True).write({"state": "cancelled"})
            rec.message_post(body=_("Budget cancelled."))

    def action_close(self):
        for rec in self:
            if rec.state in ("closed", "cancelled", "revised"):
                raise UserError(_("Cannot close a budget that is already closed, cancelled, or revised."))
            if rec.state == "draft":
                 raise UserError(_("Draft budgets cannot be closed directly."))
            rec.with_context(bypass_state_protection=True).write({"state": "closed"})
            rec.message_post(body=_("Budget closed."))

    def action_revise(self):
        """Create a new revision of this approved budget.

        - Original budget transitions to 'revised' state (immutable history).
        - New budget is created as a clone in 'approved' state with
          ' (Rev N)' suffix, linked via parent_revision_id.
        - Both versions post a chatter message cross-referencing the other.

        Returns an action to open the newly created revision.
        """
        Revisions = self.env["budget.plan"]
        for rec in self:
            if rec.state != "approved":
                raise UserError(_("Only approved budgets can be revised."))
            # Next revision is the current one + 1 (walk the parent chain
            # implicitly via the integer itself; no need to query children).
            next_rev = rec.revision_number + 1

            # 1) Mark original as 'revised' FIRST so the new approved plan
            #    passes the _check_overlap constraint below.
            rec.with_context(bypass_state_protection=True).write({"state": "revised"})

            # 2) Clone the now-revised budget into a new approved budget.
            new_budget = rec.copy({
                "name": _("%s (Rev %s)") % (rec.name, next_rev),
                "state": "approved",
                "parent_revision_id": rec.id,
                "revision_number": next_rev,
                "approved_by": self.env.user.id,
                "approved_date": fields.Datetime.now(),
                "line_ids": [(0, 0, {
                    "account_id": line.account_id.id,
                    "name": line.name,
                    "planned_amount": line.planned_amount,
                }) for line in rec.line_ids],
            })
            rec.message_post(body=_("Revised as %s.") % new_budget.name)
            new_budget.message_post(
                body=_("Created as revision of %s.") % rec.name
            )
            Revisions |= new_budget

        if len(Revisions) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Revised Budget"),
                "res_model": "budget.plan",
                "res_id": Revisions.id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Revised Budgets"),
            "res_model": "budget.plan",
            "domain": [("id", "in", Revisions.ids)],
            "view_mode": "list,form",
            "target": "current",
        }


class BudgetPlanLine(models.Model):
    _name = "budget.plan.line"
    _description = "Budget Plan Line"
    _check_company_auto = True

    _sql_constraints = [
        (
            'unique_plan_account',
            'UNIQUE(plan_id, account_id)',
            'A budget line already exists for this account in this budget plan.'
        ),
    ]

    @api.model
    def _get_impacted_budget_lines_from_move(self, move):
        """Return budget lines impacted by a posted move."""
        analytic_ids = set()
        account_ids = set()
        for line in move.line_ids.filtered(lambda l: l.company_id == move.company_id):
            if line.analytic_distribution:
                analytic_ids |= {int(aid) for aid in line.analytic_distribution.keys() if aid.isdigit()}
            elif "analytic_account_id" in line._fields and line.analytic_account_id:
                analytic_ids.add(line.analytic_account_id.id)
            if line.account_id:
                account_ids.add(line.account_id.id)

        if not analytic_ids or not account_ids:
            return self.browse()

        date = move.date
        return self.search([
            ('company_id', '=', move.company_id.id),
            ('plan_id.date_from', '<=', date),
            ('plan_id.date_to', '>=', date),
            ('plan_id.cost_center_id.analytic_account_id', 'in', list(analytic_ids)),
            ('account_id', 'in', list(account_ids)),
        ])

    @api.model
    def _get_impacted_budget_lines_from_po_line(self, po_line):
        """Return budget lines impacted by a Purchase Order line.

        Mirrors ``_get_impacted_budget_lines_from_move`` but for PO lines.
        Joins through the PO's company + date_order against the budget plan
        period, and matches via analytic_distribution on the PO line.

        Note: we do not pre-filter by ``po.state`` here. Cancelled POs must
        still return the previously-impacted budget lines so that recompute
        can zero out the committed amount. The actual ``po.state`` filter
        lives in the SQL inside ``_compute_committed_amount``.
        """
        po = po_line.order_id
        if not po:
            return self.browse()
        analytic_ids = set()
        for key in (po_line.analytic_distribution or {}).keys():
            try:
                analytic_ids.add(int(key))
            except (TypeError, ValueError):
                continue
        if not analytic_ids:
            return self.browse()
        return self.search([
            ("company_id", "=", po.company_id.id),
            ("plan_id.date_from", "<=", po.date_order),
            ("plan_id.date_to", ">=", po.date_order),
            ("plan_id.cost_center_id.analytic_account_id", "in", list(analytic_ids)),
        ])

    @api.model
    def _recompute_actual_amount_batch(self, lines):
        """Recompute actual_amount for impacted budget lines.

        Computed fields with store=True are automatically persisted by the ORM
        on flush, so explicit write() calls are unnecessary. Triggering the
        compute methods here is enough.
        """
        if not lines:
            return
        protected_lines = lines.with_context(bypass_protection=True)
        protected_lines.invalidate_recordset()
        protected_lines._compute_actual_amount()
        protected_lines._compute_remaining_amount()
        protected_lines._compute_usage_percent()
        protected_lines._compute_alert_level()
        protected_lines._compute_committed_amount()

    plan_id = fields.Many2one(
        "budget.plan",
        string="Budget Plan",
        required=True,
        ondelete="cascade",
        index=True,
        check_company=True,
    )
    account_id = fields.Many2one(
        "account.account",
        string="Account",
        required=True,
        index=True,
        check_company=True,
        domain=[("account_type", "in", (
            "expense", "expense_depreciation", "expense_direct_cost"
        ))]
    )
    name = fields.Char(string="Description", default="")
    planned_amount = fields.Monetary(
        string="Planned Amount",
        required=True,
        currency_field="currency_id"
    )
    actual_amount = fields.Monetary(
        string="Actual Amount",
        currency_field="currency_id",
        readonly=True,
        compute="_compute_actual_amount",
        store=True,
    )
    po_committed_amount = fields.Monetary(
        string="PO Committed",
        currency_field="currency_id",
        readonly=True,
        compute="_compute_committed_amount",
        store=True,
        help="Amount in confirmed (not yet invoiced) Purchase Orders for this "
             "budget line. Computed from purchase.order.line via analytic_distribution.",
    )
    committed_amount = fields.Monetary(
        string="Committed",
        currency_field="currency_id",
        readonly=True,
        compute="_compute_committed_amount",
        store=True,
        help="Total committed = Actual + unbilled PO committed. Mirrors Odoo 18 "
             "native 'Committed' column convention.",
    )
    available_amount = fields.Monetary(
        string="Available",
        currency_field="currency_id",
        readonly=True,
        compute="_compute_committed_amount",
        store=True,
        help="Planned - Committed. Negative = over-committed.",
    )
    remaining_amount = fields.Monetary(
        string="Remaining Amount",
        currency_field="currency_id",
        compute="_compute_remaining_amount",
        store=True,
        help="The remaining budget amount (Planned - Actual).",
    )
    usage_percent = fields.Float(
        string="Usage %",
        readonly=True,
        compute="_compute_usage_percent",
        store=True,
    )
    alert_level = fields.Selection([
        ("normal", "Normal"),
        ("warning", "Warning"),
        ("danger", "Danger"),
        ("exceeded", "Exceeded"),
    ], compute="_compute_alert_level", store=True, readonly=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="plan_id.currency_id",
        readonly=True,
        store=True
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        string="Company Currency",
        related="plan_id.company_currency_id",
        readonly=True,
        store=True,
    )
    is_multi_currency = fields.Boolean(
        string="Multi-Currency",
        related="plan_id.is_multi_currency",
        store=True,
    )
    planned_amount_company_currency = fields.Monetary(
        string="Planned (Company Curr.)",
        currency_field="company_currency_id",
        compute="_compute_company_currency_amounts",
        help="Planned amount converted to the company's reporting currency.",
    )
    actual_amount_company_currency = fields.Monetary(
        string="Actual (Company Curr.)",
        currency_field="company_currency_id",
        compute="_compute_company_currency_amounts",
        help="Actual amount converted to the company's reporting currency.",
    )
    committed_amount_company_currency = fields.Monetary(
        string="Committed (Company Curr.)",
        currency_field="company_currency_id",
        compute="_compute_company_currency_amounts",
        help="Committed amount converted to the company's reporting currency.",
    )
    available_amount_company_currency = fields.Monetary(
        string="Available (Company Curr.)",
        currency_field="company_currency_id",
        compute="_compute_company_currency_amounts",
        help="Available amount converted to the company's reporting currency.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="plan_id.company_id",
        store=True,
        readonly=True
    )

    # -------------------------------------------------------------------------
    # COMPUTED FIELDS
    # -------------------------------------------------------------------------

    @api.depends(
        "plan_id.date_from",
        "plan_id.date_to",
        "plan_id.cost_center_id.analytic_account_id",
        "account_id",
    )
    def _compute_actual_amount(self):
        """Compute actual amount using Odoo 18 analytic_distribution (JSONB)."""
        for rec in self:
            if not all([rec.plan_id, rec.account_id]):
                rec.actual_amount = 0.0
                continue

            plan = rec.plan_id
            analytic_account = plan.cost_center_id.analytic_account_id
            if not analytic_account:
                rec.actual_amount = 0.0
                continue

            analytic_key = str(analytic_account.id)

            # SQL: weighted aggregation via analytic_distribution JSONB
            sql_weighted = (
                "SELECT COALESCE(SUM((l.balance)::numeric * (l.analytic_distribution->>%s)::numeric / 100.0), 0.0) "
                "FROM account_move_line l "
                "WHERE l.account_id = %s "
                "AND l.company_id = %s "
                "AND l.parent_state = 'posted' "
                "AND l.date >= %s "
                "AND l.date <= %s "
                "AND l.analytic_distribution ? %s"
            )

            params = (
                analytic_key,
                rec.account_id.id,
                rec.company_id.id,
                plan.date_from,
                plan.date_to,
                analytic_key,
            )
            self.env.cr.execute(sql_weighted, params)
            weighted_sum = self.env.cr.fetchone()[0] or 0.0

            if "analytic_account_id" in self.env["account.move.line"]._fields:
                sql_fallback = (
                    "SELECT COALESCE(SUM((l.balance)::numeric), 0.0) "
                    "FROM account_move_line l "
                    "WHERE l.account_id = %s "
                    "AND l.company_id = %s "
                    "AND l.parent_state = 'posted' "
                    "AND l.date >= %s "
                    "AND l.date <= %s "
                    "AND l.analytic_account_id = %s "
                    "AND (l.analytic_distribution IS NULL OR l.analytic_distribution = '{}'::jsonb)"
                )
                params_fb = (
                    rec.account_id.id,
                    rec.company_id.id,
                    plan.date_from,
                    plan.date_to,
                    analytic_account.id,
                )
                self.env.cr.execute(sql_fallback, params_fb)
                weighted_sum += self.env.cr.fetchone()[0] or 0.0

            rec.actual_amount = float_round(weighted_sum, precision_digits=rec.currency_id.decimal_places)

    @api.depends(
        "plan_id.date_from",
        "plan_id.date_to",
        "plan_id.cost_center_id.analytic_account_id",
        "account_id",
    )
    def _compute_committed_amount(self):
        """Compute PO-committed, total committed, and available amounts.

        Mirrors the Odoo 18 native convention: Committed = Achieved (posted) +
        unbilled confirmed Purchase Orders. Available = Planned - Committed.

        Uses parameterized SQL aggregation against purchase_order_line
        analytic_distribution (JSONB) to keep performance predictable on
        large datasets. The post_init_hook installs the supporting GIN
        index, so this query uses the same index path as actual_amount.
        """
        for rec in self:
            po_committed = 0.0
            if all([rec.plan_id, rec.account_id, rec.plan_id.cost_center_id]):
                analytic_account = rec.plan_id.cost_center_id.analytic_account_id
                if analytic_account:
                    analytic_key = str(analytic_account.id)
                    plan = rec.plan_id
                    currency = rec.currency_id
                    # SQL: weighted aggregation via analytic_distribution JSONB
                    sql_po = (
                        "SELECT COALESCE(SUM("
                        "  (l.price_subtotal)::numeric * "
                        "  COALESCE((l.analytic_distribution->>%s)::numeric, 0) / 100.0"
                        "), 0.0) "
                        "FROM purchase_order_line l "
                        "JOIN purchase_order o ON o.id = l.order_id "
                        "WHERE l.product_id IS NOT NULL "
                        "  AND o.state IN ('purchase', 'done') "
                        "  AND o.company_id = %s "
                        "  AND o.date_order >= %s "
                        "  AND o.date_order <= %s "
                        "  AND l.analytic_distribution ? %s"
                    )
                    params_po = (
                        analytic_key,
                        rec.company_id.id,
                        plan.date_from,
                        plan.date_to,
                        analytic_key,
                    )
                    try:
                        with rec.env.cr.savepoint():
                            rec.env.cr.execute(sql_po, params_po)
                            po_committed = rec.env.cr.fetchone()[0] or 0.0
                    except Exception:
                        # If purchase module data isn't ready or table missing
                        # during initial install, skip without breaking the
                        # compute. Recompute on next write. Savepoint ensures
                        # the failed SQL doesn't poison the outer transaction.
                        po_committed = 0.0

            po_committed = float_round(
                po_committed, precision_digits=rec.currency_id.decimal_places
            )
            committed = float_round(
                rec.actual_amount + po_committed,
                precision_digits=rec.currency_id.decimal_places,
            )
            rec.po_committed_amount = po_committed
            rec.committed_amount = committed
            rec.available_amount = float_round(
                rec.planned_amount - committed,
                precision_digits=rec.currency_id.decimal_places,
            )

    @api.depends("planned_amount", "actual_amount")
    def _compute_remaining_amount(self):
        for rec in self:
            rec.remaining_amount = rec.planned_amount - rec.actual_amount

    @api.depends("planned_amount", "actual_amount")
    def _compute_usage_percent(self):
        for rec in self:
            if rec.planned_amount and rec.planned_amount > 0:
                rec.usage_percent = (rec.actual_amount / rec.planned_amount) * 100
            else:
                rec.usage_percent = 0.0

    @api.depends("usage_percent")
    def _compute_alert_level(self):
        get_param = self.env["ir.config_parameter"].sudo().get_param
        warning_thr = float(get_param("cost_center_budget_control.warning_threshold", "70"))
        critical_thr = float(get_param("cost_center_budget_control.critical_threshold", "90"))
        blocking_thr = float(get_param("cost_center_budget_control.blocking_threshold", "100"))
        for rec in self:
            pct = rec.usage_percent
            if pct >= blocking_thr:
                rec.alert_level = "exceeded"
            elif pct >= critical_thr:
                rec.alert_level = "danger"
            elif pct >= warning_thr:
                rec.alert_level = "warning"
            else:
                rec.alert_level = "normal"

    @api.depends(
        "planned_amount",
        "actual_amount",
        "committed_amount",
        "available_amount",
        "currency_id",
        "company_currency_id",
    )
    def _compute_company_currency_amounts(self):
        """Convert budget amounts to the company's reporting currency.

        This is a best-effort informational conversion. It uses the latest
        ``res.currency.rate`` available on the budget plan's start date.
        If no rate is defined, the original amount is shown (no conversion).
        """
        for rec in self:
            if not rec.is_multi_currency or not rec.company_currency_id or not rec.currency_id:
                rec.planned_amount_company_currency = rec.planned_amount
                rec.actual_amount_company_currency = rec.actual_amount
                rec.committed_amount_company_currency = rec.committed_amount
                rec.available_amount_company_currency = rec.available_amount
                continue

            rate_date = rec.plan_id.date_from or fields.Date.today()
            rec.planned_amount_company_currency = rec.currency_id._convert(
                rec.planned_amount,
                rec.company_currency_id,
                rec.company_id,
                rate_date,
            )
            rec.actual_amount_company_currency = rec.currency_id._convert(
                rec.actual_amount,
                rec.company_currency_id,
                rec.company_id,
                rate_date,
            )
            rec.committed_amount_company_currency = rec.currency_id._convert(
                rec.committed_amount,
                rec.company_currency_id,
                rec.company_id,
                rate_date,
            )
            rec.available_amount_company_currency = rec.currency_id._convert(
                rec.available_amount,
                rec.company_currency_id,
                rec.company_id,
                rate_date,
            )

    def write(self, vals):
        if self.env.context.get('bypass_protection'):
            return super().write(vals)

        system_computed_fields = {
            "actual_amount",
            "po_committed_amount",
            "committed_amount",
            "available_amount",
            "remaining_amount",
            "usage_percent",
            "alert_level",
        }
        if vals and set(vals).issubset(system_computed_fields):
            return super().write(vals)

        for rec in self:
            if rec.plan_id.state in ("approved", "closed", "cancelled") and not self.env.su:
                raise UserError(_("Cannot modify a budget line that is in Approved, Closed or Cancelled state."))
        return super().write(vals)

    def unlink(self):
        if self.env.context.get('bypass_protection'):
            return super().unlink()

        for rec in self:
            if rec.plan_id.state in ("submitted", "approved", "closed", "cancelled") and not self.env.su:
                raise UserError(_("Cannot delete a budget line that is not in Draft state."))
        return super().unlink()