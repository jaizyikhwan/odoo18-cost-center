# -*- coding: utf-8 -*-
"""Tests for Budget Revision (Revise) feature.

Validates:
- Only approved budgets can be revised
- Original transitions to 'revised' state
- New revision is created in 'approved' state with ' (Rev N)' suffix
- All budget lines are copied to the new revision
- parent_revision_id correctly links the chain
- revision_number increments correctly
- revised budgets are immutable (write/unlink blocked)
- is_latest_revision computes correctly
- Cancelled / closed budgets cannot be revised
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestBudgetRevision(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = (
            env.ref("base.main_company", raise_if_not_found=False)
            or env["res.company"].search([], limit=1)
        )
        cls.analytic_plan = env["account.analytic.plan"].create(
            {"name": "Test Revision Plan"}
        )
        cls.analytic_account = env["account.analytic.account"].create({
            "name": "AA Revision Test",
            "company_id": cls.company.id,
            "plan_id": cls.analytic_plan.id,
        })
        cls.cost_center = env["cost.center"].create({
            "name": "CC Revision",
            "code": "CCREVISION",
            "company_id": cls.company.id,
            "analytic_account_id": cls.analytic_account.id,
        })
        cls.expense_account = env["account.account"].create({
            "name": "Expense Revision",
            "code": "EXPREV",
            "account_type": "expense",
            "company_ids": [(6, 0, [cls.company.id])],
        })

    def _create_approved_plan(self, name="Q1 Rev", planned=1000.0):
        plan = self.env["budget.plan"].create({
            "name": name,
            "cost_center_id": self.cost_center.id,
            "company_id": self.company.id,
            "date_from": "2025-01-01",
            "date_to": "2025-03-31",
        })
        self.env["budget.plan.line"].create({
            "plan_id": plan.id,
            "account_id": self.expense_account.id,
            "planned_amount": planned,
        })
        plan.write({"state": "approved"})
        return plan

    def test_revise_only_allowed_from_approved_state(self):
        plan = self.env["budget.plan"].create({
            "name": "Draft Plan",
            "cost_center_id": self.cost_center.id,
            "company_id": self.company.id,
            "date_from": "2025-01-01",
            "date_to": "2025-03-31",
            "state": "draft",
        })
        with self.assertRaises(UserError):
            plan.action_revise()

    def test_revise_creates_new_approved_budget_with_rev_suffix(self):
        plan = self._create_approved_plan(name="Q1 Marketing")
        result = plan.action_revise()
        new_plan = self.env["budget.plan"].browse(result["res_id"])
        self.assertEqual(new_plan.state, "approved")
        self.assertIn("(Rev 2)", new_plan.name)
        self.assertEqual(new_plan.revision_number, 2)

    def test_revise_marks_original_as_revised_state(self):
        plan = self._create_approved_plan()
        plan.action_revise()
        self.assertEqual(plan.state, "revised")

    def test_revise_copies_all_budget_lines(self):
        plan = self._create_approved_plan(planned=2500.0)
        result = plan.action_revise()
        new_plan = self.env["budget.plan"].browse(result["res_id"])
        self.assertEqual(len(new_plan.line_ids), len(plan.line_ids))
        self.assertEqual(
            new_plan.line_ids.planned_amount,
            plan.line_ids.planned_amount,
        )
        self.assertEqual(
            new_plan.line_ids.account_id,
            plan.line_ids.account_id,
        )

    def test_revise_increments_revision_number_through_chain(self):
        plan_v1 = self._create_approved_plan(name="Annual 2025")
        plan_v2 = self.env["budget.plan"].browse(
            plan_v1.action_revise()["res_id"]
        )
        plan_v3 = self.env["budget.plan"].browse(
            plan_v2.action_revise()["res_id"]
        )
        self.assertEqual(plan_v1.revision_number, 1)
        self.assertEqual(plan_v2.revision_number, 2)
        self.assertEqual(plan_v3.revision_number, 3)
        self.assertIn("(Rev 2)", plan_v2.name)
        self.assertIn("(Rev 3)", plan_v3.name)

    def test_revise_links_via_parent_revision_id(self):
        plan = self._create_approved_plan()
        new_plan = self.env["budget.plan"].browse(
            plan.action_revise()["res_id"]
        )
        self.assertEqual(new_plan.parent_revision_id, plan)
        self.assertIn(new_plan, plan.child_revision_ids)

    def test_revise_blocked_from_cancelled_state(self):
        plan = self._create_approved_plan()
        plan.write({"state": "cancelled"})
        with self.assertRaises(UserError):
            plan.action_revise()

    def test_revise_blocked_from_revised_state(self):
        plan = self._create_approved_plan()
        new_plan = self.env["budget.plan"].browse(
            plan.action_revise()["res_id"]
        )
        # The new revision is 'approved' and can be revised again
        self.assertEqual(new_plan.state, "approved")
        # But the original (now 'revised') cannot be re-revised
        with self.assertRaises(UserError):
            plan.action_revise()

    def test_revised_budget_is_immutable(self):
        plan = self._create_approved_plan()
        plan.action_revise()
        # plan is now in 'revised' state -> cannot modify fields
        with self.assertRaises(UserError):
            plan.write({"name": "Should fail"})

    def test_is_latest_revision_computed_correctly(self):
        plan_v1 = self._create_approved_plan()
        plan_v2 = self.env["budget.plan"].browse(
            plan_v1.action_revise()["res_id"]
        )
        plan_v1.invalidate_recordset()
        plan_v2.invalidate_recordset()
        # v1 is no longer the latest (v2 superseded it)
        self.assertFalse(plan_v1.is_latest_revision)
        # v2 is the latest
        self.assertTrue(plan_v2.is_latest_revision)

    def test_revise_preserves_company_cost_center_dates(self):
        plan = self._create_approved_plan()
        new_plan = self.env["budget.plan"].browse(
            plan.action_revise()["res_id"]
        )
        self.assertEqual(new_plan.company_id, plan.company_id)
        self.assertEqual(new_plan.cost_center_id, plan.cost_center_id)
        self.assertEqual(new_plan.date_from, plan.date_from)
        self.assertEqual(new_plan.date_to, plan.date_to)

    def test_search_filter_latest_revision_only(self):
        plan_v1 = self._create_approved_plan()
        plan_v2 = self.env["budget.plan"].browse(
            plan_v1.action_revise()["res_id"]
        )
        latest = self.env["budget.plan"].search([
            ("is_latest_revision", "=", True),
            ("cost_center_id", "=", self.cost_center.id),
        ])
        self.assertIn(plan_v2, latest)
        self.assertNotIn(plan_v1, latest)
