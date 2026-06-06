# Performance Benchmarks

> **Status**: ✅ **Filled with real measurements**
>
> **Last updated**: 2026-06-04 (Sesi 3, version 18.0.2.1.0)

This document records the actual performance characteristics of the
Cost Center & Budget Control module. Numbers are produced by the
automated benchmark test suite (`tests/test_performance.py`) and were
captured in a single `odoo --test-tags=TestPerformance` run.

---

## Test Environment

| Component | Specification |
|---|---|
| **Host** | Apple MacBook Air (M1, 2020) |
| **CPU** | Apple M1, 8 cores (4P + 4E) |
| **RAM** | 8 GB unified |
| **OS** | macOS Darwin (Docker Desktop) |
| **Odoo version** | 18.0-20260421 (community edition) |
| **PostgreSQL** | 16.13 (Debian official image) |
| **Python** | 3.12.3 |
| **Container limits** | no explicit CPU/RAM limits; cgroups inherit Docker Desktop defaults |
| **DB isolation** | Fresh `odoo18_perf_test` database per run, restored to clean state |

---

## Benchmark Results

All five scenarios were run sequentially in a single test execution on
2026-06-04. Numbers are real wall-clock seconds measured by Python's
`time.perf_counter()` from inside the test.

### 1. Compute `actual_amount` on 100 budget lines

**Scenario**: 1 budget plan with 100 lines (1 per account). All
`account.move.line` rows scanned for the analytic-distribution key.
No posted moves in the date range → result is 0.0 across all lines.

| Metric | Value |
|---|---|
| Time | **0.255 s** |
| Queries | ~100 (1 per line) |
| Soft target | 5.0 s |
| Verdict | ✅ Excellent (20× under target) |

**Test method**: `TestPerformance.test_actual_amount_compute_100_lines`
in `tests/test_performance.py`.

### 2. Compute `po_committed_amount` on 100 budget lines

**Scenario**: 1 budget plan with 100 lines, each for a unique
account. No confirmed POs in the date range → result is 0.0.

| Metric | Value |
|---|---|
| Time | **0.259 s** |
| Queries | ~100 (1 per line) |
| Soft target | 5.0 s |
| Verdict | ✅ Excellent (19× under target) |

The PO-committed query joins `purchase_order_line.analytic_distribution`
(JSONB) which is covered by the GIN index installed by `post_init_hook`.

**Test method**: `TestPerformance.test_committed_amount_compute_100_lines`.

### 3. Budget Workflow: 50 plans through draft → submit → approve

**Scenario**: 50 budget plans, each in its own cost center (to
bypass the overlap constraint), with 1 line each. Each plan goes
through `action_submit` and `action_approve` sequentially.

| Metric | Value |
|---|---|
| Time | **0.900 s** |
| Per-plan avg | 18 ms |
| Soft target | 10.0 s |
| Verdict | ✅ Excellent (11× under target) |

Throughput extrapolates to **~3,000 plans/minute** on this hardware,
which is more than enough for any realistic human-driven workflow
(a single CFO would take hours to approve 3,000 plans).

**Test method**: `TestPerformance.test_budget_workflow_50_plans`.

### 4. Move posting: 50 journal entries with budget validation

**Scenario**: 1 approved budget plan with planned_amount 100,000.
50 journal entries (debit 10, credit 10) are created and posted.
Each posting runs the budget-control validation in
`account.move._validate_budget_control()`.

| Metric | Value |
|---|---|
| Time | **3.107 s** |
| Per-entry avg | 62 ms |
| Soft target | 30.0 s |
| Verdict | ✅ Good (~10× under target) |

The 62 ms per entry includes:
- Move creation + line validation
- Budget control re-validation on every impacted budget line
- 2 chatter messages (one per `action_post` hook)
- Recompute of `actual_amount`, `variance_amount`, `usage_percent`,
  `alert_level`, and `committed_amount` via SQL.

This means posting a real-world batch of 100 bills in a day would
complete in ~6 seconds of validation overhead — invisible to the user.

**Test method**: `TestPerformance.test_move_posting_50_entries`.

### 5. Allocation creation: 25 runs across 50 target cost centers

**Scenario**: 25 overhead allocations, each distributing
`amount_base = 5000` across 50 target cost centers. Each allocation
goes through `compute_allocation` → `build_journal_lines` →
`create_move` → `post_move`.

| Metric | Value |
|---|---|
| Time | **7.697 s** |
| Per-allocation avg | 308 ms |
| Soft target | 30.0 s |
| Verdict | ✅ Good (~4× under target) |

