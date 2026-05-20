# Project Backlog: odoo18-cost-center

Project Status:
- Scaffold initialized
- Docker environment exists
- Initial GitHub commit completed

---

# PHASE 1 — Core Foundation

## Repository Analysis

- [ ] Analyze existing repository structure
- [ ] Analyze scaffold architecture
- [ ] Analyze current module registration
- [ ] Analyze Docker setup relevanceThe Cost Center foundation is now stable enough to continue.

Next, we will move into the Budget Models phase:

* `budget.plan`
* `budget.plan.line`

Before implementing anything, switch to PLAN mode first.

Tasks for this planning phase:

1. Analyze current repository state

* inspect existing models
* inspect current security structure
* inspect current XML/menu architecture
* inspect company consistency patterns already implemented
* inspect analytic account integration already implemented

2. Design the architecture for:

* `budget.plan`
* `budget.plan.line`

3. Propose:

* model responsibilities
* field structure
* workflow/state machine
  (`draft -> submitted -> approved -> active -> closed -> cancelled`)
* accounting relationships
* company consistency strategy
* currency handling strategy
* future compatibility with `actual_amount`
* future compatibility with overhead allocation engine
* future reporting compatibility

4. Specifically explain:

* how `budget.plan.line` should relate to `account.account`
* whether account selection should be restricted by account type/category
* what accounting strategy is most appropriate for enterprise budgeting use cases
* how date ranges should work
* how overlapping budget periods for the same Cost Center should be prevented
* how state transitions should behave
* how approved/active budgets should be protected from accidental edits
  (readonly strategy, locking strategy, cancellation behavior, etc.)
* how future computed aggregation can remain performant
* how future reporting/grouping compatibility should be preserved

5. Multi-company expectations
   Ensure:

* strict company isolation
* proper use of `_check_company_auto`
* proper use of `check_company=True`
* no cross-company accounting references
* safe currency consistency

6. Odoo 18 architecture expectations

* follow native Odoo 18 CE patterns
* avoid overengineering
* prefer maintainable ORM design
* prefer explicit accounting logic
* prefer OCA-style accounting architecture
* use Context7 references when uncertain

7. Accounting safety expectations

* avoid future double-budgeting scenarios
* avoid ambiguous accounting aggregation behavior
* ensure future `actual_amount` computation remains deterministic
* ensure future allocation engine integration remains safe

Do NOT implement code yet.

Do NOT create files yet.

Do NOT continue automatically.

After analysis:

* provide a detailed implementation proposal
* explain architectural tradeoffs
* explain accounting tradeoffs
* explain workflow decisions
* explain risks and future scaling considerations
* explain how this design prepares the module for:

  * `actual_amount`
  * overhead allocation engine
  * threshold control
  * future reporting/analytics


---

## Core Models

- [ ] Create `cost.center` model
- [ ] Add cost center sequence
- [ ] Add company support
- [ ] Add active/archive support
- [ ] Add responsible manager relation
- [ ] Add optional hierarchy support

---

## Budget Models

- [ ] Create `budget.plan`
- [ ] Create `budget.plan.line`
- [ ] Add budget states/workflow
- [ ] Add period/date support
- [ ] Add currency support
- [ ] Add planned amount fields

---

## Security

- [ ] Create `ir.model.access.csv`
- [ ] Create user groups
- [ ] Create manager groups
- [ ] Protect accounting-related actions

---

## Base UI

- [ ] Create tree views
- [ ] Create form views
- [ ] Create search views
- [ ] Create menu items
- [ ] Create actions

---

# PHASE 2 — Budget Tracking Engine

## actual_amount Logic (CRITICAL)

- [ ] Add computed field `actual_amount`
- [ ] Aggregate values from `account.move.line`
- [ ] Filter by analytic account
- [ ] Filter by budget period/date range
- [ ] Store computed values
- [ ] Optimize ORM aggregation performance

---

## Budget Metrics

- [ ] Add usage percentage field
- [ ] Add remaining amount field
- [ ] Add over-budget detection
- [ ] Add warning indicators

---

## UX Improvements

- [ ] Add smart buttons
- [ ] Add visual status decorations
- [ ] Add accounting shortcuts

---

# PHASE 3 — Overhead Allocation Engine (CRITICAL)

## Architecture Planning

- [ ] Define allocation workflow
- [ ] Define journal behavior
- [ ] Define allocation strategies
- [ ] Define posting lifecycle

---

## Accounting Engine

- [ ] Create programmatic `account.move`
- [ ] Create balanced `account.move.line`
- [ ] Support analytic distribution
- [ ] Support multi-cost-center allocation
- [ ] Handle debit/credit balancing
- [ ] Support posting workflow
- [ ] Prevent duplicate allocations
- [ ] Implement idempotent behavior

---

## Accounting Validation

- [ ] Validate accounting constraints
- [ ] Validate journal configuration
- [ ] Validate move balancing
- [ ] Validate analytic distribution

---

# PHASE 4 — Budget Control & Configuration

## Settings Integration

- [ ] Create Budget Control settings section
- [ ] Create `res.config.settings` integration
- [ ] Connect settings to `ir.config_parameter`

---

## Threshold Logic

- [ ] Add 70% threshold support
- [ ] Add 90% threshold support
- [ ] Add 100% threshold support
- [ ] Add warning logic
- [ ] Add overspending validation
- [ ] Add blocking behavior if required

---

## Notifications

- [ ] Add chatter integration
- [ ] Add activity scheduling
- [ ] Add warning banners

---

# PHASE 5 — Reporting & Analytics

## Reporting

- [ ] Create pivot views
- [ ] Create graph views
- [ ] Create advanced search filters
- [ ] Create grouped analytics

---

## Dashboard

- [ ] Create budget dashboard
- [ ] Add KPI cards
- [ ] Add allocation summaries
- [ ] Add budget monitoring widgets

---

# PHASE 6 — QA & Stabilization

## Functional Validation

- [ ] Validate module installation
- [ ] Validate upgrade flow
- [ ] Validate XML loading
- [ ] Validate security access
- [ ] Validate accounting correctness

---

## Performance Validation

- [ ] Review computed field performance
- [ ] Review ORM query performance
- [ ] Review reporting performance

---

## Cleanup

- [ ] Remove dead code
- [ ] Improve naming consistency
- [ ] Improve comments/docstrings
- [ ] Improve maintainability

---

# PHASE 7 — Documentation

## README.md

- [ ] Write installation guide
- [ ] Write Docker setup guide
- [ ] Add feature overview
- [ ] Add architecture explanation
- [ ] Add screenshots
- [ ] Add approval flowchart
- [ ] Add allocation flow explanation
- [ ] Add "Without vs With System" comparison table

---

## Developer Documentation

- [ ] Add accounting flow explanation
- [ ] Add technical notes
- [ ] Add troubleshooting notes
- [ ] Add future improvement notes

---

# FINAL REVIEW

- [ ] Final architecture review
- [ ] Final accounting review
- [ ] Final UI review
- [ ] Final README review
- [ ] Prepare GitHub repository for portfolio/demo