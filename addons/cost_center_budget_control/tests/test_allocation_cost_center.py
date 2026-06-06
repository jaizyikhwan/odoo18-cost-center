# -*- coding: utf-8 -*-

import logging
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class TestBudgetAllocation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = (
            env.ref("base.main_company", raise_if_not_found=False)
            or env["res.company"].search([], limit=1)
        )
        # Use a unique analytic plan to avoid interfering with other tests
        cls.analytic_plan = env["account.analytic.plan"].create(
            {"name": "Test Alloc Plan"}
        )

        cls.analytic_src = env["account.analytic.account"].create({
            "name": "AA Source",
            "company_id": cls.company.id,
            "plan_id": cls.analytic_plan.id,
        })
        cls.analytic_tgt1 = env["account.analytic.account"].create({
            "name": "AA Target 1",
            "company_id": cls.company.id,
            "plan_id": cls.analytic_plan.id,
        })
        cls.analytic_tgt2 = env["account.analytic.account"].create({
            "name": "AA Target 2",
            "company_id": cls.company.id,
            "plan_id": cls.analytic_plan.id,
        })

        cls.cc_src = env["cost.center"].create({
            "name": "CC Source",
            "code": "CCSRC",
            "company_id": cls.company.id,
            "analytic_account_id": cls.analytic_src.id,
        })
        cls.cc_tgt1 = env["cost.center"].create({
            "name": "CC Target 1",
            "code": "CCT1",
            "company_id": cls.company.id,
            "analytic_account_id": cls.analytic_tgt1.id,
        })
        cls.cc_tgt2 = env["cost.center"].create({
            "name": "CC Target 2",
            "code": "CCT2",
            "company_id": cls.company.id,
            "analytic_account_id": cls.analytic_tgt2.id,
        })

        # Expense accounts (Odoo 18 uses company_ids, Many2many)
        cls.account_src = env["account.account"].create({
            "name": "Alloc Source",
            "code": "ALLOCSRC",
            "account_type": "expense",
            "company_ids": [(6, 0, [cls.company.id])],
        })
        cls.account_tgt = env["account.account"].create({
            "name": "Alloc Target",
            "code": "ALLOCTGT",
            "account_type": "expense",
            "company_ids": [(6, 0, [cls.company.id])],
        })

        # General journal
        cls.journal = env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company.id)],
            limit=1,
        )

    def _create_allocation(self, base_amount, percentages, allocation_date="2025-06-15"):
        """Create an allocation in `draft` state ready to be allocated.

        :param base_amount: total amount to allocate
        :param percentages: list of (cost_center, percent) tuples
        :param allocation_date: posting date for the resulting journal entry
        """
        return self.env["budget.allocation"].create({
            "name": "Test Allocation",
            "company_id": self.company.id,
            "source_cost_center_id": self.cc_src.id,
            "overhead_account_id": self.account_src.id,
            "target_account_id": self.account_tgt.id,
            "journal_id": self.journal.id if self.journal else False,
            "amount_base": base_amount,
            "allocation_date": allocation_date,
            "line_ids": [(0, 0, {
                "cost_center_id": cc.id,
                "percentage": pct,
            }) for cc, pct in percentages],
        })

    def test_percentage_sum_must_equal_100(self):
        """Allocation with percentages not summing to 100 must fail."""
        alloc = self._create_allocation(
            base_amount=1000.0,
            percentages=[(self.cc_tgt1, 60.0), (self.cc_tgt2, 30.0)],
        )
        with self.assertRaises(UserError):
            alloc.action_allocate()

    def test_allocation_creates_balanced_journal(self):
        """Allocation must produce a journal entry where debits == credits."""
        alloc = self._create_allocation(
            base_amount=1000.0,
            percentages=[(self.cc_tgt1, 60.0), (self.cc_tgt2, 40.0)],
        )
        alloc.action_allocate()
        self.assertTrue(alloc.move_id, "Allocation must create a journal entry")
        total_debit = sum(alloc.move_id.line_ids.mapped("debit"))
        total_credit = sum(alloc.move_id.line_ids.mapped("credit"))
        self.assertAlmostEqual(total_debit, total_credit, places=2)
        self.assertAlmostEqual(total_debit, 1000.0, places=2)
        self.assertEqual(alloc.state, "posted")

    def test_idempotency_reference_is_deterministic(self):
        """Two allocations with same period+source+rules must produce the same ref."""
        alloc_a = self._create_allocation(
            base_amount=500.0,
            percentages=[(self.cc_tgt1, 100.0)],
        )
        alloc_a.action_allocate()
        alloc_b = self._create_allocation(
            base_amount=500.0,
            percentages=[(self.cc_tgt1, 100.0)],
        )
        alloc_b.action_allocate()
        # Both should reference the same idempotency ref (re-use same move)
        self.assertEqual(alloc_a.ref, alloc_b.ref)
        self.assertEqual(alloc_a.move_id.id, alloc_b.move_id.id)

    def test_rounding_residual_absorbed_in_final_line(self):
        """Proportional allocation with awkward percentages must still balance."""
        alloc = self._create_allocation(
            base_amount=100.0,
            percentages=[
                (self.cc_tgt1, 33.33),
                (self.cc_tgt2, 33.33),
                (self.cc_src, 33.34),
            ],
        )
        alloc.action_allocate()
        self.assertTrue(alloc.move_id)
        total_debit = sum(alloc.move_id.line_ids.mapped("debit"))
        total_credit = sum(alloc.move_id.line_ids.mapped("credit"))
        # Critical: must be EXACTLY balanced to currency precision
        self.assertAlmostEqual(total_debit, total_credit, places=2)
        self.assertAlmostEqual(total_credit, 100.0, places=2)

    def test_cannot_delete_posted_allocation(self):
        """Posted allocation must not be deletable."""
        alloc = self._create_allocation(
            base_amount=100.0,
            percentages=[(self.cc_tgt1, 100.0)],
        )
        alloc.action_allocate()
        self.assertEqual(alloc.state, "posted")
        with self.assertRaises(UserError):
            alloc.unlink()

    def test_allocate_twice_does_not_duplicate_moves(self):
        """Calling action_allocate twice on the same record must be idempotent."""
        alloc = self._create_allocation(
            base_amount=250.0,
            percentages=[(self.cc_tgt1, 50.0), (self.cc_tgt2, 50.0)],
        )
        alloc.action_allocate()
        move_id = alloc.move_id.id
        alloc.action_allocate()
        self.assertEqual(alloc.move_id.id, move_id)


