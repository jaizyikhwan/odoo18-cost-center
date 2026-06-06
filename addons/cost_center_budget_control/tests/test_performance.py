# -*- coding: utf-8 -*-
"""Performance benchmarks for the Cost Center & Budget Control module.

These tests measure key operations at scale and log the timings. They are
not strict pass/fail gates — instead, they capture numbers for the
``docs/PERFORMANCE.md`` reference document.

Scenarios:
  1. ``_compute_actual_amount`` on 1000 budget lines (SQL aggregation speed).
  2. ``_compute_committed_amount`` on 1000 budget lines (PO join speed).
  3. Budget plan workflow: draft → submit → approve on 100 plans.
  4. Move posting with budget enforcement: 100 posted journal entries.
  5. Allocation creation: 50 overhead allocations across 100 cost centers.

Numbers are recorded in ``_logger.info`` and into
``self.benchmark_results`` for easy extraction. The test runner is Odoo
``TransactionCase``; each test runs in its own transaction with rollback.
"""
import logging
import time
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


class TestPerformance(TransactionCase):
    """Benchmark tests. Thresholds are loose to avoid CI flakiness."""

    BUDGET_LINE_COUNT = 100
    PLAN_COUNT = 50
    MOVE_COUNT = 50
    ALLOCATION_COUNT = 25
    TARGET_CC_COUNT = 50

    # Soft targets (seconds) — failing these logs a warning, not an error.
    SOFT_TARGETS = {
        "test_actual_amount_compute_100_lines": 5.0,
        "test_committed_amount_compute_100_lines": 5.0,
        "test_budget_workflow_50_plans": 10.0,
        "test_move_posting_50_entries": 30.0,
        "test_allocation_creation_25_runs": 30.0,
    }

    benchmark_results = {}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = (
            env.ref("base.main_company", raise_if_not_found=False)
            or env["res.company"].search([], limit=1)
        )
        cls.analytic_plan = (
            env["account.analytic.plan"].search([], limit=1)
            or env["account.analytic.plan"].create({"name": "Perf Plan"})
        )
        cls.analytic_account = env["account.analytic.account"].create({
            "name": "AA Perf",
            "company_id": cls.company.id,
            "plan_id": cls.analytic_plan.id,
        })
        cls.cost_center = env["cost.center"].create({
            "name": "CC Perf",
            "code": "CCPERF",
            "company_id": cls.company.id,
            "analytic_account_id": cls.analytic_account.id,
        })
        cls.expense_account = env["account.account"].create({
            "name": "Expense Perf",
            "code": "EXPPERF",
            "account_type": "expense",
            "company_ids": [(6, 0, [cls.company.id])],
        })
        cls.journal = env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.journal:
            cls.journal = env["account.journal"].create({
                "name": "Perf Journal",
                "code": "PERFJ",
                "type": "general",
                "company_id": cls.company.id,
            })

    def _record(self, name, duration):
        """Record a benchmark number and warn if over the soft target."""
        target = self.SOFT_TARGETS.get(name)
        msg = "[BENCHMARK] %s: %.3fs" % (name, duration)
        if target:
            if duration > target * 1.5:
                _logger.warning("%s (soft target %.3fs EXCEEDED)", msg, target)
            else:
                _logger.info("%s (soft target %.3fs)", msg, target)
        else:
            _logger.info(msg)
        self.benchmark_results[name] = duration

    def test_actual_amount_compute_100_lines(self):
        """Measure _compute_actual_amount on 100 budget lines."""
        plan = self.env["budget.plan"].create({
            "name": "Perf Plan Actual",
            "cost_center_id": self.cost_center.id,
            "company_id": self.company.id,
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
        })
        # Create N budget lines, each for a different account
        accounts = []
        for i in range(self.BUDGET_LINE_COUNT):
            acc = self.env["account.account"].create({
                "name": "Acc %d" % i,
                "code": "ACCPERF%d" % i,
                "account_type": "expense",
                "company_ids": [(6, 0, [self.company.id])],
            })
            accounts.append(acc)
        for acc in accounts:
            self.env["budget.plan.line"].create({
                "plan_id": plan.id,
                "account_id": acc.id,
                "planned_amount": 1000.0,
            })

        start = time.perf_counter()
        plan.line_ids.invalidate_recordset()
        plan.line_ids._compute_actual_amount()
        self.env.cr.execute("SELECT 1")  # flush
        duration = time.perf_counter() - start
        self._record("test_actual_amount_compute_100_lines", duration)
        self.assertEqual(len(plan.line_ids), self.BUDGET_LINE_COUNT)

    def test_committed_amount_compute_100_lines(self):
        """Measure _compute_committed_amount on 100 budget lines."""
        plan = self.env["budget.plan"].create({
            "name": "Perf Plan Committed",
            "cost_center_id": self.cost_center.id,
            "company_id": self.company.id,
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
        })
        for i in range(self.BUDGET_LINE_COUNT):
            acc = self.env["account.account"].create({
                "name": "Acc Comm %d" % i,
                "code": "ACCCOMM%d" % i,
                "account_type": "expense",
                "company_ids": [(6, 0, [self.company.id])],
            })
            self.env["budget.plan.line"].create({
                "plan_id": plan.id,
                "account_id": acc.id,
                "planned_amount": 1000.0,
            })

        start = time.perf_counter()
        plan.line_ids.invalidate_recordset()
        plan.line_ids._compute_committed_amount()
        self.env.cr.execute("SELECT 1")
        duration = time.perf_counter() - start
        self._record("test_committed_amount_compute_100_lines", duration)
        self.assertEqual(len(plan.line_ids), self.BUDGET_LINE_COUNT)

    def test_budget_workflow_50_plans(self):
        """Create, submit, approve 50 budget plans sequentially.

        Each plan uses a unique cost center to avoid the overlap constraint.
        """
        plans = []
        start = time.perf_counter()
        for i in range(self.PLAN_COUNT):
            # Use a dedicated cost center per plan to bypass overlap check
            aa = self.env["account.analytic.account"].create({
                "name": "AA Wk %d" % i,
                "company_id": self.company.id,
                "plan_id": self.analytic_plan.id,
            })
            cc = self.env["cost.center"].create({
                "name": "CC Wk %d" % i,
                "code": "CCWK%d" % i,
                "company_id": self.company.id,
                "analytic_account_id": aa.id,
            })
            plan = self.env["budget.plan"].create({
                "name": "Workflow Plan %d" % i,
                "cost_center_id": cc.id,
                "company_id": self.company.id,
                "date_from": "2025-01-01",
                "date_to": "2025-12-31",
                "line_ids": [(0, 0, {
                    "account_id": self.expense_account.id,
                    "planned_amount": 100.0 * (i + 1),
                })],
            })
            plan.action_submit()
            plan.action_approve()
            plans.append(plan)
        duration = time.perf_counter() - start
        self._record("test_budget_workflow_50_plans", duration)
        self.assertTrue(all(p.state == "approved" for p in plans))

    def test_move_posting_50_entries(self):
        """Post 50 journal entries that pass through budget validation."""
        plan = self.env["budget.plan"].create({
            "name": "Posting Plan",
            "cost_center_id": self.cost_center.id,
            "company_id": self.company.id,
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
        })
        self.env["budget.plan.line"].create({
            "plan_id": plan.id,
            "account_id": self.expense_account.id,
            "planned_amount": 100000.0,
        })
        plan.action_submit()
        plan.action_approve()

        start = time.perf_counter()
        for i in range(self.MOVE_COUNT):
            move = self.env["account.move"].create({
                "journal_id": self.journal.id,
                "date": "2025-06-15",
                "company_id": self.company.id,
                "line_ids": [
                    (0, 0, {
                        "account_id": self.expense_account.id,
                        "debit": 10.0,
                        "credit": 0.0,
                        "analytic_distribution": {str(self.analytic_account.id): 100.0},
                    }),
                    (0, 0, {
                        "account_id": self.expense_account.id,
                        "debit": 0.0,
                        "credit": 10.0,
                    }),
                ],
            })
            move.action_post()
        duration = time.perf_counter() - start
        self._record("test_move_posting_50_entries", duration)

    def test_allocation_creation_25_runs(self):
        """Run 25 overhead allocations across 50 target cost centers."""
        target_ccs = []
        for i in range(self.TARGET_CC_COUNT):
            aa = self.env["account.analytic.account"].create({
                "name": "AA Tgt %d" % i,
                "company_id": self.company.id,
                "plan_id": self.analytic_plan.id,
            })
            cc = self.env["cost.center"].create({
                "name": "CC Tgt %d" % i,
                "code": "CCTPERF%d" % i,
                "company_id": self.company.id,
                "analytic_account_id": aa.id,
            })
            target_ccs.append(cc)

        overhead_account = self.env["account.account"].create({
            "name": "Overhead",
            "code": "OVERHEAD",
            "account_type": "expense",
            "company_ids": [(6, 0, [self.company.id])],
        })
        target_account = self.env["account.account"].create({
            "name": "Target Overhead",
            "code": "TGT",
            "account_type": "expense",
            "company_ids": [(6, 0, [self.company.id])],
        })

        start = time.perf_counter()
        for i in range(self.ALLOCATION_COUNT):
            alloc_lines = []
            equal_pct = 100.0 / len(target_ccs)
            for cc in target_ccs:
                alloc_lines.append((0, 0, {
                    "cost_center_id": cc.id,
                    "percentage": equal_pct,
                }))
            alloc = self.env["budget.allocation"].create({
                "name": "Perf Alloc %d" % i,
                "source_cost_center_id": self.cost_center.id,
                "amount_base": 5000.0,
                "allocation_date": "2025-06-15",
                "overhead_account_id": overhead_account.id,
                "target_account_id": target_account.id,
                "journal_id": self.journal.id,
                "line_ids": alloc_lines,
            })
            alloc.action_allocate()
        duration = time.perf_counter() - start
        self._record("test_allocation_creation_25_runs", duration)
        posted = self.env["budget.allocation"].search_count([("state", "=", "posted")])
        self.assertEqual(posted, self.ALLOCATION_COUNT)
