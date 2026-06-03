from odoo import models, fields


class BudgetAllocationLine(models.Model):
    _name = "budget.allocation.line"
    _description = "Allocation Line"
    _rec_name = "cost_center_id"
    _check_company_auto = True

    allocation_id = fields.Many2one(
        "budget.allocation",
        string="Allocation",
        required=True,
        ondelete="cascade",
        index=True,
    )

    cost_center_id = fields.Many2one(
        "cost.center",
        string="Target Cost Center",
        required=True,
        ondelete="restrict",
        check_company=True,
    )

    percentage = fields.Float(
        string="Percentage (%)",
        required=True,
        default=0.0,
    )

    company_id = fields.Many2one(
        "res.company",
        related="allocation_id.company_id",
        store=True,
        readonly=True,
    )
