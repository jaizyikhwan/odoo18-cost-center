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
        related="company_id.currency_id",
        readonly=True,
        store=True
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

    PROTECTED_STATES = ("approved", "closed", "cancelled")
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
        if self.env.su:
            return

        if self._is_mail_write(vals):
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
            rec.write({"state": "submitted"})
            rec.message_post(body=_("Budget submitted for approval."))

    def action_approve(self):
        self.ensure_one()
        if self.state != "submitted":
            raise UserError(_("Only submitted budgets can be approved."))
        self.write({
            "state": "approved",
            "approved_by": self.env.user.id,
            "approved_date": fields.Datetime.now(),
        })
        self.message_post(body=_("Budget approved by %s." % self.env.user.name))

    def action_reset_to_draft(self):
        self.ensure_one()
        if self.state not in ("submitted", "approved"):
            raise UserError(_("Only submitted or approved budgets can be reset to draft."))
        self.write({
            "state": "draft",
            "approved_by": False,
            "approved_date": False,
        })
        self.message_post(body=_("Budget reset to draft."))

    def action_cancel(self):
        for rec in self:
            if rec.state in ("closed", "cancelled"):
                raise UserError(_("Cannot cancel a closed or already cancelled budget."))
            rec.write({"state": "cancelled"})
            rec.message_post(body=_("Budget cancelled."))

    def action_close(self):
        for rec in self:
            if rec.state in ("closed", "cancelled"):
                raise UserError(_("Cannot close a budget that is already closed or cancelled."))
            if rec.state == "draft":
                 raise UserError(_("Draft budgets cannot be closed directly."))
            rec.write({"state": "closed"})
            rec.message_post(body=_("Budget closed."))


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
        protected_lines._compute_variance_amount()
        protected_lines._compute_remaining_amount()
        protected_lines._compute_usage_percent()
        protected_lines._compute_alert_level()

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
    variance_amount = fields.Monetary(
        string="Variance",
        currency_field="currency_id",
        readonly=True,
        compute="_compute_variance_amount",
        store=True,
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

    @api.depends("planned_amount", "actual_amount")
    def _compute_variance_amount(self):
        for rec in self:
            rec.variance_amount = rec.planned_amount - rec.actual_amount

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

    def write(self, vals):
        if self.env.context.get('bypass_protection'):
            return super().write(vals)

        system_computed_fields = {
            "actual_amount",
            "variance_amount",
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