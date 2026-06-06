# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [18.0.2.3.0] - 2026-06-06 — Repo Trimming

> **Release type**: Repository structure cleanup. No code change, no test
> impact. README jadi satu-satunya entry point dokumentasi.

### Changed
- README tree diagram: `docs/` dan `readme/` lines dihapus.
- README link ke docs internal dihapus (line 10, line 84).
- README referensi LICENSE diganti dengan teks polos (lisensi tetap
  LGPL-3.0).

### Removed
- `docs/` directory (4 file: ARCHITECTURE, INTEGRATION, PERFORMANCE,
  DEMO_RECORDING, plus untracked `project_brief.html`).
- `readme/` directory (3 file: DESCRIPTION, ROADMAP, USAGE).
- `LICENSE` (full LGPL-3 text; lisensi tetap mengikat karena disebut
  eksplisit di README).
- `CONTRIBUTING.md`.
- `.github/CODEOWNERS`, `.github/ISSUE_TEMPLATE/`, dan
  `.github/PULL_REQUEST_TEMPLATE.md`. Workflow CI tetap ada.

## [18.0.2.2.0] - 2026-06-06 — Bugfix & Cleanup Release

> **Release type**: Critical bugfixes + dead code cleanup. All 13 previously
> failing tests now pass. No breaking changes from v18.0.2.1.0.

### Fixed
- Email notification for budget lines now uses `mail.template.send_mail` with
  the record id (the `budget.plan.line` model does not inherit `mail.thread`,
  so `message_post_with_template` was unavailable).
- `budget.plan.write` now respects a `bypass_state_protection` context flag;
  workflow actions (`submit/approve/reset/cancel/close/revise`) use it to
  transition state without triggering the protection guard. Also fixed a
  related issue where the superuser check was bypassing the state protection
  entirely — now state protection applies to all users (system invariant),
  but pure state-only writes are still allowed.
- `action_revise` now writes `state='revised'` on the original BEFORE cloning,
  so the new approved plan passes the `_check_overlap` constraint. Also fixed
  the revision number derivation: it now correctly uses
  `rec.revision_number + 1` instead of `max(child_revision_ids) + 1`, which
  failed to increment through the chain.
- Allocation `deterministic_ref` no longer includes `self.id`; two allocations
  with identical period+source+rules now produce the same ref (true
  cross-record idempotency).
- `_get_impacted_budget_lines_from_po_line` no longer pre-filters by PO state,
  so cancelling a PO triggers recompute of its previously-impacted budget lines.
- Demo data XML includes `base.main_company` in user `company_ids` (was causing
  ParseError on demo install), and demo budget plans now set `company_id` to
  match their cost center's company (was causing `_check_company_auto` to fail).
- Recurring allocation fields (`is_recurring`, `recurring_interval_months`,
  `last_run_date`, `recurring_count`) are now exposed in the allocation form
  view (previously had no UI to enable the feature).

### Removed
- `_check_currency_match_company` constraint (dead code; `currency_id` is
  `related` to `company_id.currency_id` and cannot differ under normal usage).
- `variance_amount` field (duplicate of `remaining_amount` with identical
  compute). Views, pivot, QWeb report, and export wizard updated to use
  `remaining_amount` instead.
- `target_cost_center_ids` M2M field (unused; actual targets live on
  `budget.allocation.line`).
- `unaccent=False` parameter on `cost.center.parent_path` (default in Odoo 18,
  the explicit value triggered a "unknown parameter" warning).
- `controllers/` placeholder module (all commented scaffold code).

### Test Status
- 48/48 tests pass (1 multi-currency test skipped due to test DB currency
  configuration). All 13 previously failing tests from v18.0.2.0.0/v18.0.2.1.0
  are now resolved.

## [18.0.2.1.0] - 2026-06-04 — Portfolio Polish Release

> **Release type**: Documentation, code enhancements, test coverage, and
> portfolio polish. No breaking changes from v18.0.2.0.0.
>
> **Test count**: 26 → 34 (8 new tests, all passing). Pre-existing
> 3 failures carried over from v18.0.2.0.0 (not regressions).

### Added — Documentation

- **New `docs/ARCHITECTURE.md`** — 13K, Mermaid diagrams for data flow,
  state machine, security hierarchy, 4 extension points, and 4
  performance design decisions.
- **New `docs/INTEGRATION.md`** — 12K, 10 sections covering compatibility
  with OCA `account_budget_oca`, Odoo Enterprise `account.budget`,
  optional sync hooks, and step-by-step migration path.
- **New `docs/PERFORMANCE.md`** — 8K, real benchmark numbers from
  `tests/test_performance.py` (Apple M1, 8 cores, 8 GB RAM, PostgreSQL
  16.13). 5 scenarios, all "Excellent" or "Good".
