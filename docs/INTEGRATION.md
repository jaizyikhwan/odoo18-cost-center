# Integration Guide

> **Audience**: System administrators, Odoo integrators, and developers
> who need to deploy this module alongside other budget/accounting
> modules.
>
> **Last updated**: 2026-06-04

This document describes how this module coexists with other budget
modules in the Odoo ecosystem, and provides migration paths from
vanilla Odoo or OCA's `account_budget_oca`.

---

## 1. Quick Reference Matrix

| Scenario | Compatible? | Recommended Approach |
|---|---|---|
| **Vanilla Odoo 18 CE** (no budget module) | ✅ Fully compatible | Install this module — it provides everything vanilla lacks |
| **OCA `account_budget_oca` (v18.0)** | ✅ Compatible | Install both. Use `account_budget_oca` for **multi-company crossovered budgets**, use this module for **per-cost-center enforcement** |
| **OCA `account_budget_oca` + this module** | ✅ Best of both worlds | Recommended for organizations with complex multi-company budget needs |
| **Native Odoo Enterprise `account.budget`** | ⚠️ Disabled by Enterprise | Enterprise module auto-disables if not licensed; this module is a CE alternative |
| **Both Enterprise `account.budget` AND this module** | ❌ Conflict | OCA note: "incompatible". Disable Enterprise `account.budget` or this module |

---

## 2. Coexistence with OCA `account_budget_oca`

OCA's `account_budget_oca` is a **great** module maintained by Odoo S.A.
It provides:

- `crossovered.budget` (analytic budget definition)
- `crossovered.budget.lines` (planned/actual/practical amount)
- 3 built-in QWeb reports
- Multi-company support

This module provides **complementary** features:

- Per-cost-center enforcement (not per-analytic)
- Hard-block at posting
- PO committed tracking
- Allocation engine
- Revision chain

### 2.1 Installation Order

**No specific order required.** Both modules can be installed
independently:

```bash
# Either order works
odoo-bin -d mydb -i account_budget_oca,cost_center_budget_control
# OR
odoo-bin -d mydb -i cost_center_budget_control,account_budget_oca
```

After installation, both module sets are active and don't conflict.

### 2.2 Data Model Coexistence

| Concept | `account_budget_oca` | This Module |
|---|---|---|
| Budget definition | `crossovered.budget` | `budget.plan` |
| Budget line | `crossovered.budget.lines` | `budget.plan.line` |
| Org unit | `account.analytic.account` | `cost.center` (linked to analytic account) |
| Actual amount | `practical_amount` (computed via `_compute_practical_amount`) | `actual_amount` (computed via SQL JSONB) |
| Committed amount | (not in CE version) | `po_committed_amount`, `committed_amount` |

**Note**: The two `actual` amounts are computed differently but should
match (within tolerance) for the same analytic account + period. The
`account_budget_oca` uses ORM search; this module uses SQL JSONB with
GIN index. For very large datasets, this module's compute is faster.

### 2.3 Optional: Sync Budget Plan ↔ Crossovered Budget

If you want data to flow from `budget.plan` (this module) to
`crossovered.budget` (OCA), you can add a sync hook in your custom
module. Example:

```python
# In your custom module: models/budget_plan_sync.py
from odoo import models, api


class BudgetPlanSync(models.Model):
    _inherit = "budget.plan"

    crossovered_budget_id = fields.Many2one(
        "crossovered.budget",
        help="Optional link to OCA crossovered.budget for cross-reporting",
    )

    @api.model_create_multi
    def create(self, vals_list):
        plans = super().create(vals_list)
        for plan, vals in zip(plans, vals_list):
            if self.env.context.get("sync_to_oca_budget"):
                # Create corresponding crossovered.budget
                cb = self.env["crossovered.budget"].create({
                    "name": plan.name,
                    "date_from": plan.date_from,
                    "date_to": plan.date_to,
                    # ... other fields
                })
                plan.crossovered_budget_id = cb
        return plans
```

This is **optional** and **not enabled by default**. Most users will
find the two modules' reporting sufficient on their own.

---

## 3. Coexistence with Odoo Enterprise `account.budget`

**OCA's documented note**: *"This module is incompatible with Odoo
Enterprise account_budget module"*.

This is because both modules:

- Use the `account.budget` XML ID
- Override `account.move._post` to add budget checks
- Define `crossovered.budget` (or similar) models

