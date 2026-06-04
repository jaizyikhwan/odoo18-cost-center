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
    parent_path = fields.Char(index=True, unaccent=False)
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
