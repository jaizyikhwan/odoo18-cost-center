# -*- coding: utf-8 -*-
from hashlib import sha1
from psycopg2 import IntegrityError

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round


class BudgetAllocation(models.Model):
    _name = "budget.allocation"
    _description = "Overhead Allocation Record"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "allocation_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(string="Description", required=True, tracking=True)
    ref = fields.Char(string="Reference", readonly=True, index=True, copy=False)

    source_cost_center_id = fields.Many2one(
        "cost.center",
        string="Source Cost Center",
        required=True,
        ondelete="restrict",
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        tracking=True,
    )

    target_cost_center_ids = fields.Many2many(
        "cost.center",
        "budget_allocation_cost_center_rel",
        "allocation_id",
        "cost_center_id",
        string="Target Cost Centers",
        check_company=True,
        tracking=True,
    )

    line_ids = fields.One2many(
        "budget.allocation.line",
        "allocation_id",
        string="Allocation Lines",
    )

    allocation_rules = fields.Json(
        string="Allocation Rules",
        compute="_compute_allocation_rules",
        store=True,
        default=dict,
    )

    amount_base = fields.Monetary(
        string="Base Amount",
        required=True,
        currency_field="currency_id",
        tracking=True,
    )

    allocation_date = fields.Date(
        string="Allocation Date",
        required=True,
        default=fields.Date.today,
        tracking=True,
    )

    overhead_account_id = fields.Many2one(
        "account.account",
        string="Overhead Account (Credit)",
        required=True,
        check_company=True,
        domain=[("account_type", "in", ("expense", "expense_depreciation", "expense_direct_cost", "other"))],
        help="Account to be credited (Source pool).",
    )

    target_account_id = fields.Many2one(
        "account.account",
        string="Target Account (Debit)",
        required=True,
        check_company=True,
        domain=[("account_type", "in", ("expense", "expense_depreciation", "expense_direct_cost"))],
        help="Account to be debited for target cost centers.",
    )

    journal_id = fields.Many2one(
        "account.journal",
        string="Journal",
        required=True,
        check_company=True,
        domain=[("type", "=", "general")],
        default=lambda self: self.env["account.journal"].search([
            ("type", "=", "general"),
            ("company_id", "=", self.env.company.id),
        ], limit=1),
    )

    move_id = fields.Many2one(
        "account.move",
        string="Journal Entry",
        ondelete="restrict",
        check_company=True,
        readonly=True,
    )

    reversal_move_id = fields.Many2one(
        "account.move",
        string="Reversal Entry",
        ondelete="restrict",
        check_company=True,
        readonly=True,
    )

    state = fields.Selection([
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("cancelled", "Cancelled"),
    ], string="Status", default="draft", tracking=True, readonly=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        readonly=True,
        store=True,
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------

    @api.constrains("amount_base")
    def _check_amount_base(self):
        for rec in self:
            if rec.amount_base <= 0.0:
                raise ValidationError(_("Base Amount must be strictly positive."))

    @api.depends("line_ids", "line_ids.cost_center_id", "line_ids.percentage")
    def _compute_allocation_rules(self):
        for rec in self:
            rules = {}
            for line in rec.line_ids:
                rules[str(line.cost_center_id.id)] = line.percentage
            rec.allocation_rules = rules

    # -------------------------------------------------------------------------
    # CORE LOGIC
    # -------------------------------------------------------------------------

    def compute_allocation(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Allocation lines are not defined."))

        allocation_data = []
        total_percent = 0.0

        for line in self.line_ids:
            cost_center = line.cost_center_id
            if not cost_center.exists():
                continue

            raw_amount = (line.percentage / 100.0) * self.amount_base
            allocation_data.append({
                "cost_center": cost_center,
                "percent": line.percentage,
                "raw_amount": raw_amount,
            })
            total_percent += line.percentage

        if abs(total_percent - 100.0) > 0.01:
            raise ValidationError(
                _("Allocation percentages must sum to 100%%. Current total: %s%%") % total_percent
            )

        if not allocation_data:
            raise UserError(_("No valid target cost centers found in allocation lines."))

        return allocation_data

    def build_journal_lines(self, allocation_data):
        """Step 2: Construct perfectly balanced move lines.

        Balancing strategy:
        - credit_total is the precisely rounded pool credit amount.
        - Each target debit is individually rounded.
        - The last target absorbs any rounding residual to guarantee:
              sum(debits) == credit_total exactly.
        - An explicit assertion validates balance before return.

        Analytic distribution:
        - Uses Odoo 18 analytic_distribution JSONB field.
        - Format: {str(analytic_account_id): 100.0} for 100% attribution.
        - Consistent with actual_amount SQL aggregation in budget_plan.py.
        """
        self.ensure_one()
        precision = self.currency_id.decimal_places
        credit_total = float_round(self.amount_base, precision_digits=precision)

        lines = []
        running_debit = 0.0

        # Debit side (Targets) — process all but the last
        for idx, data in enumerate(allocation_data):
            is_last = (idx == len(allocation_data) - 1)

            if is_last:
                # Last line absorbs rounding residual to guarantee balance
                debit_amount = float_round(credit_total - running_debit, precision_digits=precision)
            else:
                debit_amount = float_round(data["raw_amount"], precision_digits=precision)

            if debit_amount == 0.0:
                if not is_last:
                    continue
                # Last-line residual is zero — this is fine; skip silently
                continue

            running_debit = float_round(running_debit + debit_amount, precision_digits=precision)

            analytic_cc = data["cost_center"].analytic_account_id
            analytic_distribution = (
                {str(analytic_cc.id): 100.0} if analytic_cc else False
            )

            lines.append((0, 0, {
                "name": _("Allocated Overhead: %s") % self.name,
                "account_id": self.target_account_id.id,
                "debit": debit_amount,
                "credit": 0.0,
                "analytic_distribution": analytic_distribution,
                "company_id": self.company_id.id,
            }))

        # Credit side (Pool) — single line crediting the full pool amount
        analytic_src = self.source_cost_center_id.analytic_account_id
        analytic_distribution_src = (
            {str(analytic_src.id): 100.0} if analytic_src else False
        )

        lines.append((0, 0, {
            "name": _("Allocation Pool: %s") % self.name,
            "account_id": self.overhead_account_id.id,
            "debit": 0.0,
            "credit": credit_total,
            "analytic_distribution": analytic_distribution_src,
            "company_id": self.company_id.id,
        }))

        # Safety assertion: sum of debits must equal credit_total exactly
        total_debits = float_round(
            sum(
                cmd[2]["debit"]
                for cmd in lines
                if cmd[2].get("debit", 0.0) > 0.0
            ),
            precision_digits=precision,
        )
        if abs(total_debits - credit_total) > 10 ** (-precision):
            raise ValidationError(
                _("Internal error: allocation journal entry is not balanced "
                  "(debits: %s, credits: %s). Please contact your administrator.")
                % (total_debits, credit_total)
            )

        return lines

    def create_move(self, lines):
        """Step 3: Create account.move with idempotency check."""
        self.ensure_one()
        rule_fingerprint = sha1(
            repr(sorted((self.allocation_rules or {}).items())).encode()
        ).hexdigest()[:10]
        deterministic_ref = (
            f"ALLOC/{self.company_id.id}/{self.id}/{self.source_cost_center_id.id}/"
            f"{self.allocation_date}/{rule_fingerprint}"
        )

        existing_move = self.env["account.move"].search([
            ("ref", "=", deterministic_ref),
            ("company_id", "=", self.company_id.id),
            ("state", "!=", "cancel"),
        ], limit=1)

        if existing_move:
            return existing_move

        try:
            with self.env.cr.savepoint():
                move = self.env["account.move"].create({
                    "journal_id": self.journal_id.id,
                    "date": self.allocation_date,
                    "ref": deterministic_ref,
                    "move_type": "entry",
                    "line_ids": lines,
                    "company_id": self.company_id.id,
                })
                return move
        except IntegrityError:
            return self.env["account.move"].search([
                ("ref", "=", deterministic_ref),
                ("company_id", "=", self.company_id.id),
                ("state", "!=", "cancel"),
            ], limit=1)

    def post_move(self, move):
        """Step 4: Post the move."""
        if move.state == "draft":
            move.action_post()
        return True

    def action_allocate(self):
        """Main entry point for allocation process."""
        for rec in self:
            if rec.state != "draft":
                continue

            data = rec.compute_allocation()
            lines = rec.build_journal_lines(data)
            move = rec.create_move(lines)
            rec.post_move(move)

            rec.write({
                "move_id": move.id,
                "state": "posted",
                "ref": move.ref,
            })

    def action_cancel(self):
        for rec in self:
            if rec.move_id and rec.move_id.state == "posted":
                reversal = rec.move_id._reverse_moves(
                    default_values_list=[{
                        "ref": _("Reversal of allocation: %s") % rec.name,
                        "date": fields.Date.today(),
                    }],
                    cancel=True,
                )
                rec.reversal_move_id = reversal.id
            rec.write({"state": "cancelled"})

    # -------------------------------------------------------------------------
    # ORM OVERRIDES
    # -------------------------------------------------------------------------

    def unlink(self):
        for rec in self:
            if rec.state == "posted":
                raise UserError(_("You cannot delete a posted allocation record."))
        return super().unlink()
