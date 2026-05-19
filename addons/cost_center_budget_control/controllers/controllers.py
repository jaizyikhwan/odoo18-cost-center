# -*- coding: utf-8 -*-
# from odoo import http


# class CostCenterBudgetControl(http.Controller):
#     @http.route('/cost_center_budget_control/cost_center_budget_control', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/cost_center_budget_control/cost_center_budget_control/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('cost_center_budget_control.listing', {
#             'root': '/cost_center_budget_control/cost_center_budget_control',
#             'objects': http.request.env['cost_center_budget_control.cost_center_budget_control'].search([]),
#         })

#     @http.route('/cost_center_budget_control/cost_center_budget_control/objects/<model("cost_center_budget_control.cost_center_budget_control"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('cost_center_budget_control.object', {
#             'object': obj
#         })

