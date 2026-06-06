# Contributing to Cost Center & Budget Control

Thanks for your interest in contributing! This document is short on
purpose — the project follows standard open-source conventions, with
a few opinionated choices documented below.

---

## Quick Start

```bash
# 1. Fork & clone
git clone https://github.com/<you>/odoo18-cost-center.git
cd odoo18-cost-center

# 2. Start the dev environment
docker compose up -d

# 3. Install the module via UI
open http://localhost:8018 → Apps → Cost Center & Budget Control → Install

# 4. Run the test suite
docker stop odoo18-cost-web
docker run --rm --network container:odoo18-cost-db \
  -v $(pwd)/addons:/mnt/extra-addons \
  -e PGHOST=db -e PGUSER=odoo -e PGPASSWORD=odoo \
  odoo:18.0 odoo -i cost_center_budget_control --test-enable \
    --test-tags=/cost_center_budget_control --stop-after-init --no-http \
    -d odoo18_test
docker start odoo18-cost-web
docker exec odoo18-cost-db psql -U odoo -d postgres -c "DROP DATABASE odoo18_test;"
```

---

## Coding Conventions

This project follows **OCA-style** structure. The most important rules:

1. **One model per file**, file name = snake_case version of model name
   (e.g. `budget_plan.py` contains `class BudgetPlan`).
2. **Sequence = `sequence_default`**: the `_order` of a model sorts by
   the most-recently-relevant field first (e.g. `date_from desc, name`).
3. **XML data files in `data/` use `noupdate="1"`** when the records
   are reference data (security groups, mail templates, cron jobs).
4. **Security = declarative**: every new model needs an entry in
   `security/ir.model.access.csv`. Use existing groups when possible.
5. **`_check_company_auto = True`** on every model that has `company_id`.
   This is enforced at the ORM level, not via custom code.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for deeper design
rationale (especially § 5 "Performance Design Decisions").

---

## Performance Discipline

This module processes O(10K) records in O(1) query count via SQL
JSONB + GIN index. **New code that adds an ORM loop over a large
recordset is a regression.** Before opening a PR, ask:

- Could this be done in 1 SQL query instead of N?
- Does my new field have the right `index=True`?
- Am I creating an N+1 by browsing a `one2many` in a loop?

If unsure, look at `_compute_actual_amount` and
`_compute_committed_amount` in
[`models/budget_plan.py`](addons/cost_center_budget_control/models/budget_plan.py)
for the canonical patterns.

---

## Test Requirements

PRs that change behavior must include tests. The 3-tier policy:

| Change type | Test required |
|---|---|
| New field on existing model | 1 test that sets the field and reads it back |
| New model | 3 tests: create, search, security |
| New SQL aggregation | 1 test with at least 50 records + benchmark log |
| New view | Manual screenshot in PR description |
| New cron | 1 test that invokes the cron method directly |
| Bug fix | 1 regression test that would have caught the bug |
| Documentation only | No test required |

Tests use `TransactionCase` (rolls back per test). New tests should
follow the `test_<feature>_<scenario>` naming convention.

---

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Common types in this project:

- `feat`: new feature
- `fix`: bug fix
- `docs`: documentation only
- `perf`: performance improvement
- `test`: test-only change
- `refactor`: code change that doesn't fix a bug or add a feature
- `chore`: build, CI, or tooling change

Example:

```
feat(budget.plan): add multi-currency support

Allow overriding currency_id on budget.plan. Adds 4 computed
fields on budget.plan.line for company-currency equivalent.
Closes #42.
```

---

## Pull Request Process

1. Fork the repo, create a feature branch (`feat/my-feature`).
2. Make your change, add tests, update `CHANGELOG.md`.
3. Verify all tests pass (see Quick Start above).
4. Open a PR. The [PR template](.github/PULL_REQUEST_TEMPLATE.md) will
   guide you. Fill it out completely — incomplete PRs are closed after
   30 days.
5. Wait for CI to pass. Address review comments.
6. Squash-merge when approved.

---

## Reporting Bugs

Open an issue using the [Bug Report template](.github/ISSUE_TEMPLATE/bug.md).
Include:
- Reproduction steps
- Odoo version + module version
- Full log output (`docker compose logs odoo --tail=200`)
- Whether `demo` data was installed

---

## Suggesting Features

Open an issue using the
[Feature Request template](.github/ISSUE_TEMPLATE/feature.md).
Before requesting, check if it can be solved with the existing
**extension points** documented in
[`docs/ARCHITECTURE.md` § 4](docs/ARCHITECTURE.md#4-extension-points).
Most customizations don't need a code change.

---

## License

By contributing, you agree that your contributions will be licensed
under **LGPL-3.0**, matching the project's existing license.
