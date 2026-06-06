# -*- coding: utf-8 -*-
"""Multi-company isolation tests.

Verifies that budgets, cost centers, and PO commitments in one company
are strictly isolated from another company. The module declares
``_check_company_auto = True`` on its models, but this test exercises the
boundary end-to-end through the user-facing workflow.
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, UserError


class TestMultiCompanyIsolation(TransactionCase):
    """Multi-company data isolation checks."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # Two independent companies
        cls.company_a = env["res.company"].create({"name": "MCI A"})
        cls.company_b = env["res.company"].create({"name": "MCI B"})

        cls.analytic_plan = env["account.analytic.plan"].search([], limit=1)
        if not cls.analytic_plan:
            cls.analytic_plan = env["account.analytic.plan"].create({
                "name": "MCI Plan",
            })
        cls.analytic_a = env["account.analytic.account"].create({
            "name": "AA A", "company_id": cls.company_a.id,
            "plan_id": cls.analytic_plan.id,
        })
        cls.analytic_b = env["account.analytic.account"].create({
            "name": "AA B", "company_id": cls.company_b.id,
            "plan_id": cls.analytic_plan.id,
        })

        cls.cc_a = env["cost.center"].create({
            "name": "MCI CC A", "code": "MCI-A",
            "company_id": cls.company_a.id,
            "analytic_account_id": cls.analytic_a.id,
        })
        cls.cc_b = env["cost.center"].create({
            "name": "MCI CC B", "code": "MCI-B",
            "company_id": cls.company_b.id,
            "analytic_account_id": cls.analytic_b.id,
        })

        cls.account_a = env["account.account"].create({
            "name": "MCI Account A", "code": "MCIACCA",
            "account_type": "expense",
            "company_ids": [(6, 0, [cls.company_a.id])],
        })
        cls.account_b = env["account.account"].create({
            "name": "MCI Account B", "code": "MCIACCB",
            "account_type": "expense",
            "company_ids": [(6, 0, [cls.company_b.id])],
        })

        cls.journal_a = env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company_a.id)], limit=1
        )
        if not cls.journal_a:
            cls.journal_a = env["account.journal"].create({
                "name": "MCI Journal A", "code": "MCIA",
                "type": "general", "company_id": cls.company_a.id,
            })
        cls.journal_b = env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company_b.id)], limit=1
        )
        if not cls.journal_b:
            cls.journal_b = env["account.journal"].create({
                "name": "MCI Journal B", "code": "MCIB",
                "type": "general", "company_id": cls.company_b.id,
            })

    def test_01_cost_center_cross_company_blocked(self):
        """A cost center from Company A cannot be assigned to a Company B plan.

        The ``cost_center_id`` field has ``check_company=True`` so a direct
        write/copy must raise a ``ValidationError``.
        """
        plan_b = self.env["budget.plan"].create({
            "name": "Plan B",
            "company_id": self.company_b.id,
            "cost_center_id": self.cc_b.id,
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
        })
        # Attempt to assign the Company A cost center to a Company B plan.
        with self.assertRaises(Exception):
            plan_b.write({"cost_center_id": self.cc_a.id})
        # Confirm state unchanged
        self.assertEqual(plan_b.cost_center_id, self.cc_b)

    def test_02_budget_lines_isolated_by_company(self):
        """Actual amounts in Company A are NOT visible to Company B's plan.

        Even though both plans share the same account type, the SQL
        aggregation must filter by ``company_id``. Otherwise a holding
        company's books would bleed across subsidiaries.
        """
        plan_a = self.env["budget.plan"].create({
            "name": "Plan A",
            "company_id": self.company_a.id,
            "cost_center_id": self.cc_a.id,
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
            "line_ids": [(0, 0, {
                "account_id": self.account_a.id,
                "planned_amount": 1000.0,
            })],
        })
        plan_b = self.env["budget.plan"].create({
            "name": "Plan B",
            "company_id": self.company_b.id,
            "cost_center_id": self.cc_b.id,
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
            "line_ids": [(0, 0, {
                "account_id": self.account_b.id,
                "planned_amount": 2000.0,
            })],
        })
        # Post a journal entry in Company A
        move_a = self.env["account.move"].create({
            "journal_id": self.journal_a.id,
            "date": "2025-06-15",
            "company_id": self.company_a.id,
            "line_ids": [
                (0, 0, {
                    "account_id": self.account_a.id,
                    "debit": 500.0,
                    "credit": 0.0,
                    "analytic_distribution": {str(self.analytic_a.id): 100.0},
                }),
                (0, 0, {
                    "account_id": self.account_a.id,
                    "debit": 0.0,
                    "credit": 500.0,
                }),
            ],
        })
        move_a.action_post()
        # Force compute
        plan_a.line_ids.invalidate_recordset()
        plan_a.line_ids._compute_actual_amount()
        plan_b.line_ids.invalidate_recordset()
        plan_b.line_ids._compute_actual_amount()
        # Company A's line sees 500 actual, Company B's line is 0
        self.assertAlmostEqual(plan_a.line_ids.actual_amount, 500.0)
        self.assertAlmostEqual(plan_b.line_ids.actual_amount, 0.0)

    def test_03_po_committed_amount_does_not_bleed_across_companies(self):
        """A PO confirmed in Company B does NOT commit against Company A's budget.

        The committed-amount SQL filters by ``o.company_id``. Without this
        isolation, a multi-company group would see cross-company false
        positives in the committed column.
        """
        plan_a = self.env["budget.plan"].create({
            "name": "Plan A PO",
            "company_id": self.company_a.id,
            "cost_center_id": self.cc_a.id,
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
            "line_ids": [(0, 0, {
                "account_id": self.account_a.id,
                "planned_amount": 5000.0,
            })],
        })
        product = self.env["product.product"].create({
            "name": "MCI Product", "type": "service", "standard_price": 100.0,
        })
        vendor = self.env["res.partner"].create({"name": "MCI Vendor"})

        # PO in Company B, hitting the same analytic-distribution key by accident
        # is not possible because the AA ID differs; but to be thorough we test
        # the company filter directly via a same-AA-distributed PO in Company B
        po_b = self.env["purchase.order"].create({
            "partner_id": vendor.id,
            "company_id": self.company_b.id,
            "date_order": "2025-06-15",
        })
        po_b.write({"order_line": [(0, 0, {
            "product_id": product.id,
            "name": product.name,
            "product_qty": 1,
            "price_unit": 2000.0,
            "analytic_distribution": {str(self.analytic_a.id): 100.0},
        })]})
        po_b.button_confirm()
        # Force compute on Plan A
        plan_a.line_ids.invalidate_recordset()
        plan_a.line_ids._compute_committed_amount()
        # Plan A's committed amount must be 0 — Company B's PO is filtered out
        self.assertAlmostEqual(plan_a.line_ids.po_committed_amount, 0.0)
        self.assertAlmostEqual(plan_a.line_ids.committed_amount, 0.0)
        self.assertAlmostEqual(plan_a.line_ids.available_amount, 5000.0)
