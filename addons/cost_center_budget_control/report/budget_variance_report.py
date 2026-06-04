# -*- coding: utf-8 -*-

from odoo import api, models


class BudgetVarianceReport(models.AbstractModel):
    _name = "report.cost_center_budget_control.budget_variance_report"
    _description = "Budget Variance Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["budget.plan"].browse(docids)
        return {
            "doc_ids": docids,
            "doc_model": "budget.plan",
            "docs": docs,
            "data": data or {},
        }
