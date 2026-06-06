# -*- coding: utf-8 -*-
{
    "name": "Cost Center & Budget Control",
    "version": "18.0.2.2.0",
    "category": "Accounting/Accounting",
    "summary": "Cost center governance with budget enforcement, PO committed tracking, and version control",
    "description": """
Enterprise-grade Cost Center governance, real-time budget enforcement, Purchase Order
committed amount tracking, and budget version control for Odoo 18 Community Edition.

Builds on Odoo 18's native analytic budgets by adding:
- Hard posting-block mechanism at the move level
- Three-tier role-based override governance
- Hierarchical cost centers with parent-child tree
- Programmatic overhead allocation engine
- Committed amount aggregation from confirmed Purchase Orders
- Budget revision workflow with immutable history chain
    """,
    "author": "Muhammad Ikhwan Jaizy",
    "website": "https://github.com/jaizyikhwan/odoo18-cost-center",
    "license": "LGPL-3",
    "depends": [
        "base",
        "account",
        "analytic",
        "mail",
        "purchase",
    ],
    "external_dependencies": {
        "python": ["openpyxl"],
    },
    "data": [
        "security/security.xml",
        "security/budget_allocation_line_access.xml",
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "report/budget_variance_report.xml",
        "wizard/budget_approval_wizard.xml",
        "wizard/budget_variance_export_views.xml",
        "data/mail_template_over_budget.xml",
        "data/ir_cron_data.xml",
        "views/cost_center_views.xml",
        "views/budget_plan_views.xml",
        "views/budget_allocation_views.xml",
        "views/account_move_views.xml",
        "views/budget_reporting_views.xml",
        "views/allocation_reporting_views.xml",
        "views/menu_items.xml",
        "views/res_config_settings_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "demo": [
        "demo/demo.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "check_company_auto": True,
}
