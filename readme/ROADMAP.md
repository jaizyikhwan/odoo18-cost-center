# Roadmap

This document tracks planned future improvements and known limitations.

## Planned Features

### Scheduled Allocations
Integrate with Odoo's `ir.cron` framework to execute monthly overhead
allocations automatically. The allocation engine already supports the
underlying logic; only a cron entry is missing.

### Budget Variance Report (QWeb PDF)
A QWeb-rendered PDF report showing planned vs actual variance per cost
center, with department headers, status indicators, and a footer summary.
This is the most-requested portfolio enhancement.

### Budget Approval Wizard
A `TransientModel` wizard that batches multiple budget plans for
approval/rejection with a comment. Useful for month-end review sessions.

### Over-Budget Email Notification
A `mail.template` triggered from `_validate_budget_control` when a
posting crosses the warning or critical threshold. The template is
ready to integrate — only the trigger and recipient lookup remain.

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

### `approval_required` Mode (Not Implemented)
The `res.config.settings` declares a third mode `approval_required` in
its selection field, but the validation logic in `_validate_budget_control`
only handles `blocking` and `warning_only`. The third option silently
behaves as `warning_only`. Either the mode needs implementation or the
option should be removed.

## Future Considerations

- Integration with OCA `mis_builder` for advanced management reporting
- Excel/CSV export of variance reports
- Department-level approval workflow with multi-level sign-off
- Mobile-friendly views (Owl framework)
- Webhook notifications for budget milestones

## Contributing

Bug reports and feature requests are welcome via the issue tracker.
For major changes, please open an issue first to discuss the proposed
change.
