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
        "account",
        "analytic",
        "mail",
    ],
    "data": [
        # Security and Views will be added in subsequent steps
    ],
    "demo": [
        "demo/demo.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "check_company_auto": True,
}
