from odoo import models, fields

class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    cost_center_id = fields.Many2one(
        "cost.center",
        string="Cost Center",
        ondelete="set null",
        help="The cost center associated with this analytic account."
    )
