# Roadmap

This document tracks planned future improvements and known limitations.

## Implemented Beyond Native Odoo 18

The following features are implemented in v18.0.2.0.0 and differentiate this
module from the native Odoo 18 `account.budget`:

- **Hard posting-block on budget overrun** — native Odoo only reports
  threshold breaches in pivot views; this module raises `UserError` at
  `_post()` time.
- **Role-based override governance** — group membership check
  (`group_budget_override_manager`) with chatter audit trail; native Odoo
  has no override concept.
- **Programmatic overhead allocation engine** — balanced journal entries
  with SHA1 idempotency and exact zero residual; not available in native
  Odoo CE.
- **Hierarchical cost center tree** — `cost.center` with `parent_path`
  for parent-child organization; native Odoo `account.analytic.plan` is flat.
- **PO Committed Amount tracking with opt-in hard block** — `po_committed_amount`
  and `committed_amount` fields mirror Odoo 18 Enterprise's `Committed`
  column, with optional hard block on RFQ confirmation.
- **Budget Revision with immutable version chain** — clones approved budget
  as fully editable revision, marks original as `revised` (immutable);
  native Odoo `Revise` only renames the budget.
- **Configurable thresholds via Settings UI** — 3-level thresholds
  (warning / critical / blocking) editable by admin.

## Planned Features

### Scheduled Allocations
Integrate with Odoo's `ir.cron` framework to execute monthly overhead
allocations automatically. The allocation engine already supports the
underlying logic; only a cron entry is missing.

### Budget Approval Wizard
A `TransientModel` wizard that batches multiple budget plans for
approval/rejection with a comment. Useful for month-end review sessions.

### Multi-Currency Support
Currently `currency_id` is `related="company_id.currency_id"`, so all
budgets are denominated in the company currency. A future enhancement
would allow per-budget currency with conversion at posting time using
`res.currency._convert`.

## Known Limitations

### Performance: N+1 in `_validate_budget_control`
The threshold validation uses nested `.filtered(lambda)` calls that
trigger one query per record. For small transaction volumes this is fine,
but large journals with many lines and many budget plans could be slow.
A `read_group` precomputation is the planned fix.

### Hardcoded Alert Thresholds
The `alert_level` field uses hardcoded 70/90/100 thresholds. The
`warning_threshold` and `blocking_threshold` settings are read at runtime,
but the alert_level categorization in `_compute_alert_level` is not
configurable. This is being moved to `ir.config_parameter`.

### Block on Purchase does not validate `mode=warning_only`
The `block_on_purchase` ICP only blocks RFQ confirmation when the budget
control mode is `blocking`. In `warning_only` mode, the PO will be
confirmed even if it would exceed the blocking threshold. This is by
design (matches the move-level behavior), but the report should call
this out more clearly in the budget variance report.

## Future Considerations

- Integration with OCA `mis_builder` for advanced management reporting
- Excel/CSV export of variance reports
- Department-level approval workflow with multi-level sign-off
- Mobile-friendly views (Owl framework)
- Webhook notifications for budget milestones
- `account.budget` and `account.budget.line` syncing (read-only mirror
  of native budgets) for cross-tool reporting

## Contributing

Bug reports and feature requests are welcome via the issue tracker.
For major changes, please open an issue first to discuss the proposed
change.