**Practical implication**: You cannot have both Enterprise
`account.budget` AND this module active simultaneously.

### 3.1 Which to Choose?

| Choose Enterprise `account.budget` if: | Choose This Module if: |
|---|---|
| You already have Odoo Enterprise license | You're on Odoo Community |
| You need Odoo's official support contract | You're comfortable with community/OCA support |
| You need other Enterprise features (helpdesk, mobile, etc.) | You only need budget enforcement |
| You need automated budget vs actual reports in pivot | You need **enforcement + allocation + revision** |
| Your Odoo partner insists on Enterprise | You want LGPL-3 source-available |

**Cost consideration**: Enterprise is ~$20-25/user/month. For an org
with 50 users, that's $12,000-15,000/year just for budget module.

This module: **free**, LGPL-3, source-available, OCA-style.

### 3.2 If You're Currently on Enterprise

To migrate from Enterprise `account.budget` to this module:

1. **Disable** Enterprise `account.budget` module
2. **Install** this module + OCA `account_budget_oca` (optional)
3. **Migrate data** (see Section 5 below)
4. **Validate** that reports match expectations

---

## 4. Coexistence with OCA `account_budget_oca_usability`

OCA has another module `account_budget_oca_usability` (by AvanzOSC)
that adds pivot view for budget lines. It is:

- **Compatible** with `account_budget_oca`
- **Compatible** with this module (different models, no overlap)
- Adds: pivot view, "Budget Lines" sub-menu

You can install all three without issues.

---

## 5. Migration Path from Vanilla Odoo 18

If you currently use vanilla Odoo 18's `account.budget` and want to
migrate to this module:

### 5.1 Pre-Migration Audit

```sql
-- Run in psql to audit existing budget data
SELECT
    b.name,
    b.date_from,
    b.date_to,
    COUNT(bl.id) AS line_count,
    SUM(bl.planned_amount) AS total_planned
FROM account_budget b
LEFT JOIN account_budget_line bl ON bl.budget_id = b.id
WHERE b.state != 'cancelled'
GROUP BY b.id
ORDER BY b.date_from DESC;
```

This gives you a baseline of what to migrate.

### 5.2 Migration Script (Manual Process)

For each existing `account.budget` in vanilla:

1. Identify the analytic account(s) in `account.budget.line`
2. Find or create a `cost.center` with matching `analytic_account_id`
3. Create a new `budget.plan` for the period
4. Create `budget.plan.line` for each `account.budget.line`:
   - `account_id` ← `account.budget.line.account_id`
   - `planned_amount` ← `account.budget.line.planned_amount`
   - `name` ← description
5. (Optional) Link via custom field for historical reference

### 5.3 Sample Migration Code (Odoo Shell)

```python
# In Odoo shell (odoo-bin shell -d mydb)
env = Environment(cr, SUPERUSER_ID, {})

# Get all vanilla budgets
vanilla_budgets = env['account.budget'].search([('state', '!=', 'cancelled')])

for vb in vanilla_budgets:
    # Find or create cost center
    analytic = vb.analytic_account_id
    cost_center = env['cost.center'].search([
        ('analytic_account_id', '=', analytic.id)
    ], limit=1)

    if not cost_center:
        cost_center = env['cost.center'].create({
            'name': analytic.name,
            'code': analytic.code or analytic.name[:8],
            'analytic_account_id': analytic.id,
            'company_id': vb.company_id.id,
        })

    # Create budget plan
    plan = env['budget.plan'].create({
        'name': f"[Migrated] {vb.name}",
        'cost_center_id': cost_center.id,
        'date_from': vb.date_from,
        'date_to': vb.date_to,
        'state': 'approved',  # or 'submitted' if you want re-approval
    })

    # Migrate lines
    for vbl in vb.budget_line_ids:
        env['budget.plan.line'].create({
            'plan_id': plan.id,
            'account_id': vbl.account_id.id,
            'planned_amount': vbl.planned_amount,
            'name': vbl.name or '',
        })

    env.cr.commit()
    print(f"Migrated: {vb.name} → {plan.name}")
```

### 5.4 Post-Migration Validation

1. Compare `actual_amount` between vanilla and this module for same
   period — should match within rounding tolerance
