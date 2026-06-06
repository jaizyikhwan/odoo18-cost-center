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
| Critical Threshold | `90%` | Mail template queued |
| Blocking Threshold | `100%` | Posting halted |
| Block Purchase Orders | `False` | When `True` + `mode=blocking`, RFQ confirm is also blocked |
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

State machine: `Draft → Submitted → Approved → Revised / Closed / Cancelled`

| From | To | Action | By Whom |
|---|---|---|---|
| Draft | Submitted | **Submit** | Budget User |
| Submitted | Draft | **Reject** | Budget Manager |
| Submitted | Approved | **Approve** | Budget Manager |
| Approved | Revised | **(auto via Revise)** | System (clones to new approved) |
| Revised | (terminal) | (none) | — |
| Approved | Closed | **Close** | Budget Manager |
| * | Cancelled | **Cancel** | Budget Manager |

### Steps
1. **Create** budget plan in `Draft` state
2. Add **budget lines**: each line pairs an `account.account` with a
   `planned_amount` and (optionally) a date range
3. **Submit** when ready for review
4. **Approve** to lock the plan against modifications
5. As accounting moves get posted with matching analytic accounts, the
   `actual_amount`, `po_committed_amount`, `committed_amount`,
   `available_amount`, `variance_amount`, `usage_percent`, and
   `alert_level` fields are automatically computed
6. **Revise** when the budget needs to change mid-period (see §3a)
7. **Close** the plan at the end of the period

### 3a. Budget Revision Workflow

When approved budgets need adjustment mid-period (scope change, reforecast,
new grant, etc.):

1. Open the approved budget plan
2. Click **Revise** in the form header
3. The system:
   - Marks the original as `Revised` (immutable — cannot be edited)
   - Clones the entire plan (header + lines) as a new record
   - Sets the new plan's name to `<original name> (Rev N)` (N auto-increments)
   - Links the new plan to the original via `parent_revision_id`
   - Sets new plan state to `Approved` (the revision itself is immediately
     active; revision is a fresh budget, not a re-approval)
   - Posts a chatter message on the original plan announcing the revision
4. Edit the new plan's lines as needed
5. Subsequent posted moves aggregate to the **new** plan (since the old one
   is `revised` and excluded from `_recompute_actual_amount_batch`)

**Important**: revisions are NOT destructive. The original `revised` plan
remains as audit history with its `actual_amount` snapshot frozen. You can
view the entire chain in the list view by grouping on "Parent Revision".

**Reversal note**: Revisions cannot be reverted via UI action. If a wrong
revision was created, the recommended pattern is to revise it again (chain)
or close it manually via direct ORM (with appropriate permissions and
audit logging).

## 4. Budget Threshold Control

When a journal entry is posted and it has analytic accounts linked to
cost centers with active budget plans:

- **< 70%**: posting proceeds silently
- **70% – 90%**: posting proceeds, chatter warning is logged (if enabled)
- **90% – 100%**: posting proceeds, mail template queued to manager
- **> 100%** in `blocking` mode: posting fails with `UserError` listing
  the impacted budget plans. An Override Manager can authorize the
  override by group membership (not by context flag).

The `committed_amount` is also checked:
- `committed_amount = actual_amount + po_committed_amount`
- `available_amount = planned_amount - committed_amount`
- If `available_amount < 0`, the budget is **over-committed** (line turns
  red in list view, PDF report shows negative value in red)

## 5. Purchase Order Integration

