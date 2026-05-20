from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date


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
        related="cost_center_id.company_id", 
        store=True, 
        readonly=True
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
                # Check for overlapping 'approved' or 'submitted' budgets for the same cost center
                overlap_domain = [
                    ("cost_center_id", "=", rec.cost_center_id.id),
                    ("id", "!=", rec.id),
                    ("state", "in", ("approved", "submitted")),
                    ("date_from", "<=", rec.date_to),
                    ("date_to", ">=", rec.date_from),
                ]
                if self.search(overlap_domain, count=True):
                    raise ValidationError(
                        _("An overlapping budget already exists for this Cost Center during the specified period.")
                    )

    def write(self, vals):
        # Allow mail_thread/activity_mixin related fields to be updated in any state
        mail_fields = ['message_follower_ids', 'activity_ids', 'message_ids', 'activity_state'] # add other mail fields if needed
        if not any(field in vals for field in mail_fields):
            # If no mail fields are updated, apply state-based protection
            for rec in self:
                if rec.state in ("approved", "closed", "cancelled") and not self.env.su:
                    raise UserError(_("Cannot modify a budget that is in Approved, Closed or Cancelled state."))
                if rec.state == "submitted" and not self.env.user.has_group("cost_center_budget_control.group_budget_manager") and not self.env.su:
                    # Allow Budget Manager to edit submitted budgets (e.g., to reset_to_draft or approve)
                    # Otherwise, block regular users
                    raise UserError(_("Only Budget Managers can modify a submitted budget."))
        
        # Remove state from vals if it's being set directly to a protected state outside allowed transitions
        if "state" in vals and vals["state"] in ("approved", "closed", "cancelled") and not self.env.su:
            if self.state not in ("submitted") or vals["state"] != "approved": # Allow draft->submitted, submitted->approved, active->closed/cancelled
                if self.state not in ("approved") or vals["state"] != "closed":
                    if self.state not in ("approved") or vals["state"] != "cancelled":
                        pass # allow it
                    else:
                        raise UserError(_("Invalid state transition."))
                else:
                    pass # allow it
            else:
                pass # allow it

        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state in ("submitted", "approved", "closed", "cancelled") and not self.env.su:
                raise UserError(_("Cannot delete a budget that is not in Draft state."))
        return super().unlink()

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
        for rec in self:
            if not rec.plan_id or not rec.account_id:
                rec.actual_amount = 0.0
                continue

            analytic_account = rec.plan_id.cost_center_id.analytic_account_id
            if not analytic_account:
                rec.actual_amount = 0.0
                continue

            domain = [
                ("account_id", "=", rec.account_id.id),
                ("analytic_account_id", "=", analytic_account.id),
                ("parent_state", "=", "posted"),
                ("date", ">=", rec.plan_id.date_from),
                ("date", "<=", rec.plan_id.date_to),
            ]
            result = self.env["account.move.line"].read_group(
                domain, ["balance:sum"], []
            )
            rec.actual_amount = abs(result[0]["balance"]) if result else 0.0

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
            if rec.planned_amount:
                rec.usage_percent = (rec.actual_amount / rec.planned_amount) * 100
            else:
                rec.usage_percent = 0.0

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------

    @api.onchange("account_id")
    def _onchange_account_id(self):
        if self.account_id and not self.name:
            self.name = self.account_id.name

