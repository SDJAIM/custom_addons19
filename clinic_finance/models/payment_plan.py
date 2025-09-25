# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class PaymentPlan(models.Model):
    _name = 'clinic.payment.plan'
    _description = 'Patient Payment Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'name'
    
    # Basic Information
    name = fields.Char(
        string='Plan Reference',
        required=True,
        readonly=True,
        copy=False,
        default='New',
        tracking=True
    )
    
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        tracking=True,
        index=True,
        states={'active': [('readonly', True)], 'completed': [('readonly', True)]}
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='patient_id.partner_id',
        store=True,
        readonly=True
    )
    
    # Plan Details
    total_amount = fields.Float(
        string='Total Amount',
        required=True,
        tracking=True,
        digits='Product Price',
        states={'active': [('readonly', True)], 'completed': [('readonly', True)]}
    )
    
    down_payment = fields.Float(
        string='Down Payment',
        digits='Product Price',
        tracking=True,
        states={'active': [('readonly', True)], 'completed': [('readonly', True)]}
    )
    
    financed_amount = fields.Float(
        string='Financed Amount',
        compute='_compute_financed_amount',
        store=True,
        digits='Product Price'
    )
    
    installments = fields.Integer(
        string='Number of Installments',
        required=True,
        tracking=True,
        states={'active': [('readonly', True)], 'completed': [('readonly', True)]}
    )
    
    installment_amount = fields.Float(
        string='Installment Amount',
        compute='_compute_installment_amount',
        store=True,
        digits='Product Price'
    )
    
    payment_frequency = fields.Selection([
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
    ], string='Payment Frequency', default='monthly', required=True, tracking=True)
    
    # Dates
    start_date = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
        default=fields.Date.context_today,
        states={'active': [('readonly', True)], 'completed': [('readonly', True)]}
    )
    
    end_date = fields.Date(
        string='End Date',
        compute='_compute_end_date',
        store=True
    )
    
    # Interest
    interest_rate = fields.Float(
        string='Interest Rate (%)',
        default=0.0,
        tracking=True,
        states={'active': [('readonly', True)], 'completed': [('readonly', True)]}
    )
    
    total_interest = fields.Float(
        string='Total Interest',
        compute='_compute_interest',
        store=True,
        digits='Product Price'
    )
    
    total_payable = fields.Float(
        string='Total Payable',
        compute='_compute_total_payable',
        store=True,
        digits='Product Price'
    )
    
    # Related Documents
    invoice_ids = fields.Many2many(
        'clinic.invoice',
        string='Related Invoices',
        states={'completed': [('readonly', True)]}
    )
    
    appointment_ids = fields.Many2many(
        'clinic.appointment',
        string='Related Appointments'
    )
    
    # Payment Lines
    payment_line_ids = fields.One2many(
        'clinic.payment.plan.line',
        'plan_id',
        string='Payment Schedule'
    )
    
    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('defaulted', 'Defaulted'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True, index=True)
    
    # Payment Progress
    amount_paid = fields.Float(
        string='Amount Paid',
        compute='_compute_payment_progress',
        store=True,
        digits='Product Price'
    )
    
    amount_due = fields.Float(
        string='Amount Due',
        compute='_compute_payment_progress',
        store=True,
        digits='Product Price'
    )
    
    payment_progress = fields.Float(
        string='Payment Progress (%)',
        compute='_compute_payment_progress',
        store=True
    )
    
    overdue_amount = fields.Float(
        string='Overdue Amount',
        compute='_compute_overdue',
        store=True,
        digits='Product Price'
    )
    
    overdue_days = fields.Integer(
        string='Days Overdue',
        compute='_compute_overdue',
        store=True
    )
    
    # Agreement
    agreement_signed = fields.Boolean(
        string='Agreement Signed',
        tracking=True
    )
    
    agreement_date = fields.Date(
        string='Agreement Date',
        tracking=True
    )
    
    agreement_document = fields.Binary(
        string='Agreement Document',
        attachment=True
    )
    
    # Notes
    notes = fields.Text(
        string='Internal Notes'
    )
    
    terms_conditions = fields.Text(
        string='Terms & Conditions'
    )
    
    @api.depends('total_amount', 'down_payment')
    def _compute_financed_amount(self):
        for plan in self:
            plan.financed_amount = plan.total_amount - plan.down_payment
    
    @api.depends('financed_amount', 'installments', 'interest_rate')
    def _compute_installment_amount(self):
        for plan in self:
            if plan.installments > 0:
                if plan.interest_rate > 0:
                    # Calculate with interest (simple interest for now)
                    monthly_rate = plan.interest_rate / 100 / 12
                    plan.installment_amount = (plan.financed_amount * monthly_rate * 
                                              (1 + monthly_rate) ** plan.installments) / \
                                             ((1 + monthly_rate) ** plan.installments - 1)
                else:
                    plan.installment_amount = plan.financed_amount / plan.installments
            else:
                plan.installment_amount = 0.0
    
    @api.depends('installment_amount', 'installments', 'financed_amount')
    def _compute_interest(self):
        for plan in self:
            total_payments = plan.installment_amount * plan.installments
            plan.total_interest = total_payments - plan.financed_amount
    
    @api.depends('total_amount', 'total_interest')
    def _compute_total_payable(self):
        for plan in self:
            plan.total_payable = plan.total_amount + plan.total_interest
    
    @api.depends('start_date', 'installments', 'payment_frequency')
    def _compute_end_date(self):
        for plan in self:
            if plan.start_date and plan.installments:
                if plan.payment_frequency == 'weekly':
                    delta = relativedelta(weeks=plan.installments)
                elif plan.payment_frequency == 'biweekly':
                    delta = relativedelta(weeks=plan.installments * 2)
                elif plan.payment_frequency == 'quarterly':
                    delta = relativedelta(months=plan.installments * 3)
                else:  # monthly
                    delta = relativedelta(months=plan.installments)
                
                plan.end_date = plan.start_date + delta
            else:
                plan.end_date = False
    
    @api.depends('payment_line_ids.amount_paid', 'payment_line_ids.state')
    def _compute_payment_progress(self):
        for plan in self:
            paid_lines = plan.payment_line_ids.filtered(lambda l: l.state == 'paid')
            plan.amount_paid = sum(paid_lines.mapped('amount_paid')) + plan.down_payment
            plan.amount_due = plan.total_payable - plan.amount_paid
            
            if plan.total_payable > 0:
                plan.payment_progress = (plan.amount_paid / plan.total_payable) * 100
            else:
                plan.payment_progress = 0.0
    
    @api.depends('payment_line_ids.due_date', 'payment_line_ids.state', 'payment_line_ids.amount')
    def _compute_overdue(self):
        today = fields.Date.today()
        for plan in self:
            overdue_lines = plan.payment_line_ids.filtered(
                lambda l: l.state == 'pending' and l.due_date < today
            )
            
            plan.overdue_amount = sum(overdue_lines.mapped('amount'))
            
            if overdue_lines:
                earliest_overdue = min(overdue_lines.mapped('due_date'))
                plan.overdue_days = (today - earliest_overdue).days
            else:
                plan.overdue_days = 0
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('clinic.payment.plan') or 'New'
        return super().create(vals)
    
    @api.constrains('installments')
    def _check_installments(self):
        for plan in self:
            if plan.installments <= 0:
                raise ValidationError(_("Number of installments must be greater than zero."))
    
    @api.constrains('down_payment', 'total_amount')
    def _check_down_payment(self):
        for plan in self:
            if plan.down_payment > plan.total_amount:
                raise ValidationError(_("Down payment cannot exceed total amount."))
    
    def action_generate_schedule(self):
        """Generate payment schedule"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_("Schedule can only be generated for draft plans."))
        
        # Clear existing lines
        self.payment_line_ids.unlink()
        
        # Generate new schedule
        current_date = self.start_date
        
        for i in range(self.installments):
            # Calculate due date
            if self.payment_frequency == 'weekly':
                due_date = current_date + relativedelta(weeks=i)
            elif self.payment_frequency == 'biweekly':
                due_date = current_date + relativedelta(weeks=i * 2)
            elif self.payment_frequency == 'quarterly':
                due_date = current_date + relativedelta(months=i * 3)
            else:  # monthly
                due_date = current_date + relativedelta(months=i)
            
            # Create payment line
            self.env['clinic.payment.plan.line'].create({
                'plan_id': self.id,
                'sequence': i + 1,
                'due_date': due_date,
                'amount': self.installment_amount,
                'state': 'pending',
            })
        
        return True
    
    def action_approve(self):
        """Approve payment plan"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_("Only draft plans can be approved."))
        
        if not self.payment_line_ids:
            raise UserError(_("Please generate payment schedule first."))
        
        self.state = 'approved'
        
        return True
    
    def action_activate(self):
        """Activate payment plan"""
        self.ensure_one()
        
        if self.state != 'approved':
            raise UserError(_("Only approved plans can be activated."))
        
        if not self.agreement_signed:
            raise UserError(_("Agreement must be signed before activation."))
        
        self.state = 'active'
        
        # Create follow-up activities for payments
        for line in self.payment_line_ids:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=f'Payment due: {line.amount:.2f}',
                date_deadline=line.due_date,
                user_id=self.env.user.id
            )
        
        return True
    
    def action_hold(self):
        """Put plan on hold"""
        self.ensure_one()
        
        if self.state != 'active':
            raise UserError(_("Only active plans can be put on hold."))
        
        self.state = 'on_hold'
        
        return True
    
    def action_resume(self):
        """Resume plan from hold"""
        self.ensure_one()
        
        if self.state != 'on_hold':
            raise UserError(_("Only on-hold plans can be resumed."))
        
        self.state = 'active'
        
        return True
    
    def action_mark_defaulted(self):
        """Mark plan as defaulted"""
        self.ensure_one()
        
        if self.state not in ['active', 'on_hold']:
            raise UserError(_("Invalid state for marking as defaulted."))
        
        self.state = 'defaulted'
        
        # Send notification
        self.message_post(
            body=f"Payment plan {self.name} has been marked as defaulted. Overdue amount: {self.overdue_amount:.2f}",
            subject="Payment Plan Defaulted",
            message_type='notification'
        )
        
        return True
    
    def action_complete(self):
        """Mark plan as completed"""
        self.ensure_one()
        
        if self.amount_due > 0:
            raise UserError(_("Cannot complete plan with outstanding balance."))
        
        self.state = 'completed'
        
        return True
    
    def action_cancel(self):
        """Cancel payment plan"""
        self.ensure_one()
        
        if self.state in ['completed', 'cancelled']:
            raise UserError(_("Cannot cancel plan in current state."))
        
        self.state = 'cancelled'
        
        return True
    
    @api.model
    def check_overdue_plans(self):
        """Cron job to check for overdue payment plans"""
        overdue_plans = self.search([
            ('state', '=', 'active'),
            ('overdue_days', '>', 30),
        ])
        
        for plan in overdue_plans:
            # Create warning activity
            plan.activity_schedule(
                'mail.mail_activity_data_warning',
                summary=f'Payment plan overdue by {plan.overdue_days} days',
                user_id=plan.create_uid.id
            )
            
            # Auto-default if overdue by more than 60 days
            if plan.overdue_days > 60:
                plan.action_mark_defaulted()