When a Purchase Order is confirmed (status moves from `draft` to `purchase`),
its lines are aggregated into the matching budget line as `po_committed_amount`.
When the corresponding vendor bill is posted, `actual_amount` increases and
`po_committed_amount` decreases (since it's no longer unbilled).

### Opt-in Hard Block
By default, confirming a PO that would exceed a budget's blocking threshold
**succeeds silently** (the overage is visible in reports but does not block
procurement). To enable hard blocking:

1. Go to **Settings → Cost Center & Budget Control**
2. Set **Block Purchase Orders** to `True`
3. Set **Control Mode** to `blocking` (hard block requires blocking mode)
4. Now `button_confirm()` on a PO that would push a budget over the
   threshold will raise `UserError` listing the affected budget plans
5. The block is bypassed for users in the `group_budget_override_manager`
   security group (with chatter audit log)

### Hooked Events
The PO integration auto-recomputes impacted budget lines on:

| Event | Recompute Scope |
|---|---|
| `button_confirm` | All PO lines (new confirmed) |
| `button_cancel` | All PO lines (now un-confirmed) |
| `action_rfq_send` (sent for approval) | No recompute (RFQ is still draft) |
| `write` (any tracked field) | Only changed lines (delta) |
| `unlink` | All PO lines (cascading recompute) |

## 6. Overhead Allocation

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

## 7. Reporting

- **Budget Analysis** (pivot) — `actual` vs `planned` vs `committed` vs
  `available` by cost center × account
- **Budget Graphs** (bar/line) — usage trend
- **Allocation Analysis** (pivot) — overhead distribution history
- **Budget Variance Report** (QWeb PDF) — full variance report with
  planned/actual/PO-committed/committed/available columns, status
  indicators, and revision chain indicators
- **List view filters** — "Over-Budget", "Warning", "Critical",
  "Exceeded", "Over-Committed", "Has Committed POs", "Revised",
  "Latest Revision Only", "Has Revisions"

## 8. Demo Data

The module ships with demo data that activates budget control, creates
sample cost centers, budget plans, and an over-budget scenario. Install
with demo data enabled to see the module in action immediately.

## 9. Multi-Company Scenario

Modul ini fully supports multi-company dengan isolasi ketat di level ORM
dan record rules. Contoh skenario: holding company dengan HQ + 2 anak
perusahaan.

### 9.1 Setup Awal Multi-Company

1. **Aktifkan multi-company** di Settings → Users → Administration:
   - Set "Multi-Company" allowed companies untuk user yang relevan
2. **Buat companies** di Settings → Companies:
   - `Demo Holding (HQ)` — currency IDR
   - `Demo Subsidiary A` — currency IDR
   - `Demo Subsidiary B` — currency USD
3. **Setup Cost Centers per company**:
   - Login sebagai user dengan akses ke Demo Holding
   - Buat cost center: `HQ-Finance`, `HQ-HR` (parent_id = kosong, company = Demo Holding)
   - Switch company ke Demo Subsidiary A
   - Buat cost center: `SUB-A-Operations`, `SUB-A-Sales` (company = Demo Subsidiary A)
4. **Verifikasi isolasi**:
   - Buka Cost Centers sebagai user di Demo Holding
   - Filter by Company: hanya cost center Demo Holding yang visible
   - Cost center Demo Subsidiary A TIDAK terlihat

### 9.2 Cross-Company Block (Negative Test)

Coba test isolasi dengan attempt berbahaya:

1. Login sebagai user di Demo Holding
2. Buka form Demo Holding cost center
3. Coba ubah Company field ke Demo Subsidiary A
4. **Expected error**: ORM `check_company=True` reject — `Company
   incompatible with cost center's analytic account`
5. Hal yang sama berlaku untuk budget plan, allocation, dan journal entry

### 9.3 Consolidated Reporting Across Companies

Untuk CFO yang butuh view cross-company:

1. Login sebagai user dengan akses ke SEMUA companies
2. Buka **Reporting → Budget Analysis**
3. Search bar → Group By: **Company**
4. **Observasi**: Pivot menampilkan cost center + budget data per company
5. **Catatan**: Multi-currency conversion terjadi otomatis di background
   (planned/actual disimpan dalam currency plan, bukan company currency)

### 9.4 Record Rules (Technical Reference)

Modul ini enforce 4 record rules (`security/ir_rule.xml`):

| Rule | Model | Domain |
|---|---|---|
| `budget_plan_comp_rule` | `budget.plan` | `[('company_id', 'in', company_ids)]` |
| `budget_plan_line_comp_rule` | `budget.plan.line` | same |
| `cost_center_comp_rule` | `cost.center` | same |
| `budget_allocation_comp_rule` | `budget.allocation` | same |

User hanya bisa melihat record di companies yang ada di `user.company_ids`.
Tidak ada escape — `sudo()` dibutuhkan untuk bypass (dan di-audit di chatter).
