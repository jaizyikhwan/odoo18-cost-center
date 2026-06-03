from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestBudgetControl(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # Enable budget control and set default thresholds
        env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.enabled', 'True')
        env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.mode', 'warning_only')
        env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.warning_threshold', '70.0')
        env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.blocking_threshold', '100.0')
        # Create company A and B
        cls.company_a = env['res.company'].create({'name': 'Company A'})
        cls.company_b = env['res.company'].create({'name': 'Company B'})
        # Find or create an analytic plan
        cls.analytic_plan = env['account.analytic.plan'].search([], limit=1)
        if not cls.analytic_plan:
            cls.analytic_plan = env['account.analytic.plan'].create({
                'name': 'Test Departments',
            })
        # Create analytic accounts with required plan_id
        cls.analytic_a = env['account.analytic.account'].create({
            'name': 'AA A', 'company_id': cls.company_a.id,
            'plan_id': cls.analytic_plan.id,
        })
        cls.analytic_b = env['account.analytic.account'].create({
            'name': 'AA B', 'company_id': cls.company_b.id,
            'plan_id': cls.analytic_plan.id,
        })
        # Create cost centers
        cls.cc_a = env['cost.center'].create({'name': 'CC A', 'code': 'CCA', 'company_id': cls.company_a.id, 'analytic_account_id': cls.analytic_a.id})
        cls.cc_b = env['cost.center'].create({'name': 'CC B', 'code': 'CCB', 'company_id': cls.company_b.id, 'analytic_account_id': cls.analytic_b.id})
        
        # Create accounts (use company_ids as Odoo 18 account.account expects multi-company field)
        cls.account_expense = env['account.account'].create({
            'name': 'Expense A', 'code': 'EXPA', 'account_type': 'expense',
            'company_ids': [(6, 0, [cls.company_a.id])],
        })
        cls.account_expense_b = env['account.account'].create({
            'name': 'Expense B', 'code': 'EXPB', 'account_type': 'expense',
            'company_ids': [(6, 0, [cls.company_b.id])],
        })
        cls.account_second_a = env['account.account'].create({
            'name': 'Office Supplies A', 'code': 'OFFA', 'account_type': 'expense',
            'company_ids': [(6, 0, [cls.company_a.id])],
        })
        # Create journal
        cls.journal = env['account.journal'].search([('type', '=', 'general'), ('company_id', '=', cls.company_a.id)], limit=1)
        if not cls.journal:
            cls.journal = env['account.journal'].create({'name': 'Journal A', 'code': 'JRN', 'type': 'general', 'company_id': cls.company_a.id})
        # Users (assign to Company A + current company to avoid _check_company issues)
        cls.user_normal = env['res.users'].create({
            'name': 'Normal', 'login': 'normal',
            'company_ids': [(4, cls.company_a.id), (4, env.company.id)],
        })
        cls.user_manager = env['res.users'].create({
            'name': 'Manager', 'login': 'manager',
            'company_ids': [(4, cls.company_a.id), (4, env.company.id)],
        })
        # Assign manager to override group if exists
        group = env.ref('cost_center_budget_control.group_budget_override_manager', False)
        if group:
            cls.user_manager.write({'groups_id': [(4, group.id)]})

        # Create budget plan and lines for company A
        cls.budget_plan = env['budget.plan'].create({
            'name': 'Q1 A', 'cost_center_id': cls.cc_a.id, 'company_id': cls.company_a.id,
            'date_from': '2025-01-01', 'date_to': '2025-03-31'
        })
        cls.budget_line = env['budget.plan.line'].create({
            'plan_id': cls.budget_plan.id, 'account_id': cls.account_expense.id, 'planned_amount': 1000.0
        })

    def test_blocking_prevents_posting(self):
        # Set blocking threshold to 10% for company A
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.mode', 'blocking')
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.blocking_threshold', '10.0')
        # Create move that would exceed
        move = self.env['account.move'].create({
            'journal_id': self.journal.id,
            'date': '2025-02-01',
            'company_id': self.company_a.id,
            'line_ids': [(0,0, {'account_id': self.account_expense.id, 'debit': 200.0, 'credit': 0.0, 'analytic_distribution': {str(self.analytic_a.id): 100.0}}),
                         (0,0, {'account_id': self.account_expense.id, 'debit': 0.0, 'credit': 200.0})]
        })
        with self.assertRaises(UserError):
            move.action_post()

    def test_warning_allows_posting(self):
        # Set warning mode
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.mode', 'warning_only')
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.warning_threshold', '10.0')
        move = self.env['account.move'].create({
            'journal_id': self.journal.id,
            'date': '2025-02-02',
            'company_id': self.company_a.id,
            'line_ids': [(0,0, {'account_id': self.account_expense.id, 'debit': 200.0, 'credit': 0.0, 'analytic_distribution': {str(self.analytic_a.id): 100.0}}),
                         (0,0, {'account_id': self.account_expense.id, 'debit': 0.0, 'credit': 200.0})]
        })
        move.action_post()
        self.assertEqual(move.state, 'posted')
        # Verify budget actual_amount is updated after posting
        self.budget_line.invalidate_recordset(['actual_amount', 'usage_percent'])
        self.assertEqual(self.budget_line.actual_amount, 200.0)
        self.assertAlmostEqual(self.budget_line.usage_percent, 20.0)

    def test_override_allows_manager(self):
        # Set blocking mode
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.mode', 'blocking')
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.blocking_threshold', '10.0')
        move = self.env['account.move'].create({
            'journal_id': self.journal.id,
            'date': '2025-02-03',
            'company_id': self.company_a.id,
            'line_ids': [(0,0, {'account_id': self.account_expense.id, 'debit': 200.0, 'credit': 0.0, 'analytic_distribution': {str(self.analytic_a.id): 100.0}}),
                         (0,0, {'account_id': self.account_expense.id, 'debit': 0.0, 'credit': 200.0})]
        })
        # Manager posts with override context
        move = move.with_user(self.user_manager).with_context(budget_override=True)
        move.action_post()
        self.assertEqual(move.state, 'posted')

    def test_normal_user_cannot_override(self):
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.mode', 'blocking')
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.blocking_threshold', '10.0')
        move = self.env['account.move'].create({
            'journal_id': self.journal.id,
            'date': '2025-02-04',
            'company_id': self.company_a.id,
            'line_ids': [(0,0, {'account_id': self.account_expense.id, 'debit': 200.0, 'credit': 0.0, 'analytic_distribution': {str(self.analytic_a.id): 100.0}}),
                         (0,0, {'account_id': self.account_expense.id, 'debit': 0.0, 'credit': 200.0})]
        })
        move = move.with_user(self.user_normal).with_context(budget_override=True)
        with self.assertRaises(UserError):
            move.action_post()

    def test_split_distribution_aggregation(self):
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.mode', 'blocking')
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.blocking_threshold', '50.0')
        # Create second budget plan with a lower planned amount to trigger blocking
        budget_plan2 = self.env['budget.plan'].create({
            'name': 'Q1 A2', 'cost_center_id': self.cc_a.id, 'company_id': self.company_a.id,
            'date_from': '2025-01-01', 'date_to': '2025-03-31'
        })
        bl2 = self.env['budget.plan.line'].create({
            'plan_id': budget_plan2.id, 'account_id': self.account_second_a.id, 'planned_amount': 300.0,
        })
        # Move with split distribution: second line (200) exceeds 50% of planned (300)
        move = self.env['account.move'].create({
            'journal_id': self.journal.id,
            'date': '2025-02-05',
            'company_id': self.company_a.id,
            'line_ids': [
                (0,0, {'account_id': self.account_expense.id, 'debit': 400.0, 'credit': 0.0, 'analytic_distribution': {str(self.analytic_a.id): 100.0}}),
                (0,0, {'account_id': self.account_second_a.id, 'debit': 200.0, 'credit': 0.0, 'analytic_distribution': {str(self.analytic_a.id): 100.0}}),
                (0,0, {'account_id': self.account_expense.id, 'debit': 0.0, 'credit': 600.0}),
            ]
        })
        with self.assertRaises(UserError):
            move.action_post()

    def test_zero_planned_amount(self):
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.mode', 'blocking')
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.blocking_threshold', '50.0')
        # Create a separate budget plan with zero planned amount line
        budget_plan_zero = self.env['budget.plan'].create({
            'name': 'Q1 Zero', 'cost_center_id': self.cc_a.id, 'company_id': self.company_a.id,
            'date_from': '2025-01-01', 'date_to': '2025-03-31'
        })
        bl_zero = self.env['budget.plan.line'].create({
            'plan_id': budget_plan_zero.id, 'account_id': self.account_expense.id, 'planned_amount': 0.0,
        })
        move = self.env['account.move'].create({
            'journal_id': self.journal.id,
            'date': '2025-02-06',
            'company_id': self.company_a.id,
            'line_ids': [(0,0, {'account_id': self.account_expense.id, 'debit': 100.0, 'credit': 0.0, 'analytic_distribution': {str(self.analytic_a.id): 100.0}}),
                         (0,0, {'account_id': self.account_expense.id, 'debit': 0.0, 'credit': 100.0})]
        })
        # Should not raise ZeroDivisionError; posting should succeed (zero planned = no budget cap enforcement)
        move.action_post()
        self.assertEqual(move.state, 'posted')

    def test_actual_amount_updates_after_posting(self):
        """Budget line actual_amount must reflect posted move amounts."""
        budget_plan = self.env['budget.plan'].create({
            'name': 'Q1 B', 'cost_center_id': self.cc_a.id, 'company_id': self.company_a.id,
            'date_from': '2025-01-01', 'date_to': '2025-03-31'
        })
        budget_line = self.env['budget.plan.line'].create({
            'plan_id': budget_plan.id, 'account_id': self.account_expense.id, 'planned_amount': 1000.0,
        })
        self.assertEqual(budget_line.actual_amount, 0.0)
        move = self.env['account.move'].create({
            'journal_id': self.journal.id,
            'date': '2025-02-09',
            'company_id': self.company_a.id,
            'line_ids': [(0,0, {'account_id': self.account_expense.id, 'debit': 300.0, 'credit': 0.0, 'analytic_distribution': {str(self.analytic_a.id): 100.0}}),
                         (0,0, {'account_id': self.account_expense.id, 'debit': 0.0, 'credit': 300.0})]
        })
        move.action_post()
        self.assertEqual(move.state, 'posted')
        budget_line.invalidate_recordset(['actual_amount', 'usage_percent'])
        self.assertEqual(budget_line.actual_amount, 300.0)
        self.assertAlmostEqual(budget_line.usage_percent, 30.0)

    def test_empty_analytic_distribution(self):
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.mode', 'blocking')
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.blocking_threshold', '10.0')
        move = self.env['account.move'].create({
            'journal_id': self.journal.id,
            'date': '2025-02-07',
            'company_id': self.company_a.id,
            'line_ids': [(0,0, {'account_id': self.account_expense.id, 'debit': 50.0, 'credit': 0.0, 'analytic_distribution': {}}),
                         (0,0, {'account_id': self.account_expense.id, 'debit': 0.0, 'credit': 50.0})]
        })
        # Empty distribution should not crash; behavior: no impacted budgets -> posting allowed
        move.action_post()
        self.assertEqual(move.state, 'posted')

    def test_multi_company_isolation(self):
        # Set thresholds differently for companies
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.mode', 'blocking')
        self.env['ir.config_parameter'].sudo().set_param('cost_center_budget_control.blocking_threshold', '10.0')
        # Create a move in company B which should not be blocked by company A settings
        j_b = self.env['account.journal'].create({'name': 'Journal B', 'code': 'JRNB', 'type': 'general', 'company_id': self.company_b.id})
        move = self.env['account.move'].create({
            'journal_id': j_b.id,
            'date': '2025-02-08',
            'company_id': self.company_b.id,
            'line_ids': [(0,0, {'account_id': self.account_expense_b.id, 'debit': 200.0, 'credit': 0.0, 'analytic_distribution': {str(self.analytic_b.id): 100.0}}),
                         (0,0, {'account_id': self.account_expense_b.id, 'debit': 0.0, 'credit': 200.0})]
        })
        # Company B should be independent; if no budgets exist, posting allowed
        move.action_post()
        self.assertEqual(move.state, 'posted')
