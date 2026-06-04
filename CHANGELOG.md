# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