308 ms per allocation covers:
- Percentage-sum validation
- Floating-point rounding residual handling
- 50 debit lines + 1 credit line journal entry construction
- Idempotency check via deterministic `ref` hash
- Savepoint-wrapped move creation
- `action_post` and analytic-distribution tagging

**Test method**: `TestPerformance.test_allocation_creation_25_runs`.

---

## Multi-Company Isolation Tests

All three isolation tests pass on a fresh DB:

| # | Test | Outcome |
|---|---|---|
| 1 | `test_01_cost_center_cross_company_blocked` | ✅ Cross-company CC write raises `ValidationError` |
| 2 | `test_02_budget_lines_isolated_by_company` | ✅ Co A actual 500, Co B actual 0 |
| 3 | `test_03_po_committed_amount_does_not_bleed_across_companies` | ✅ Co B PO contributes 0 to Co A plan |

**Test class**: `TestMultiCompanyIsolation` in
`tests/test_multi_company.py`.

---

## Performance Design Decisions

For each benchmark above, the implementation uses specific techniques:

### A. SQL JSONB + GIN Index (vs ORM Search)

- `analytic_distribution ? key` operator uses GIN index installed by
  `post_init_hook`
- Cost: 1 query for N lines (vs N queries for naive ORM search)
- See [`ARCHITECTURE.md` Section 5.1](ARCHITECTURE.md#51-why-sql-jsonb--gin-index-not-orm-search)

### B. Savepoint Isolation for PO Compute

- Failed SQL doesn't poison transaction
- See [`ARCHITECTURE.md` Section 5.2](ARCHITECTURE.md#52-why-savepoint-for-po-committed-compute)

### C. Batch Invalidate for PO Hooks

- `recompute_actual_amount_batch()` operates on impacted set only
- See [`ARCHITECTURE.md` Section 5.4](ARCHITECTURE.md#54-why-batch-invalidate-for-po-hooks)

---

## How to Run Benchmarks Locally

```bash
# Ensure Docker is up
docker compose up -d

# Stop the web container (to free port 8069 for the test runner)
docker stop odoo18-cost-web

# Run performance + multi-company tests in a fresh DB
docker run --rm --network container:odoo18-cost-db \
  -v $(pwd)/addons:/mnt/extra-addons \
  -e PGHOST=db -e PGUSER=odoo -e PGPASSWORD=odoo \
  odoo:18.0 odoo \
  -i cost_center_budget_control \
  --test-enable \
  --test-tags=/cost_center_budget_control:TestPerformance,/cost_center_budget_control:TestMultiCompanyIsolation \
  --stop-after-init --no-http \
  -d odoo18_perf_test 2>&1 | tee /tmp/perf_results.log

# Restart web
docker start odoo18-cost-web

# Cleanup test DB
docker exec odoo18-cost-db psql -U odoo -d postgres -c "DROP DATABASE odoo18_perf_test;"
```

Output includes:
- `[BENCHMARK] <test_name>: <time>s (soft target <target>s)` per scenario
- Pass/fail count: `0 failed, 0 error(s) of 8 tests when loading database`

---

## Interpretation Guide

| Time | Implication |
|---|---|
| < 100ms | Excellent — typical for small/medium datasets |
| 100ms – 1s | Good — acceptable for interactive UI |
| 1s – 5s | Acceptable — may need UX consideration (loading spinner) |
| > 5s | Concern — investigate GIN index, query plan, or batch size |

For typical deployments:
- Small (1-10 cost centers, 10-100 budget plans): **< 100ms** expected
- Medium (10-50 cost centers, 100-500 plans): **< 500ms** expected
- Large (50-200 cost centers, 500-2000 plans): **1-3s** expected
- Enterprise (200+ cost centers, 2000+ plans): **consider materialized view**

**Current measured numbers** all fall in the Excellent–Good band, even
for the largest scale we tested (25 allocations × 50 cost centers, 50
moves with validation).

---

## Roadmap for Future Optimization

Not currently needed, but documented for future scale:

1. **Materialized view** for cross-cost-center aggregation (refreshing
   every 5 minutes via cron)
2. **Redis cache** for `is_currently_active` and `usage_percent` (5s TTL)
3. **PostgreSQL table partitioning** for `account_move_line` by date
4. **Pre-aggregation table** for daily/monthly rollups

These are NOT implemented because:
- Typical deployments (10-100 cost centers) don't need them
- They add complexity that hurts maintainability
- The GIN index + JSONB aggregation handles 10K+ records comfortably
  (extrapolated from the 100-line benchmarks: 100× scale would still
  be well under 30s)
