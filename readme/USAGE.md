# Usage Guide

This document walks through the end-to-end workflow of the Cost Center &
Budget Control module.

## 1. Initial Setup

After installing the module, navigate to **Settings → Cost Center & Budget
Control** to configure thresholds:

| Setting | Default | Purpose |
|---|---|---|
| Enable Budget Control | `True` | Master switch |
| Control Mode | `warning_only` | `blocking` or `warning_only` |
| Warning Threshold | `70%` | Chatter warning posted |
| Blocking Threshold | `100%` | Posting halted |
| Chatter Notifications | `True` | Log warnings to document chatter |
| Activity Notifications | `False` | Schedule activity alerts |

## 2. Cost Center Lifecycle

1. Navigate to **Cost Center & Budget Control → Cost Centers → Create**
2. Fill in:
   - **Name** (required)
   - **Code** (required, unique per company)
   - **Parent Cost Center** (optional, for hierarchy)
   - **Company** (required, defaults to current)
   - **Manager** (responsible user)
   - **Analytic Account** (auto-created if not provided)
3. Save and archive when no longer needed (active flag, not delete)

### Hierarchy
Parent-child relationships are stored using Odoo's `_parent_store`
mechanism for efficient tree traversal. The `parent_path` field provides
materialized path queries for fast ancestor lookups.

## 3. Budget Plan Workflow

State machine: `Draft → Submitted → Approved → Closed / Cancelled`

| From | To | Action | By Whom |
|---|---|---|---|
| Draft | Submitted | **Submit** | Budget User |
| Submitted | Draft | **Reject** | Budget Manager |
| Submitted | Approved | **Approve** | Budget Manager |
| Approved | Closed | **Close** | Budget Manager |
| * | Cancelled | **Cancel** | Budget Manager |

### Steps
1. **Create** budget plan in `Draft` state
2. Add **budget lines**: each line pairs an `account.account` with a
   `planned_amount` and (optionally) a date range
3. **Submit** when ready for review
4. **Approve** to lock the plan against modifications
5. As accounting moves get posted with matching analytic accounts, the
   `actual_amount`, `variance_amount`, `usage_percent`, and `alert_level`
   fields are automatically computed
6. **Close** the plan at the end of the period

## 4. Budget Threshold Control

When a journal entry is posted and it has analytic accounts linked to
cost centers with active budget plans:

- **< 70%**: posting proceeds silently
- **70% – 100%**: posting proceeds, chatter warning is logged (if enabled)
- **> 100%** in `blocking` mode: posting fails with `UserError` listing
  the impacted budget plans. An Override Manager can authorize the
  override by group membership (not by context flag).

## 5. Overhead Allocation

Allocate shared overhead costs from a source cost center to multiple
target cost centers by percentage:

1. Navigate to **Budget Allocations → Create**
2. Set **Source Cost Center** (the overhead pool)
3. Add **Allocation Lines**: each line pairs a target cost center with
   a percentage. The sum MUST equal 100%.
4. Set **Period** (date range)
5. Click **Allocate** — the system:
   - Validates percentages sum to 100%
   - Calculates proportional debits
   - Absorbs rounding residual in the final line
   - Generates a balanced `account.move` with analytic distribution
   - Assigns a deterministic idempotency reference
6. Use **Reverse** if the allocation needs to be undone (generates a
   reversal entry)

## 6. Reporting

- **Budget Analysis** (pivot) — `actual` vs `planned` by cost center × account
- **Budget Graphs** (bar/line) — usage trend
- **Allocation Analysis** (pivot) — overhead distribution history

## 7. Demo Data

The module ships with demo data that activates budget control, creates
sample cost centers, budget plans, and an over-budget scenario. Install
with demo data enabled to see the module in action immediately.
