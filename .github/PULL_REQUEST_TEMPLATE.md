---
name: Pull request
about: Submit a code change to Cost Center & Budget Control
title: '[PR] '
labels: ''
assignees: ''
---

## What does this PR do?

<!-- One-paragraph summary of the change. -->

## Why is this change needed?

<!-- Link the issue, or explain the use case. -->

Closes #<issue_number> (if applicable)

## How was this tested?

<!-- Describe the test plan. -->

- [ ] Existing tests pass (`odoo-bin -d test_db --test-enable --test-tags=/cost_center_budget_control`)
- [ ] New tests added (if behaviour changed)
- [ ] Manual test in browser (if UI changed — attach screenshot)
- [ ] Multi-company isolation verified (if relevant)

## Type of change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Refactor (no functional change)

## Checklist

- [ ] My code follows the OCA-style conventions of this project
- [ ] I have added tests that prove my fix/feature works
- [ ] New and existing unit tests pass locally
- [ ] I have updated [`CHANGELOG.md`](../../CHANGELOG.md) under the unreleased section
- [ ] I have read the [`docs/ARCHITECTURE.md`](../../docs/ARCHITECTURE.md) and my change
      does not violate the design decisions documented there
- [ ] I have not introduced any new lint warnings
- [ ] I have not introduced any N+1 query patterns (use SQL with GIN index for
      aggregations, as documented in `docs/ARCHITECTURE.md` § 5.1)

## Screenshots (if UI changed)

<!-- Add screenshots/GIFs to help reviewers understand the change. -->

## Performance impact (if applicable)

<!-- If your change touches SQL or large data paths, include a benchmark. -->

| Scenario | Before | After |
|---|---|---|
| | | |

## Additional context

<!-- Anything else the reviewer should know. -->
