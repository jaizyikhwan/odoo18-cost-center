# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BudgetApprovalWizard(models.TransientModel):
    _name = "budget.approval.wizard"
    _description = "Budget Approval Wizard"

    plan_ids = fields.Many2many(
        "budget.plan",
        string="Budget Plans",
        required=True,
    )
    action_type = fields.Selection(
        selection=[
            ("approve", "Approve"),
            ("reject", "Reject"),
            ("cancel", "Cancel"),
        ],
        string="Action",
        required=True,
    )
    comment = fields.Text(
        string="Comment",
        help="Optional comment explaining the decision. Will be posted to chatter.",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_model") == "budget.plan" and self.env.context.get("active_ids"):
            res["plan_ids"] = [(6, 0, self.env.context["active_ids"])]
        return res

    def action_apply(self):
        self.ensure_one()
        if not self.plan_ids:
            raise UserError(_("Please select at least one budget plan."))

        posted = 0
        for plan in self.plan_ids:
            if self.action_type == "approve" and plan.state == "submitted":
                plan.action_approve()
                posted += 1
            elif self.action_type == "reject" and plan.state == "submitted":
                plan.write({"state": "draft"})
                if self.comment:
                    plan.message_post(body=_("Rejected: %s") % self.comment)
                posted += 1
            elif self.action_type == "cancel" and plan.state not in ("closed", "cancelled"):
                plan.action_cancel()
                if self.comment:
                    plan.message_post(body=_("Cancelled: %s") % self.comment)
                posted += 1

        if posted == 0:
            raise UserError(
                _("No plans were affected. Make sure the selected plans are in the correct state for this action.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Budget Plans"),
            "res_model": "budget.plan",
            "view_mode": "list,form",
            "target": "main",
        }