2. Compare `planned_amount` totals — should match exactly
3. Verify all `cost.center` records are linked to a valid
   `analytic.account`
4. Test threshold validation by posting a small JE

---

## 6. Cross-Module Conflict Resolution

If you encounter errors during install/upgrade:

### 6.1 "Model already exists" Error

Means another module defines the same model. Likely candidates:
- `account.budget` (Enterprise)
- `account_budget_oca` (OCA)

**Fix**: Uninstall the conflicting module first.

### 6.2 "Field X already exists with different type"

Means another module defines the same field with different type.
Example: both modules define `state` on a related model with different
selection.

**Fix**: Check `__manifest__.py` of all installed modules; the
conflicting one must be modified (not in scope for this guide).

### 6.3 Demo Data Conflict

This module's demo data uses IDs like `cost_center_*`, `budget_plan_*`.
If another module uses the same external IDs, demo data fails to load.

**Fix**: Use `noupdate="1"` on demo data, or rename XML IDs in one
module.

---

## 7. Production Deployment Checklist

Before deploying this module to production:

- [ ] **Backup database** before any module install/upgrade
- [ ] **Test in staging** with copy of production data
- [ ] **Verify multi-company** isolation works for your setup
- [ ] **Configure settings** (thresholds, override groups) before
  enabling in production
- [ ] **Audit existing users** for proper group assignment
- [ ] **Set `block_on_purchase = False`** initially (opt-in only)
- [ ] **Train finance team** on override workflow
- [ ] **Set up monitoring** for `ir.config_parameter` for settings
  changes
- [ ] **Document your budget periods** (e.g., fiscal year start, period
  alignment)
- [ ] **Plan revision cycles** (when is Revise expected, by whom)

---

## 8. API & Webhook Integration (Future)

This module currently uses standard Odoo XML-RPC / JSON-RPC. No
custom REST API is exposed. For external system integration:

| Need | Solution |
|---|---|
| Read budget status from BI tool | Use Odoo's `/xmlrpc/2/object` endpoint with `execute_kw` |
| Trigger allocation from external scheduler | Create allocation via XML-RPC, call `action_allocate()` |
| Webhook on threshold breach | Subscribe to `account.move` chatter via Odoo's bus (long-polling) |
| Bulk import historical budgets | Use Odoo's standard `import` wizard on `budget.plan` |

For more advanced needs, the module is extensible via `_inherit` on
any model. See [`ARCHITECTURE.md` Section 4](ARCHITECTURE.md#4-extension-points).

---

## 9. Frequently Asked Questions

### Q: Can I use this module without OCA `account_budget_oca`?

A: Yes. This module is **standalone**. It does not require
`account_budget_oca`. They are complementary but independent.

### Q: Will this module auto-create a crossovered.budget when I create a
budget.plan?

A: No. They are independent models. If you want sync, see Section 2.3
above.

### Q: I'm on Odoo 17. Can I use this module?

A: No. The module targets Odoo 18.0 specifically due to:
- `analytic_distribution` JSONB (v16+, but with v18-specific behaviors)
- `_parent_store` API stable in v18
- `account.move._post()` signature changes

For Odoo 17, the module would need a separate branch. (Not currently
maintained.)

### Q: Does this work with OCA `mis_builder`?

A: Yes, they are independent modules. You can use `mis_builder` for
advanced KPI dashboards on top of `budget.plan.line` data via
`_compute_*` extension. No conflict.

### Q: What about multi-currency?

A: Supported in this module. Each `budget.plan` can have its own
`currency_id` (defaults to company currency but can be overridden).
SQL aggregate uses `currency_id` for grouping; conversion to company
currency happens at display time.

### Q: How do I disable enforcement temporarily?

A: Set `cost_center_budget_control.enabled = False` via Settings
(checkbox) or via shell:
```python
env['ir.config_parameter'].set_param(
    'cost_center_budget_control.enabled', False
)
```
The hard-block is bypassed; warnings are also disabled.

---

## 10. Getting Help

If you encounter issues not covered here:

1. Check the [main README troubleshooting section](../README.md#troubleshooting)
2. Search [GitHub Issues](https://github.com/jaizyikhwan/odoo18-cost-center/issues)
3. Open a new issue with:
   - Odoo version + commit hash
   - Steps to reproduce
   - Expected vs actual behavior
   - Module combination installed (this + which others)
