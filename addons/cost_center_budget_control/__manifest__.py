# -*- coding: utf-8 -*-
{
    "name": "Cost Center & Budget Control",
    "version": "18.0.1.0.0",
    "category": "Accounting/Accounting",
    "summary": "Hierarchical cost centers with automatic analytic account integration",
    "description": """
Enterprise-grade Cost Center management for Odoo 18 Community Edition.
    """,
    "author": "Muhammad Ikhwan Jaizy",
    "website": "https://github.com/jaizyikhwan/odoo18-cost-center",
    "license": "LGPL-3",
    "depends": [
        "base",
        "board",
        "account",
        "analytic",
        "mail",
    ],
    "data": [
        "security/security.xml",
        "security/budget_allocation_line_access.xml",
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
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
