# -*- coding: utf-8 -*-
"""Purchase Order integration for budget committed amount tracking.

Mirrors Odoo 18 native behavior: confirmed Purchase Orders contribute to the
budget line's "Committed" amount (Actual + unbilled POs). When a PO is
cancelled or amended, the committed amount is recomputed accordingly.

The ``block_on_purchase`` setting (opt-in, off by default) lets companies
enforce the same hard block on RFQ confirmation that the move posting hook
already enforces.
"""
import logging

from odoo import _, models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _get_impacted_budget_lines(self):
        """Return budget.plan.line records impacted by any line in this PO."""
        impacted = self.env["budget.plan.line"].browse()
        for order in self:
            for po_line in order.order_line:
                impacted |= self.env["budget.plan.line"]._get_impacted_budget_lines_from_po_line(po_line)
        return impacted

    def _recompute_committed_amounts(self):
        impacted = self._get_impacted_budget_lines()
        if impacted:
            self.env["budget.plan.line"]._recompute_actual_amount_batch(impacted)

    def button_confirm(self):
        """Confirm RFQ. If block_on_purchase is enabled, validate first."""
        for order in self:
            self._validate_budget_on_purchase(order)
        result = super().button_confirm()
        self._recompute_committed_amounts()
        return result

    def button_cancel(self):
        result = super().button_cancel()
        self._recompute_committed_amounts()
        return result

    def action_rfq_send(self):
        result = super().action_rfq_send()
        # Sending RFQ may not change state, but a recompute is cheap and safe
        self._recompute_committed_amounts()
        return result

    def _validate_budget_on_purchase(self, order):
        """Raise UserError if a PO line would exceed the budget blocking threshold.

        Controlled by ``cost_center_budget_control.block_on_purchase``. Off
        by default. When enabled, it mirrors the move-level hook: blocking
        mode + threshold breach + no override manager group => blocked.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        enabled = ICP.get_param(
            "cost_center_budget_control.block_on_purchase", "False"
        ) == "True"
        if not enabled:
            return

        control_mode = ICP.get_param(
            "cost_center_budget_control.mode", "warning_only"
        )
        if control_mode != "blocking":
            return

        blocking_thr = float(ICP.get_param(
            "cost_center_budget_control.blocking_threshold", "100.0"
        ))
        warning_thr = float(ICP.get_param(
            "cost_center_budget_control.warning_threshold", "0.0"
        ))

        blocked_names = []
        for po_line in order.order_line:
            analytic_ids = set()
            for key in (po_line.analytic_distribution or {}).keys():
                try:
                    analytic_ids.add(int(key))
                except (TypeError, ValueError):
                    continue
            if not analytic_ids:
                continue
            # The line is valued in the order's currency; convert to company
            # currency if needed (handled inside the budget line's compute).
            raw_amount = po_line.price_subtotal
            impacted = self.env["budget.plan.line"].search([
                ("company_id", "=", order.company_id.id),
                ("plan_id.date_from", "<=", order.date_order),
                ("plan_id.date_to", ">=", order.date_order),
                ("plan_id.state", "in", ("approved", "submitted")),
                ("plan_id.cost_center_id.analytic_account_id", "in", list(analytic_ids)),
            ])
            for bud_line in impacted:
                if not bud_line.planned_amount or bud_line.planned_amount <= 0:
                    continue
                projected = bud_line.actual_amount + bud_line.po_committed_amount + raw_amount
                pct = projected / bud_line.planned_amount * 100.0
                if pct >= blocking_thr:
                    blocked_names.append(bud_line.plan_id.name)

        if blocked_names:
            override_allowed = self.env.user.has_group(
                "cost_center_budget_control.group_budget_override_manager"
            )
            if not override_allowed:
                msg = _(
                    "Budget Control BLOCKED on Purchase Order %(name)s.\n"
                    "The following budgets would exceed their blocking threshold:\n"
                    "%(budgets)s\n\n"
                    "Contact a Budget Override Manager to request an exception."
                ) % {
                    "name": order.name,
                    "budgets": ", ".join(blocked_names),
                }
                raise UserError(msg)
            _logger.info(
                "Budget override applied for PO %s by user %s",
                order.name, self.env.user.name,
            )


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _recompute_budget_lines(self):
        impacted = self.env["budget.plan.line"].browse()
        for po_line in self:
            impacted |= self.env["budget.plan.line"]._get_impacted_budget_lines_from_po_line(po_line)
        if impacted:
            self.env["budget.plan.line"]._recompute_actual_amount_batch(impacted)

    def write(self, vals):
        tracked_fields = {
            "analytic_distribution",
            "price_subtotal",
            "price_unit",
            "product_qty",
            "date_planned",
            "currency_id",
        }
        res = super().write(vals)
        if tracked_fields.intersection(vals):
            self._recompute_budget_lines()
        return res

    def unlink(self):
        self._recompute_budget_lines()
        return super().unlink()
