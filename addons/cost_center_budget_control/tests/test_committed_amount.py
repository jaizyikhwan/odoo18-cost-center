# -*- coding: utf-8 -*-
"""Tests for Committed Amount tracking via Purchase Order integration.

These tests cover the new ``committed_amount``, ``po_committed_amount``, and
``available_amount`` fields on ``budget.plan.line``, plus the PO hooks in
``models/purchase_order.py`` that recompute them when POs are confirmed,
cancelled, or amended.
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestCommittedAmount(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = (
            env.ref("base.main_company", raise_if_not_found=False)
            or env["res.company"].search([], limit=1)
        )
        cls.analytic_plan = env["account.analytic.plan"].create(
            {"name": "Test Committed Plan"}
        )
        cls.analytic_account = env["account.analytic.account"].create({
            "name": "AA Committed Test",
            "company_id": cls.company.id,
            "plan_id": cls.analytic_plan.id,
        })
        cls.cost_center = env["cost.center"].create({
            "name": "CC Committed",
            "code": "CCCOMMITTED",
            "company_id": cls.company.id,
            "analytic_account_id": cls.analytic_account.id,
        })
        cls.expense_account = env["account.account"].create({
            "name": "Expense Committed",
            "code": "EXPCOMMITTED",
            "account_type": "expense",
            "company_ids": [(6, 0, [cls.company.id])],
        })
        cls.product = env["product.product"].create({
            "name": "Test Product",
            "type": "service",
            "standard_price": 100.0,
        })
        cls.vendor = env["res.partner"].create({
            "name": "Test Vendor",
        })
        cls.budget_plan = env["budget.plan"].create({
            "name": "Q1 Committed Test",
            "cost_center_id": cls.cost_center.id,
            "company_id": cls.company.id,
            "date_from": "2025-01-01",
            "date_to": "2025-03-31",
        })
        cls.budget_line = env["budget.plan.line"].create({
            "plan_id": cls.budget_plan.id,
            "account_id": cls.expense_account.id,
            "planned_amount": 1000.0,
        })

    def _create_po(self, amount, distribution=None, state="draft"):
        po = self.env["purchase.order"].create({
            "partner_id": self.vendor.id,
            "company_id": self.company.id,
            "date_order": "2025-02-15",
        })
        po.write({"order_line": [(0, 0, {
            "product_id": self.product.id,
            "name": self.product.name,
            "product_qty": 1,
            "price_unit": amount,
            "analytic_distribution": distribution or {
                str(self.analytic_account.id): 100.0,
            },
        })]})
        if state in ("purchase", "done"):
            po.button_confirm()
        return po

    def test_po_committed_amount_zero_before_po(self):
        """Without any confirmed PO, po_committed_amount should be 0."""
        self.assertEqual(self.budget_line.po_committed_amount, 0.0)
        self.assertEqual(self.budget_line.committed_amount, 0.0)
        self.assertEqual(self.budget_line.available_amount, 1000.0)

    def test_po_committed_aggregated_after_confirm(self):
        """Confirming a PO should populate po_committed_amount."""
        self._create_po(300.0, state="purchase")
        self.budget_line.invalidate_recordset()
        self.assertAlmostEqual(self.budget_line.po_committed_amount, 300.0)
        self.assertAlmostEqual(self.budget_line.committed_amount, 300.0)
        self.assertAlmostEqual(self.budget_line.available_amount, 700.0)

    def test_draft_rfq_not_counted(self):
        """RFQ in draft state must NOT contribute to po_committed_amount."""
        self._create_po(500.0, state="draft")
        self.budget_line.invalidate_recordset()
        self.assertEqual(self.budget_line.po_committed_amount, 0.0)

    def test_committed_includes_actual_and_po(self):
        """When posted move + confirmed PO, committed = actual + po."""
        # Post a journal entry contributing 200 to actual
        journal = self.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", self.company.id)], limit=1
        )
        if not journal:
            journal = self.env["account.journal"].create({
                "name": "Misc Test",
                "code": "MISCCOMM",
                "type": "general",
                "company_id": self.company.id,
            })
        move = self.env["account.move"].create({
            "journal_id": journal.id,
            "date": "2025-02-10",
            "company_id": self.company.id,
            "line_ids": [
                (0, 0, {
                    "account_id": self.expense_account.id,
                    "debit": 200.0,
                    "credit": 0.0,
                    "analytic_distribution": {str(self.analytic_account.id): 100.0},
                }),
                (0, 0, {
                    "account_id": self.expense_account.id,
                    "debit": 0.0,
                    "credit": 200.0,
                }),
            ],
        })
        move.action_post()
        # Confirm a PO for 300
        self._create_po(300.0, state="purchase")
        self.budget_line.invalidate_recordset()
        self.assertAlmostEqual(self.budget_line.actual_amount, 200.0)
        self.assertAlmostEqual(self.budget_line.po_committed_amount, 300.0)
        self.assertAlmostEqual(self.budget_line.committed_amount, 500.0)
        self.assertAlmostEqual(self.budget_line.available_amount, 500.0)

    def test_po_cancelled_removes_from_committed(self):
        """Cancelling a confirmed PO should drop it from po_committed_amount."""
        po = self._create_po(400.0, state="purchase")
        self.budget_line.invalidate_recordset()
        self.assertAlmostEqual(self.budget_line.po_committed_amount, 400.0)
        po.button_cancel()
        self.budget_line.invalidate_recordset()
        self.assertEqual(self.budget_line.po_committed_amount, 0.0)

    def test_split_distribution_aggregates_correctly(self):
        """PO line with split analytic distribution must allocate by %."""
        # Create a second cost center in another analytic account
        analytic_b = self.env["account.analytic.account"].create({
            "name": "AA B Test",
            "company_id": self.company.id,
            "plan_id": self.analytic_plan.id,
        })
        cc_b = self.env["cost.center"].create({
            "name": "CC B",
            "code": "CCBTEST",
            "company_id": self.company.id,
            "analytic_account_id": analytic_b.id,
        })
        plan_b = self.env["budget.plan"].create({
            "name": "Q1 CCB",
            "cost_center_id": cc_b.id,
            "company_id": self.company.id,
            "date_from": "2025-01-01",
            "date_to": "2025-03-31",
        })
        line_b = self.env["budget.plan.line"].create({
            "plan_id": plan_b.id,
            "account_id": self.expense_account.id,
            "planned_amount": 500.0,
        })
        # PO with 60/40 split
        self._create_po(
            1000.0,
            distribution={
                str(self.analytic_account.id): 60.0,
                str(analytic_b.id): 40.0,
            },
            state="purchase",
        )
        self.budget_line.invalidate_recordset()
        line_b.invalidate_recordset()
        self.assertAlmostEqual(self.budget_line.po_committed_amount, 600.0)
        self.assertAlmostEqual(line_b.po_committed_amount, 400.0)

    def test_available_amount_negative_when_over_committed(self):
        """Available should be negative when committed exceeds planned."""
        self._create_po(1500.0, state="purchase")
        self.budget_line.invalidate_recordset()
        self.assertAlmostEqual(self.budget_line.available_amount, -500.0)

    def test_block_on_purchase_blocks_rfq_confirm(self):
        """With block_on_purchase enabled, exceeding PO must fail."""
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("cost_center_budget_control.block_on_purchase", "True")
        ICP.set_param("cost_center_budget_control.mode", "blocking")
        ICP.set_param("cost_center_budget_control.blocking_threshold", "100.0")
        try:
            # Force budget line into approved state for the check
            self.budget_plan.write({"state": "approved"})
            po = self._create_po(2000.0, state="draft")
            with self.assertRaises(UserError):
                po.button_confirm()
        finally:
            # Restore defaults
            ICP.set_param("cost_center_budget_control.block_on_purchase", "False")
            self.budget_plan.write({"state": "draft"})

    def test_block_on_purchase_disabled_allows_overdraft(self):
        """With block_on_purchase disabled, the same PO must succeed."""
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("cost_center_budget_control.block_on_purchase", "False")
        ICP.set_param("cost_center_budget_control.mode", "blocking")
        self.budget_plan.write({"state": "approved"})
        po = self._create_po(2000.0, state="draft")
        # Should not raise
        po.button_confirm()
        self.assertIn(po.state, ("purchase", "done"))

    def test_budget_currency_overridable(self):
        """budget.plan.currency_id must be overridable for multi-currency support."""
        # Pick any 2 active currencies in the system. If the test DB has only
        # 1 active currency, we skip — the assignment behaviour is still
        # covered by the other tests in this file.
        active_currencies = self.env["res.currency"].search([("active", "=", True)])
        if len(active_currencies) < 2:
            self.skipTest("Less than 2 active currencies in the test DB; "
                          "cannot test multi-currency override")
        # Pick a currency that is NOT the company's currency
        company_currency = self.company.currency_id
        other_currency = active_currencies.filtered(lambda c: c != company_currency)[:1]
        if not other_currency:
            self.skipTest("No currency other than the company currency is active")

        # Override the plan currency to the non-company currency
        self.budget_plan.write({"currency_id": other_currency.id})
        self.assertEqual(self.budget_plan.currency_id, other_currency)
        self.assertTrue(self.budget_plan.is_multi_currency)
        # Line's currency should follow the plan
        self.budget_line.invalidate_recordset()
        self.assertEqual(self.budget_line.currency_id, other_currency)
        self.assertEqual(self.budget_line.company_currency_id, company_currency)
        self.assertTrue(self.budget_line.is_multi_currency)
        # Default value path: when creating a new plan without explicit currency,
        # the company currency is used.
        new_plan = self.env["budget.plan"].create({
            "name": "Q1 Default Currency",
            "cost_center_id": self.cost_center.id,
            "company_id": self.company.id,
            "date_from": "2025-04-01",
            "date_to": "2025-06-30",
        })
        self.assertEqual(new_plan.currency_id, company_currency)
        self.assertFalse(new_plan.is_multi_currency)

    def test_inactive_currency_blocked(self):
        """An archived currency must not be assignable to a budget plan.

        Use a dedicated throwaway currency (not USD, not the company
        currency) to avoid hitting the "currency is on a company" guard.
        """
        # Find a currency that is NOT active and NOT the company currency.
        inactive_currencies = self.env["res.currency"].search([
            ("active", "=", False),
            ("id", "!=", self.company.currency_id.id),
        ], limit=1)
        if not inactive_currencies:
            # Create a synthetic inactive currency just for this test
            inactive_currencies = self.env["res.currency"].with_context(
                active_test=False
            ).create({
                "name": "XTS",
                "symbol": "X",
                "active": False,
                "rounding": 0.01,
            })
        with self.assertRaises(Exception):
            self.budget_plan.write({"currency_id": inactive_currencies.id})