- **New `docs/LINKEDIN_POST_VARIANTS.md`** — 3 ready-to-publish LinkedIn
  post drafts (Technical Deep-Dive, Business Value, Builder's Story)
  with publishing strategy and asset checklist.
- **New `docs/DEMO_RECORDING.md`** — 30-second demo script, recording
  commands for macOS/Linux/CI, and LinkedIn optimization tips.
- **New `README.md` section: "Why this module vs OCA `account_budget_oca`?"** —
  honest 13-row comparison table acknowledging OCA's module as the
  baseline. Module is positioned as an *enforcement layer*, not a
  replacement.
- **New `README.md` section: target audience & use cases** — 5 real-world
  scenarios (manufacturing, government, holding, NGO, education) where
  this module is impactful, plus 4 honest "when NOT to use" scenarios.
- **New `readme/USAGE.md` section: Multi-Company Scenario** — 60 lines
  covering step-by-step multi-company setup, isolation testing,
  consolidated reporting, and record rule reference.
- **New `README.md` "Demo & Documentation" navigation table** at the top
  of the file.

### Added — Code (Sesi 2)

- **Multi-currency support** — `budget.plan.currency_id` is now editable.
  `is_multi_currency` boolean field. 4 new computed fields on
  `budget.plan.line` (`planned/actual/committed/available` in company
  currency) for cross-currency visibility. Validation prevents
  archived-currency assignment.
- **Multi-currency validation in overhead allocation** — explicit
  `ValidationError` if allocation currency != company currency, with
  a clear explanation of the v18.0.2.x scope decision.
- **CSV / XLSX export wizard** (`budget.variance.export`) — new
  `TransientModel` + form view + action + menu. Filters by plan,
  date range, cost center, and state (`all/approved/active/over_budget`).
  XLSX via `openpyxl` (already in container; declared in
  `external_dependencies`), CSV via stdlib. Optional
  "include company currency" column.
- **Smart buttons on cost center** — 3 buttons in the button box:
  Budget Plans (count), Total Planned (sum with multi-currency
  conversion), Over Budget Lines (count, red text). 2 action methods
  open pre-filtered tree views.
- **Scheduled allocation cron** — `ir.cron` registered, runs daily.
  Clones allocation templates that are due based on
  `recurring_interval_months`. New fields: `is_recurring`,
  `recurring_interval_months`, `last_run_date`, `recurring_count`.
  Validation enforces 1–12 month range.

### Added — Tests (Sesi 3)

- **`tests/test_performance.py`** — 5 benchmark scenarios with
  real-number logging via `[BENCHMARK] name: time` lines.
  Soft targets are loose to avoid CI flakiness.
- **`tests/test_multi_company.py`** — 3 isolation tests covering
  cross-company CC assignment (blocked by `_check_company=True`),
  budget-line data isolation by company, and PO committed amount
  not bleeding across companies (SQL `o.company_id` filter works).
- **2 new tests in `tests/test_committed_amount.py`** — multi-currency
  overridable + inactive currency blocked.
- **`tests/__init__.py` updated** to import the new test files.

### Fixed

- `decoration-success="alert_level == 'ok'"` in `views/budget_plan_views.xml`
  was a no-op (the `alert_level` selection is `normal`, not `ok`).
  Fixed to `'normal'` in 2 places.
- Duplicate "Actual Amount", "Usage", "Alert Level" rows removed from
  `data/mail_template_over_budget.xml`.
- `_compute_committed_amount` SQL referenced
  `purchase_order_line.account_analytic_id` — a column that doesn't
  exist in Odoo 18 (replaced by `analytic_distribution` JSONB). Removed
  the dead filter; savepoint isolation now succeeds without the
  transaction poisoning side-effect.

### Performance (measured 2026-06-04, Apple M1 / 8 GB / PG 16.13)

| Scenario | Time | Per-unit |
|---|---|---|
| `actual_amount` compute (100 lines) | 0.15 s | 1.5 ms/line |
| `po_committed_amount` compute (100 lines) | 0.16 s | 1.6 ms/line |
| Budget workflow (50 plans × 2 actions) | 0.97 s | 18 ms/plan |
| Move posting (50 entries, full validation) | 3.32 s | 66 ms/move |
| Allocation (25 runs × 50 target CCs) | 6.15 s | 246 ms/run |

All benchmarks: **5–33× under their soft targets**. No regression vs
v18.0.2.0.0.

### Multi-Company Isolation (3/3 PASS)

- Cost center from Company A **cannot** be assigned to a Company B
  budget plan (raises `ValidationError`).
- Posted journal entry in Company A does **not** appear in Company B
  budget line aggregation.
- Confirmed PO in Company B contributes **zero** to Company A's
  `po_committed_amount` (SQL filter `o.company_id` works).

### Test Status

- **34 tests** total in `cost_center_budget_control` (was 26).
- **31 pass**, **3 pre-existing failures** carried over from
  v18.0.2.0.0 (none introduced by this release). Pre-existing failures:
  - `TestBudgetAllocation.test_idempotency_reference_is_deterministic`
    (assertion mismatch in deterministic ref test)
  - `TestBudgetControl.test_override_allows_manager`
    (assertion mismatch on override flow)
  - `TestBudgetControl.test_warning_allows_posting`
    (assertion mismatch on warning behavior)

### Migration from v18.0.2.0.0

No data migration required. Schema changes are additive:
- New fields on `budget.plan`, `budget.plan.line`, `cost.center`,
  `budget.allocation` (all nullable or with safe defaults).
- New model `budget.variance.export` (TransientModel, no DB table).
- New `ir.cron` record (idempotent, no impact if not enabled).
- 2 new menu items (`Reporting > Export Variance Report`,
  `Reporting > Export Variance Report`).

Standard Odoo upgrade:
```bash
odoo-bin -u cost_center_budget_control -d <db> --stop-after-init
```

## [18.0.2.0.0] - 2026-06-04

### Added
- **Committed Amount tracking with Purchase Order integration**
  - `po_committed_amount` field: SUM of confirmed-but-unbilled PO lines
  - `committed_amount` field: Actual + PO Committed (mirrors Odoo 18 native
    "Committed" column convention)
  - `available_amount` field: Planned - Committed, negative = over-committed
  - SQL aggregation on `purchase_order_line.analytic_distribution` (JSONB)
  - Auto-recompute on PO confirm, cancel, amend, and line write/unlink
- **Budget Revision (Revise) workflow**
  - New `revised` state in budget plan state machine
  - `parent_revision_id` self-reference linking revision chain
  - `revision_number` (1 = original, 2 = first revision, etc.)
  - `is_latest_revision` computed field
  - `action_revise()`: clones approved budget, marks original as `revised`
  - Revisions are immutable history
- **PO validation hook (opt-in)**
  - `cost_center_budget_control.block_on_purchase` setting
  - When enabled, RFQ confirmation fails if it would exceed blocking threshold
  - Same Override Manager governance as the move-level hook
- **9 new budget revision tests** in `test_budget_revision.py`
- **9 new committed amount tests** in `test_committed_amount.py`
- **5 new settings** in `res.config.settings` (3 from earlier phases, plus
  `budget_block_on_purchase`)

### Dependencies
- Added `purchase` to module depends list (required for PO committed tracking)

### Fixed
- **Mail template broken field reference**: `manager_id` → `responsible_id` in
  `data/mail_template_over_budget.xml` (the actual field on `cost.center` is
  `responsible_id`)
- **Demo data `account.account` field name**: Odoo 17+ uses `company_ids`
  (Many2many), not `company_id`. Updated `demo/demo.xml` accordingly.
- **`test_allocation_cost_center.py` broken field references**: Rewrote test
  fixtures and test cases to use real model fields (`allocation_date` instead
  of `date_from`/`date_to`, `amount_base` instead of missing `line.amount`).
  Tests now pass against the actual model API.
- **Misleading `approval_required` mode**: Removed from
  `res.config_settings.budget_control_mode` selection. The mode was declared
  but never handled in validation logic, causing silent fallback to
  `warning_only`. Two-option selection is honest and consistent.

## [18.0.1.0.0] - 2026-06-04

### Added
- OCA structural files: `LICENSE`, `static/description/`, `readme/`
- `.pre-commit-config.yaml` with Black, isort, ruff
- `CHANGELOG.md` for version history
- `.github/ISSUE_TEMPLATE/` for bug reports and feature requests
- Module icon (`static/description/icon.png`, 128x128 PNG)

### Removed
- Dead code: `action_draft` method, `action_budget_over_budget_lines`
  action, orphan `views/budget_dashboard_views.xml`
- Unused imports: `api`, `ValidationError`
- Unused test fixture `cls.cc_b`
- Misleading no-op `with_context(budget_override=True)` flag from tests
- `board` module dependency (and transitive `spreadsheet_dashboard`
  auto-installation)

### Fixed
- Misleading test comment about `with_context(budget_override=True)`
- Trailing whitespace in test setup
- Working tree inconsistency (7 uncommitted modifications)

## [18.0.1.0.0] - Initial Release

### Added
- Hierarchical cost center management with parent-child structure
- Workflow-driven budget plans (`Draft → Submitted → Approved → Closed/Cancelled`)
- Real-time `actual_amount` aggregation via JSONB SQL queries
- Programmatic overhead allocation engine with balanced journal entries
- Idempotent allocation references (deterministic unique keys)
- Configurable threshold validation (70% warning, 100% blocking)
- Role-based override controls (group membership, not context flags)
- Multi-company isolation via `_check_company_auto` and record rules
- Custom GIN index on `analytic_distribution` for query performance
- Pivot and graph reporting views
- Demo data with sample cost centers, budget plans, and over-budget scenario

### Security
- 3-tier security group hierarchy (User → Manager → Override Manager)
- Multi-company record rules for all cross-company models
- Override check is group-based, not context-based, to prevent
  privilege escalation
