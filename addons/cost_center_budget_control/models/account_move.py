from odoo import models, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _is_budget_override_allowed(self):
        """Check if the current user can apply budget overrides.
        
        Returns True only if:
        - user belongs to group_budget_override_manager
        - context contains explicit budget_override flag
        """
        has_override_group = self.env.user.has_group(
            'cost_center_budget_control.group_budget_override_manager'
        )
        override_context_flag = self.env.context.get('budget_override', False)
        return has_override_group and override_context_flag

    def _validate_budget_control(self):
        """Validate budget thresholds before posting a move.
        
        - Reads warning/critical/blocking thresholds from ir.config_parameter.
        - Uses control mode (blocking, warning_only) to decide action.
        - Evaluates projected usage on all impacted budget lines.
        - Raises UserError if moving to a blocked state (unless override allowed).
        - Returns a dict with:
            - 'warnings': list of warning messages
            - 'blocked_budgets': list of budget info dicts (name, percent, threshold)
        - Runs only for approved/draft budgets in the same company.
        - Does not modify posted amounts; only checks projected usage.
        """
        result = {'warnings': [], 'blocked_budgets': []}
        
        # Early exit: no company context or no thresholds definable
        if not self.company_id:
            return result
        
        # Get thresholds and control mode
        blocking_thr = float(self.env['ir.config_parameter'].sudo().get(
            'cost_center_budget_control.blocking_threshold', '100.0'))
        warning_thr = float(self.env['ir.config_parameter'].sudo().get(
            'cost_center_budget_control.warning_threshold', '0.0'))
        control_mode = self.env['ir.config_parameter'].sudo().get(
            'cost_center_budget_control.mode', 'warning_only')
        chatter_enabled = self.env['ir.config_parameter'].sudo().get(
            'cost_center_budget_control.chatter_enabled', 'True') == 'True'
        activity_enabled = self.env['ir.config_parameter'].sudo().get(
            'cost_center_budget_control.activity_enabled', 'True') == 'True'
        
        # If mode is not 'blocking' or 'warning_only', skip validation
        if control_mode not in ('blocking', 'warning_only'):
            return result
        
        # Get all budget lines impacted by this move (using existing helper)
        impacted_budget_lines = self.env['budget.plan.line']._get_impacted_budget_lines_from_move(self)
        if not impacted_budget_lines:
            return result
        
        # Aggregate projected increment per budget line
        projected_increment_by_budget_line = {}
        for line in self.line_ids.filtered(lambda l: l.analytic_distribution):
            distribution = line.analytic_distribution or {}
            for analytic_key, percent in distribution.items():
                # Parse the numeric key to integer
                analytic_account_id = int(analytic_key)
                # Compute raw amount contributed by this line for this percentage
                # Use abs() to correctly handle refunds/credit notes
                raw_amount = abs(line.balance) * (float(percent) / 100.0)
                # Distribute proportionally across impacted budget lines
                for bud_line in impacted_budget_lines:
                    projected_increment_by_budget_line[bud_line.id] = (
                        projected_increment_by_budget_line.get(bud_line.id, 0.0) +
                        raw_amount
                    )
        
        # Evaluate thresholds for each impacted budget line
        for bud_line in impacted_budget_lines:
            projected_inc = projected_increment_by_budget_line.get(bud_line.id, 0.0)
            projected_total_actual = bud_line.actual_amount + projected_inc
            # Guard against division by zero
            if bud_line.planned_amount and bud_line.planned_amount > 0:
                projected_usage_percent = (
                    projected_total_actual / bud_line.planned_amount * 100.0
                )
                if control_mode == 'blocking' and projected_usage_percent >= blocking_thr:
                    # Budget line would be blocked
                    budget_info = {
                        'name': bud_line.plan_id.name,
                        'percent': projected_usage_percent,
                        'threshold': blocking_thr
                    }
                    result['blocked_budgets'].append(budget_info)
                elif control_mode == 'warning_only' and projected_usage_percent >= warning_thr:
                    # Issue a warning message
                    warn_msg = _(
                        "Budget WARNING for %s: projected usage %.1f%% exceeds warning threshold %s%%"
                    ) % (bud_line.plan_id.name, projected_usage_percent, warning_thr)
                    result['warnings'].append(warn_msg)
        
        # Build aggregated block message if there are blocked budgets
        if result['blocked_budgets']:
            override_allowed = self._is_budget_override_allowed()
            if not override_allowed:
                # Build a clear, aggregated error message
                blocked_names = ', '.join([b['name'] for b in result['blocked_budgets']])
                msg = _(
                    "Budget Control BLOCKED: The following budgets would exceed their blocking threshold:\n%s\n\n"
                    "Contact a Budget Override Manager to request an exception."
                ) % blocked_names
                raise UserError(msg)
            else:
                # Override is allowed; add override messages
                for budget_info in result['blocked_budgets']:
                    override_msg = _(
                        "Budget OVERRIDE applied for %s (usage %.1f%% exceeds threshold %s%%)"
                    ) % (budget_info['name'], budget_info['percent'], budget_info['threshold'])
                    result['warnings'].append(override_msg)
        
        # Store activity requirement flag if blocking occurred and activity is enabled
        if result['blocked_budgets'] and activity_enabled:
            result['should_create_activity'] = True
        
        return result

    def _post(self, **kwargs):
        """Overrides the standard _post method to integrate budget control validation and actual amount recomputation.
        This method acts as the main integration point for budget control checks and triggers re-calculation
        of budget actual amounts for impacted budget lines after an account move is posted or unposted.

        Posting hook that validates budget control before posting.
        
        1. Validate budget thresholds (may raise UserError to block).
        2. Execute normal posting logic.
        3. Recompute affected budget line actual amounts.
        4. Post any warning messages as chatter and create activity if needed.
        Returns the standard Odoo posting result.
        """
        # Validate budget thresholds (may raise UserError to block)
        validation_result = self._validate_budget_control()
        
        # Continue with the standard posting flow
        res = super()._post(**kwargs)
        
        # Recompute affected budget line actual amounts
        impacted = self.env["budget.plan.line"]._get_impacted_budget_lines_from_move(self)
        if impacted:
            self.env["budget.plan.line"]._recompute_actual_amount_batch(impacted)
        
        # Post warning messages as chatter (if any)
        for warning in validation_result.get('warnings', []):
            self.message_post(body=warning)
        
        # Create activity for override managers if blocking occurred
        if validation_result.get('should_create_activity'):
            self._create_budget_override_activity(validation_result['blocked_budgets'])
        
        return res

    def _create_budget_override_activity(self, blocked_budgets):
        """Create a mail.activity for budget override managers.
        
        Single activity per move, summarizing all exceeded budgets.
        """
        # Find all users in the override manager group for this company
        override_manager_group = self.env.ref(
            'cost_center_budget_control.group_budget_override_manager',
            raise_if_not_found=False
        )
        if not override_manager_group:
            return
        
        # Filter managers to those in the same company
        managers = self.env['res.users'].search([
            ('groups_id', 'in', override_manager_group.id),
            ('company_id', '=', self.company_id.id),
        ])
        if not managers:
            return
        
        # Build activity summary
        blocked_names = ', '.join([b['name'] for b in blocked_budgets])
        activity_summary = _("Budget Override Required: %s") % self.name
        activity_note = _(
            "The following budgets exceeded their blocking threshold:\n%s\n\n"
            "Move: %s (Amount: %s %s)"
        ) % (blocked_names, self.name, self.amount_total, self.currency_id.name)
        
        # Create activity for the first manager (Odoo will handle assignment)
        self.activity_schedule(
            activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
            summary=activity_summary,
            note=activity_note,
            user_id=managers[0].id,
        )


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def write(self, vals):
        res = super().write(vals)
        if "analytic_distribution" not in vals:
            return res

        moves = self.mapped("move_id").filtered(lambda m: m.state == "posted")
        for move in moves:
            impacted = self.env["budget.plan.line"]._get_impacted_budget_lines_from_move(move)
            if impacted:
                self.env["budget.plan.line"]._recompute_actual_amount_batch(impacted)
        return res
