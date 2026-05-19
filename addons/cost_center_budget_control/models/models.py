# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class cost_center_budget_control(models.Model):
#     _name = 'cost_center_budget_control.cost_center_budget_control'
#     _description = 'cost_center_budget_control.cost_center_budget_control'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

