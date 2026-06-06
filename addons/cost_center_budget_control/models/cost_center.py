import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class CostCenter(models.Model):
    _name = "cost.center"
    _description = "Cost Center"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "complete_name"
    _rec_name = "complete_name"
    _parent_name = "parent_id"
    _parent_store = True
    _check_company_auto = True

    name = fields.Char(string="Name", required=True, tracking=True)
    code = fields.Char(string="Code", required=True, copy=False, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    
    complete_name = fields.Char(
        string="Full Name",
        compute="_compute_complete_name",
        recursive=True,
        store=True
    )
    
    parent_id = fields.Many2one(
        "cost.center", 
        string="Parent", 
        index=True, 
        ondelete="restrict",
        check_company=True
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("cost.center", "parent_id", string="Children")
    
    responsible_id = fields.Many2one(
        "res.users", 
        string="Responsible", 
        tracking=True,
        check_company=True,
        default=lambda self: self.env.user
    )
    
    company_id = fields.Many2one(
        "res.company", 
        string="Company", 
        required=True,
        index=True,
        default=lambda self: self.env.company
    )
    
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        ondelete="restrict",
        check_company=True,
        tracking=True,
        domain="[('company_id', '=', company_id)]",
        help="Linked analytic account for financial tracking. Created automatically if left empty."
    )

    # Smart button counts (shown in form view button box)
    budget_plan_count = fields.Integer(
        string="Budget Plans",
        compute="_compute_budget_plan_count",
    )
    budget_plan_total_planned = fields.Monetary(
        string="Total Planned",
        compute="_compute_budget_plan_count",
        currency_field="company_currency_id",
    )
    over_budget_line_count = fields.Integer(
        string="Over-Budget Lines",
        compute="_compute_over_budget_line_count",
        help="Number of budget lines where the available amount is negative.",
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        string="Company Currency",
        related="company_id.currency_id",
        readonly=True,
    )

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for rec in self:
            if rec.parent_id:
                rec.complete_name = f"{rec.parent_id.complete_name} / {rec.name}"
            else:
                rec.complete_name = rec.name

    @api.constrains("parent_id")
    def _check_parent_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_("Error! You cannot create recursive cost centers."))

    def _compute_budget_plan_count(self):
        """Count of budget plans + total planned amount (in company currency).

        Total planned is summed from the latest revision of each plan only,
        so historical revisions do not inflate the figure.
        """
        Plan = self.env["budget.plan"]
        for rec in self:
            plans = Plan.search([
                ("cost_center_id", "=", rec.id),
                ("is_latest_revision", "=", True),
            ])
            rec.budget_plan_count = len(plans)
            if not plans:
                rec.budget_plan_total_planned = 0.0
                continue
            # Convert planned totals to company currency (budget may differ)
            total = 0.0
            for plan in plans:
                plan_total = sum(plan.line_ids.mapped("planned_amount"))
                if plan.currency_id != rec.company_id.currency_id:
                    plan_total = plan.currency_id._convert(
                        plan_total,
                        rec.company_id.currency_id,
                        rec.company_id,
                        plan.date_from or fields.Date.today(),
                    )
                total += plan_total
            rec.budget_plan_total_planned = total

    def _compute_over_budget_line_count(self):
        Line = self.env["budget.plan.line"]
        for rec in self:
            rec.over_budget_line_count = Line.search_count([
                ("plan_id.cost_center_id", "=", rec.id),
                ("plan_id.is_latest_revision", "=", True),
                ("available_amount", "<", 0),
            ])

    def action_view_budget_plans(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Budget Plans"),
            "res_model": "budget.plan",
            "view_mode": "list,form",
            "domain": [
                ("cost_center_id", "=", self.id),
                ("is_latest_revision", "=", True),
            ],
            "context": {"default_cost_center_id": self.id, "search_default_latest_revision": 1},
        }

    def action_view_over_budget_lines(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Over-Budget Lines"),
            "res_model": "budget.plan.line",
            "view_mode": "list,form",
            "domain": [
                ("plan_id.cost_center_id", "=", self.id),
                ("plan_id.is_latest_revision", "=", True),
                ("available_amount", "<", 0),
            ],
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("analytic_account_id"):
                company_id = vals.get("company_id") or self.env.company.id
                analytic_account = self._create_analytic_account(
                    code=vals.get("code"),
                    name=vals.get("name"),
                    company_id=company_id,
                )
                vals["analytic_account_id"] = analytic_account.id
        return super().create(vals_list)

    def write(self, vals):
        if "code" in vals or "name" in vals:
            new_code = vals.get("code")
            new_name = vals.get("name")
            for rec in self:
                if rec.analytic_account_id:
                    code = new_code or rec.code
                    name = new_name or rec.name
                    rec.analytic_account_id.name = f"[{code}] {name}" if code else name
        return super().write(vals)

    def _create_analytic_account(self, code, name, company_id):
        plan_model = self.env["account.analytic.plan"]
        domain = []
        if "company_id" in plan_model._fields:
            domain = ["|", ("company_id", "=", company_id), ("company_id", "=", False)]
        elif "company_ids" in plan_model._fields:
            domain = ["|", ("company_ids", "in", company_id), ("company_ids", "=", False)]
        plan = plan_model.search(domain, order="sequence, id", limit=1)
        analytic_vals = {
            "name": f"[{code}] {name}" if code else name,
            "company_id": company_id,
        }
        if plan:
            analytic_vals["plan_id"] = plan.id
        return self.env["account.analytic.account"].create(analytic_vals)

    _sql_constraints = [
        ("code_company_uniq", "unique(code, company_id)", "The cost center code must be unique per company!"),
    ]
