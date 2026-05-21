from odoo import models, api


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, **kwargs):
        res = super()._post(**kwargs)
        for move in self:
            impacted = self.env["budget.plan.line"]._get_impacted_budget_lines_from_move(move)
            if impacted:
                self.env["budget.plan.line"]._recompute_actual_amount_batch(impacted)
        return res


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def write(self, vals):
        res = super().write(vals)
        if "analytic_distribution" not in vals:
            return res

        moves = self.mapped("move_id").filtered(lambda m: m.state == "posted")
        for move in moves:
            impacted = self.env["budget.plan.line"]._get_impacted_budget_lines_from_move(move)
            if impacted:
                self.env["budget.plan.line"]._recompute_actual_amount_batch(impacted)
        return res
