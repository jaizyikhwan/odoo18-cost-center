# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    budget_control_enabled = fields.Boolean(
        string="Enable Budget Control",
        config_parameter="cost_center_budget_control.enabled",
        default=False,
        help="Global toggle to enable/disable budget threshold checks."
    )

    budget_control_mode = fields.Selection([
        ("warning_only", "Warning Only"),
        ("blocking", "Blocking"),
    ],
        string="Budget Control Mode",
        config_parameter="cost_center_budget_control.mode",
        default="warning_only",
        help="Defines how the system behaves when a budget threshold is exceeded. "
             "warning_only logs alerts to chatter; blocking halts the posting."
    )

    budget_warning_threshold = fields.Float(
        string="Warning Threshold (%)",
        config_parameter="cost_center_budget_control.warning_threshold",
        default=70.0,
        help="Usage percentage that triggers a warning."
    )

    budget_critical_threshold = fields.Float(
        string="Critical Threshold (%)",
        config_parameter="cost_center_budget_control.critical_threshold",
        default=90.0,
        help="Usage percentage that triggers a critical alert."
    )

    budget_blocking_threshold = fields.Float(
        string="Blocking Threshold (%)",
        config_parameter="cost_center_budget_control.blocking_threshold",
        default=100.0,
        help="Usage percentage that blocks posting (in Blocking mode)."
    )

    budget_chatter_enabled = fields.Boolean(
        string="Enable Chatter Alerts",
        config_parameter="cost_center_budget_control.chatter_enabled",
        default=True,
        help="If enabled, threshold alerts will be posted to the document chatter."
    )

    budget_activity_enabled = fields.Boolean(
        string="Enable Activity Scheduling",
        config_parameter="cost_center_budget_control.activity_enabled",
        default=True,
        help="If enabled, critical alerts will schedule activities for managers."
    )