class PaymentPlanLine(models.Model):
    _name = 'clinic.payment.plan.line'
    _description = 'Payment Plan Line'
    _order = 'due_date, sequence'
    
    plan_id = fields.Many2one(
        'clinic.payment.plan',
        string='Payment Plan',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    sequence = fields.Integer(
        string='#',
        required=True
    )
    
    due_date = fields.Date(
        string='Due Date',
        required=True,
        index=True
    )
    
    amount = fields.Float(
        string='Amount Due',
        required=True,
        digits='Product Price'
    )
    
    amount_paid = fields.Float(
        string='Amount Paid',
        digits='Product Price',
        default=0.0
    )
    
    payment_date = fields.Date(
        string='Payment Date'
    )
    
    payment_reference = fields.Char(
        string='Payment Reference'
    )
    
    state = fields.Selection([
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ], string='Status', default='pending', required=True)
    
    days_overdue = fields.Integer(
        string='Days Overdue',
        compute='_compute_days_overdue'
    )
    
    @api.depends('due_date', 'state')
    def _compute_days_overdue(self):
        today = fields.Date.today()
        for line in self:
            if line.state == 'pending' and line.due_date < today:
                line.days_overdue = (today - line.due_date).days
                line.state = 'overdue'
            else:
                line.days_overdue = 0
    
    def action_record_payment(self):
        """Record payment for this installment"""
        self.ensure_one()
        
        return {
            'name': _('Record Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.payment.plan.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_plan_line_id': self.id,
                'default_amount': self.amount - self.amount_paid,
            }
        }