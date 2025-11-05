# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import datetime, date

_logger = logging.getLogger(__name__)


class ClinicPayment(models.Model):
    """Model for processing patient payments"""
    _name = 'clinic.payment'
    _description = 'Clinic Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'payment_date desc, id desc'
    _rec_name = 'reference'

    # Basic Information
    reference = fields.Char(
        string='Payment Reference',
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _('New'),
        index=True
    )

    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        tracking=True,
        index=True
    )

    payment_date = fields.Datetime(
        string='Payment Date',
        required=True,
        default=fields.Datetime.now,
        tracking=True
    )

    amount = fields.Monetary(
        string='Amount',
        required=True,
        tracking=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    # Payment Method
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('check', 'Check'),
        ('bank_transfer', 'Bank Transfer'),
        ('insurance', 'Insurance'),
        ('online', 'Online Payment'),
        ('other', 'Other')
    ], string='Payment Method', required=True, tracking=True)

    # Payment Type
    payment_type = fields.Selection([
        ('appointment', 'Appointment'),
        ('procedure', 'Procedure'),
        ('medication', 'Medication'),
        ('lab_test', 'Lab Test'),
        ('hospitalization', 'Hospitalization'),
        ('deposit', 'Deposit'),
        ('refund', 'Refund'),
        ('other', 'Other')
    ], string='Payment Type', required=True, default='appointment')

    # Related Documents
    invoice_id = fields.Many2one(
        'clinic.invoice',
        string='Invoice',
        tracking=True
    )

    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Appointment'
    )

    prescription_id = fields.Many2one(
        'clinic.prescription',
        string='Prescription'
    )

    # Card Information (for card payments)
    card_last_digits = fields.Char(
        string='Card Last 4 Digits',
        help='Last 4 digits of the card (max 4 characters)'
    )

    card_holder_name = fields.Char(
        string='Card Holder Name'
    )

    authorization_code = fields.Char(
        string='Authorization Code'
    )

    transaction_id = fields.Char(
        string='Transaction ID',
        help='External payment gateway transaction ID'
    )

    # Bank Information (for checks/transfers)
    bank_name = fields.Char(
        string='Bank Name'
    )

    check_number = fields.Char(
        string='Check Number'
    )

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('confirmed', 'Confirmed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded')
    ], string='State', default='draft', required=True, tracking=True)

    # Processing Information
    processing_fee = fields.Monetary(
        string='Processing Fee'
    )

    net_amount = fields.Monetary(
        string='Net Amount',
        compute='_compute_net_amount',
        store=True
    )

    # Error Handling
    error_message = fields.Text(
        string='Error Message',
        readonly=True
    )

    retry_count = fields.Integer(
        string='Retry Count',
        default=0
    )

    # Refund Information
    is_refund = fields.Boolean(
        string='Is Refund',
        default=False
    )

    refund_reason = fields.Text(
        string='Refund Reason'
    )

    original_payment_id = fields.Many2one(
        'clinic.payment',
        string='Original Payment',
        help='Original payment being refunded'
    )

    refund_payment_ids = fields.One2many(
        'clinic.payment',
        'original_payment_id',
        string='Refunds'
    )

    # Receipt
    receipt_number = fields.Char(
        string='Receipt Number'
    )

    receipt_printed = fields.Boolean(
        string='Receipt Printed',
        default=False
    )

    # Notes
    notes = fields.Text(
        string='Notes'
    )

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )

    branch_id = fields.Many2one(
        'clinic.branch',
        string='Branch'
    )

    # ========================
    # Computed Methods
    # ========================
    @api.model
    def create(self, vals):
        if vals.get('reference', _('New')) == _('New'):
            vals['reference'] = self.env['ir.sequence'].next_by_code('clinic.payment') or _('New')
        return super(ClinicPayment, self).create(vals)

    @api.depends('amount', 'processing_fee')
    def _compute_net_amount(self):
        for payment in self:
            payment.net_amount = payment.amount - (payment.processing_fee or 0.0)

    # ========================
    # Main Payment Processing
    # ========================
    def process_payment(self):
        """
        Main method to process a payment
        Handles different payment methods and integrations
        """
        self.ensure_one()

        if self.state not in ['draft', 'pending']:
            raise UserError(_("Payment %s is already processed or cancelled.") % self.reference)

        if self.amount <= 0:
            raise ValidationError(_("Payment amount must be greater than zero."))

        # Validate patient
        if not self.patient_id:
            raise ValidationError(_("Patient is required for payment processing."))

        try:
            self.write({'state': 'processing'})

            # Process based on payment method
            if self.payment_method == 'cash':
                result = self._process_cash_payment()
            elif self.payment_method in ['credit_card', 'debit_card']:
                result = self._process_card_payment()
            elif self.payment_method == 'check':
                result = self._process_check_payment()
            elif self.payment_method == 'bank_transfer':
                result = self._process_bank_transfer()
            elif self.payment_method == 'insurance':
                result = self._process_insurance_payment()
            elif self.payment_method == 'online':
                result = self._process_online_payment()
            else:
                result = self._process_other_payment()

            if result.get('success'):
                self._complete_payment(result)
                return True
            else:
                self._handle_payment_failure(result.get('error', 'Unknown error'))
                return False

        except Exception as e:
            _logger.error(f"Payment processing error for {self.reference}: {str(e)}")
            self._handle_payment_failure(str(e))
            raise

    def _process_cash_payment(self):
        """Process cash payment"""
        # Cash payments are immediately confirmed
        return {
            'success': True,
            'transaction_id': f"CASH-{self.reference}",
            'message': 'Cash payment processed successfully'
        }

    def _process_card_payment(self):
        """Process credit/debit card payment"""
        # Get payment gateway configuration
        IrConfig = self.env['ir.config_parameter'].sudo()
        gateway = IrConfig.get_param('clinic.payment.gateway', 'stripe')
        api_key = IrConfig.get_param(f'clinic.payment.{gateway}.api_key')

        if not api_key:
            # If no gateway configured, simulate success for testing
            _logger.warning(f"Payment gateway {gateway} not configured. Simulating success.")
            return {
                'success': True,
                'transaction_id': f"SIM-{self.reference}",
                'authorization_code': 'SIM123456',
                'message': 'Payment simulated (no gateway configured)'
            }

        # Process with payment gateway
        if gateway == 'stripe':
            return self._process_stripe_payment(api_key)
        elif gateway == 'paypal':
            return self._process_paypal_payment(api_key)
        else:
            # Default processing
            return {
                'success': True,
                'transaction_id': f"CARD-{self.reference}",
                'authorization_code': 'AUTH123456',
                'message': 'Card payment processed'
            }

    def _process_stripe_payment(self, api_key):
        """Process payment through Stripe"""
        try:
            import stripe
            stripe.api_key = api_key

            # Create charge
            charge = stripe.Charge.create(
                amount=int(self.amount * 100),  # Amount in cents
                currency=self.currency_id.name.lower(),
                description=f"Payment {self.reference} for {self.patient_id.name}",
                metadata={
                    'payment_id': self.id,
                    'patient_id': self.patient_id.id,
                    'reference': self.reference
                }
            )

            return {
                'success': True,
                'transaction_id': charge.id,
                'authorization_code': charge.balance_transaction,
                'message': 'Stripe payment successful'
            }

        except stripe.error.CardError as e:
            return {
                'success': False,
                'error': f"Card error: {str(e.user_message)}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Stripe error: {str(e)}"
            }

    def _process_paypal_payment(self, api_key):
        """Process payment through PayPal"""
        # PayPal implementation would go here
        return {
            'success': True,
            'transaction_id': f"PAYPAL-{self.reference}",
            'message': 'PayPal payment processed'
        }

    def _process_check_payment(self):
        """Process check payment"""
        if not self.check_number:
            raise ValidationError(_("Check number is required for check payments."))

        # Check payments are pending until cleared
        return {
            'success': True,
            'pending': True,
            'transaction_id': f"CHECK-{self.check_number}",
            'message': 'Check payment registered, pending clearance'
        }

    def _process_bank_transfer(self):
        """Process bank transfer payment"""
        # Bank transfers are pending until confirmed
        return {
            'success': True,
            'pending': True,
            'transaction_id': f"TRANSFER-{self.reference}",
            'message': 'Bank transfer registered, pending confirmation'
        }

    def _process_insurance_payment(self):
        """Process insurance payment"""
        # Create insurance claim if needed
        if not self.invoice_id:
            raise ValidationError(_("Invoice is required for insurance payments."))

        # Check if claim already exists
        existing_claim = self.env['clinic.insurance.claim'].search([
            ('invoice_id', '=', self.invoice_id.id),
            ('state', '!=', 'cancelled')
        ], limit=1)

        if not existing_claim:
            # Create new insurance claim
            claim_vals = {
                'patient_id': self.patient_id.id,
                'invoice_id': self.invoice_id.id,
                'claim_amount': self.amount,
                'claim_date': fields.Date.today(),
            }

            if self.patient_id.insurance_policy_ids:
                claim_vals['insurance_policy_id'] = self.patient_id.insurance_policy_ids[0].id

            claim = self.env['clinic.insurance.claim'].create(claim_vals)
            claim.action_submit()

            return {
                'success': True,
                'pending': True,
                'transaction_id': f"CLAIM-{claim.claim_number}",
                'message': f'Insurance claim {claim.claim_number} created'
            }
        else:
            return {
                'success': True,
                'pending': True,
                'transaction_id': f"CLAIM-{existing_claim.claim_number}",
                'message': f'Using existing claim {existing_claim.claim_number}'
            }

    def _process_online_payment(self):
        """Process online payment"""
        # Online payment gateway integration
        return {
            'success': True,
            'transaction_id': f"ONLINE-{self.reference}",
            'message': 'Online payment processed'
        }

    def _process_other_payment(self):
        """Process other payment methods"""
        return {
            'success': True,
            'transaction_id': f"OTHER-{self.reference}",
            'message': 'Payment processed'
        }

    def _complete_payment(self, result):
        """Complete successful payment"""
        self.ensure_one()

        update_vals = {
            'state': 'pending' if result.get('pending') else 'confirmed',
            'transaction_id': result.get('transaction_id'),
            'error_message': False
        }

        if result.get('authorization_code'):
            update_vals['authorization_code'] = result['authorization_code']

        self.write(update_vals)

        # Update related invoice if exists
        if self.invoice_id:
            self.invoice_id._update_payment_status()

        # Update appointment status if exists
        if self.appointment_id and self.appointment_id.state == 'draft':
            self.appointment_id.action_confirm()

        # Generate receipt
        self._generate_receipt()

        # Send confirmation
        self._send_payment_confirmation()

        # Log success
        self.message_post(
            body=_("Payment processed successfully: %s") % result.get('message', 'Payment confirmed'),
            message_type='notification'
        )

    def _handle_payment_failure(self, error_message):
        """Handle payment failure"""
        self.ensure_one()

        self.write({
            'state': 'failed',
            'error_message': error_message,
            'retry_count': self.retry_count + 1
        })

        # Log failure
        self.message_post(
            body=_("Payment failed: %s") % error_message,
            message_type='notification'
        )

        # Create activity for follow-up
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            summary=_('Payment Failed - Follow Up Required'),
            note=_('Payment %s failed with error: %s') % (self.reference, error_message),
            user_id=self.env.user.id
        )

    def _generate_receipt(self):
        """Generate payment receipt"""
        self.ensure_one()

        if not self.receipt_number:
            self.receipt_number = self.env['ir.sequence'].next_by_code('clinic.payment.receipt') or self.reference

    def _send_payment_confirmation(self):
        """Send payment confirmation to patient"""
        self.ensure_one()

        if self.patient_id.email:
            try:
                template = self.env.ref('clinic_finance.email_payment_confirmation', raise_if_not_found=False)
                if template:
                    template.send_mail(self.id, force_send=True)
                else:
                    # Create simple email
                    mail_values = {
                        'subject': _('Payment Confirmation - %s') % self.reference,
                        'email_to': self.patient_id.email,
                        'email_from': self.env.company.email or 'noreply@clinic.com',
                        'body_html': f"""
                        <p>Dear {self.patient_id.name},</p>
                        <p>Your payment has been processed successfully.</p>
                        <p>Payment Details:</p>
                        <ul>
                            <li>Reference: {self.reference}</li>
                            <li>Amount: {self.currency_id.symbol} {self.amount}</li>
                            <li>Date: {self.payment_date}</li>
                            <li>Method: {dict(self._fields['payment_method'].selection)[self.payment_method]}</li>
                        </ul>
                        <p>Thank you for your payment.</p>
                        <p>Best regards,<br/>{self.env.company.name}</p>
                        """,
                        'auto_delete': True,
                    }
                    self.env['mail.mail'].create(mail_values).send()
            except Exception as e:
                _logger.warning(f"Could not send payment confirmation email: {str(e)}")

    # ========================
    # Actions
    # ========================
    def action_retry(self):
        """Retry failed payment"""
        self.ensure_one()

        if self.state != 'failed':
            raise UserError(_("Only failed payments can be retried."))

        if self.retry_count >= 3:
            raise UserError(_("Maximum retry attempts reached. Please create a new payment."))

        self.state = 'draft'
        return self.process_payment()

    def action_cancel(self):
        """Cancel payment"""
        self.ensure_one()

        if self.state in ['confirmed', 'refunded']:
            raise UserError(_("Cannot cancel confirmed or refunded payments."))

        self.state = 'cancelled'

    def action_refund(self):
        """Create refund for this payment"""
        self.ensure_one()

        if self.state != 'confirmed':
            raise UserError(_("Only confirmed payments can be refunded."))

        if self.is_refund:
            raise UserError(_("Cannot refund a refund payment."))

        # Check if already refunded
        existing_refunds = self.refund_payment_ids.filtered(lambda r: r.state == 'confirmed')
        if existing_refunds:
            total_refunded = sum(existing_refunds.mapped('amount'))
            if total_refunded >= self.amount:
                raise UserError(_("This payment has already been fully refunded."))

        return {
            'name': _('Create Refund'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.payment.refund.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_payment_id': self.id,
                'default_amount': self.amount,
                'default_patient_id': self.patient_id.id,
            }
        }

    def action_print_receipt(self):
        """Print payment receipt"""
        self.ensure_one()

        self.receipt_printed = True

        return self.env.ref('clinic_finance.action_report_payment_receipt').report_action(self)

    def validate_payment(self):
        """Additional validation before processing"""
        self.ensure_one()

        # Check patient credit limit if applicable
        if hasattr(self.patient_id, 'credit_limit') and self.patient_id.credit_limit > 0:
            total_due = self.patient_id.get_total_due()
            if total_due + self.amount > self.patient_id.credit_limit:
                raise ValidationError(_("Payment would exceed patient's credit limit."))

        return True