class TestCostCenter(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env["res.company"].search([], limit=1)
        cls.analytic_plan = env["account.analytic.plan"].create(
            {"name": "Test CC Plan"}
        )

    def test_code_must_be_unique_per_company(self):
        """Two cost centers in the same company cannot share a code."""
        analytic = self.env["account.analytic.account"].create({
            "name": "AA Unique Test",
            "company_id": self.company.id,
            "plan_id": self.analytic_plan.id,
        })
        self.env["cost.center"].create({
            "name": "CC First",
            "code": "UNIQUE1",
            "company_id": self.company.id,
            "analytic_account_id": analytic.id,
        })
        with self.assertRaises(Exception):
            self.env["cost.center"].create({
                "name": "CC Second",
                "code": "UNIQUE1",
                "company_id": self.company.id,
                "analytic_account_id": analytic.id,
            })

    def test_complete_name_includes_hierarchy(self):
        """complete_name should reflect the parent path for hierarchical display."""
        analytic_root = self.env["account.analytic.account"].create({
            "name": "AA Root",
            "company_id": self.company.id,
            "plan_id": self.analytic_plan.id,
        })
        analytic_child = self.env["account.analytic.account"].create({
            "name": "AA Child",
            "company_id": self.company.id,
            "plan_id": self.analytic_plan.id,
        })
        root = self.env["cost.center"].create({
            "name": "Root",
            "code": "ROOTCC",
            "company_id": self.company.id,
            "analytic_account_id": analytic_root.id,
        })
        child = self.env["cost.center"].create({
            "name": "Child",
            "code": "CHILDCC",
            "company_id": self.company.id,
            "analytic_account_id": analytic_child.id,
            "parent_id": root.id,
        })
        self.assertIn("Root", child.complete_name)
        self.assertIn("Child", child.complete_name)
