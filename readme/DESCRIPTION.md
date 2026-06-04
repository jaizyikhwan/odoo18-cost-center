# Cost Center & Budget Control

Enterprise-grade cost center hierarchy management, workflow-driven budget
planning, real-time budget utilization tracking, and proactive threshold
control for Odoo 18 Community Edition.

## Overview

This module addresses the control gap in standard Odoo analytic accounting
by validating transactions **in real time during the posting workflow**
against approved departmental budgets, rather than relying on retroactive
reports that only highlight overruns after they occur.

## Key Features

- **Hierarchical cost centers** with parent-child organizational structures
- **Workflow-driven budget plans** (`Draft → Submitted → Approved → Closed/Cancelled`)
- **Real-time `actual_amount` aggregation** via JSONB-aware SQL queries
- **Programmatic overhead allocation engine** with balanced journal generation
- **Idempotent allocation** through deterministic reference keys
- **Configurable threshold validation** (70% warning, 90% critical, 100% blocking)
- **Role-based override controls** (group membership, not context flags)
- **Multi-company isolation** via `_check_company_auto` + record rules
- **Custom GIN index** on `analytic_distribution` for query performance

## Architecture Pillars

### 1. Data Integrity & Immutability
Approved, closed, and cancelled budget plans are locked against
modifications. Structural immutability is enforced at the ORM layer.

### 2. Workflow Discipline
State machine governs who can execute transitions and when. Approved
budgets are read-only by design.

### 3. Ledger Accuracy
All programmatically generated journal entries are perfectly balanced.
Rounding residuals are absorbed by the final target line.

### 4. Multi-Company Safety
Boundary separation is enforced declaratively. Cross-company accounting
references are blocked.

### 5. Proactive Budget Validation
Instead of retroactive reporting, validation is integrated into the
posting workflow. Blocking mode halts overruns and requires authorization
from an Override Manager.

## Installation

```bash
git clone https://github.com/jaizyikhwan/odoo18-cost-center.git
cd odoo18-cost-center
docker compose up -d
```

After Odoo initializes, install the module from the Apps dashboard.
The mounted `addons/` volume allows real-time local file changes to be
reflected immediately on upgrade.

## Tested With

- Odoo 18.0 Community Edition (20260421)
- PostgreSQL 16
- Python 3.11+

## License

LGPL-3. See [LICENSE](../LICENSE).

## Credits

Author: [Muhammad Ikhwan Jaizy](https://github.com/jaizyikhwan)
