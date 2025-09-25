# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class ClinicInvoice(models.Model):
    _name = 'clinic.invoice'
    _inherit = 'account.move'
    _description = 'Clinic Invoice'
    _order = 'name desc, id desc'

    # Medical-specific fields
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        tracking=True,
        help='Patient for whom this invoice is generated'
    )

    appointment_ids = fields.One2many(
        'clinic.appointment',
        'invoice_id',
        string='Appointments',
        help='Appointments included in this invoice'
    )

    primary_appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Primary Appointment',
        help='Main appointment for this invoice'
    )

    doctor_id = fields.Many2one(
        'clinic.doctor',
        string='Doctor',
        tracking=True,
        help='Primary doctor for the services'
    )

    clinic_location_id = fields.Many2one(
        'clinic.location',
        string='Clinic Location',
        help='Location where services were provided'
    )

    # Billing and insurance fields
    billing_type = fields.Selection([
        ('cash', 'Cash/Self-Pay'),
        ('insurance', 'Insurance'),
        ('insurance_cash', 'Insurance + Co-pay'),
        ('free', 'Free/Charity'),
    ], string='Billing Type', default='cash', required=True, tracking=True)

    insurance_policy_id = fields.Many2one(
        'clinic.insurance.policy',
        string='Insurance Policy',
        domain="[('patient_id', '=', patient_id), ('is_active', '=', True)]"
    )

    copay_amount = fields.Monetary(
        string='Co-payment',
        currency_field='currency_id',
        compute='_compute_copay_amount',
        store=True,
        readonly=False
    )

    copay_collected = fields.Boolean(
        string='Co-pay Collected',
        tracking=True
    )

    prior_authorization = fields.Char(
        string='Prior Authorization',
        help='Authorization number from insurance'
    )

    # Claims
    claim_ids = fields.One2many(
        'clinic.insurance.claim',
        'invoice_id',
        string='Insurance Claims'
    )

    claim_count = fields.Integer(
        string='Claims',
        compute='_compute_claim_count'
    )

    # Service information
    service_line_ids = fields.One2many(
        'clinic.invoice.service.line',
        'invoice_id',
        string='Service Lines',
        help='Detailed breakdown of services provided'
    )

    # Financial breakdown
    insurance_amount = fields.Monetary(
        string='Insurance Amount',
        currency_field='currency_id',
        compute='_compute_amounts',
        store=True
    )

    patient_amount = fields.Monetary(
        string='Patient Amount',
        currency_field='currency_id',
        compute='_compute_amounts',
        store=True
    )

    # Treatment information
    diagnosis_ids = fields.Many2many(
        'clinic.diagnosis',
        string='Diagnoses',
        help='Diagnoses related to this invoice'
    )

    primary_diagnosis_id = fields.Many2one(
        'clinic.diagnosis',
        string='Primary Diagnosis',
        compute='_compute_primary_diagnosis',
        store=True
    )

    @api.depends('insurance_policy_id')
    def _compute_copay_amount(self):
        for invoice in self:
            if invoice.insurance_policy_id:
                invoice.copay_amount = invoice.insurance_policy_id.copay_amount
            else:
                invoice.copay_amount = 0.0

    @api.depends('amount_total', 'billing_type', 'insurance_policy_id', 'copay_amount')
    def _compute_amounts(self):
        for invoice in self:
            if invoice.billing_type == 'insurance' and invoice.insurance_policy_id:
                # Calculate patient responsibility
                invoice.patient_amount = invoice.insurance_policy_id.calculate_patient_responsibility(
                    invoice.amount_total
                )
                invoice.insurance_amount = invoice.amount_total - invoice.patient_amount
            elif invoice.billing_type == 'insurance_cash':
                invoice.patient_amount = invoice.copay_amount
                invoice.insurance_amount = invoice.amount_total - invoice.copay_amount
            else:
                invoice.patient_amount = invoice.amount_total
                invoice.insurance_amount = 0.0

    @api.depends('claim_ids')
    def _compute_claim_count(self):
        for invoice in self:
            invoice.claim_count = len(invoice.claim_ids)

    @api.depends('diagnosis_ids')
    def _compute_primary_diagnosis(self):
        for invoice in self:
            if invoice.diagnosis_ids:
                invoice.primary_diagnosis_id = invoice.diagnosis_ids[0]
            else:
                invoice.primary_diagnosis_id = False

    @api.model
    def default_get(self, fields_list):
        """Set default values for clinic invoices"""
        defaults = super().default_get(fields_list)
        defaults.update({
            'move_type': 'out_invoice',
            'journal_id': self._get_default_journal().id,
        })
        return defaults

    @api.model
    def _get_default_journal(self):
        """Get default journal for clinic invoices"""
        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        return journal

    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        """Update partner and insurance when patient changes"""
        if self.patient_id:
            self.partner_id = self.patient_id.partner_id

            # Check for active insurance
            active_policies = self.env['clinic.insurance.policy'].search([
                ('patient_id', '=', self.patient_id.id),
                ('is_active', '=', True),
                ('policy_type', '=', 'primary')
            ], limit=1)

            if active_policies:
                self.insurance_policy_id = active_policies[0]
                self.billing_type = 'insurance_cash'

    @api.onchange('billing_type')
    def _onchange_billing_type(self):
        """Update partner based on billing type"""
        if self.billing_type == 'insurance' and self.insurance_policy_id:
            # Bill insurance company
            self.partner_id = self.insurance_policy_id.insurance_company_id.partner_id
        elif self.patient_id:
            # Bill patient
            self.partner_id = self.patient_id.partner_id

        if self.billing_type not in ['insurance', 'insurance_cash']:
            self.insurance_policy_id = False
            self.prior_authorization = False

    @api.onchange('insurance_policy_id')
    def _onchange_insurance_policy(self):
        """Update partner when insurance policy changes"""
        if self.insurance_policy_id and self.billing_type == 'insurance':
            self.partner_id = self.insurance_policy_id.insurance_company_id.partner_id

    def action_post(self):
        """Override to create insurance claim after posting"""
        res = super().action_post()

        for invoice in self:
            if invoice.billing_type in ['insurance', 'insurance_cash'] and invoice.insurance_policy_id:
                if not invoice.claim_ids:
                    invoice._create_insurance_claim()

        return res

    def _create_insurance_claim(self):
        """Create insurance claim for invoice"""
        self.ensure_one()

        if not self.insurance_policy_id:
            return False

        claim_vals = {
            'patient_id': self.patient_id.id,
            'policy_id': self.insurance_policy_id.id,
            'invoice_id': self.id,
            'service_date': self.invoice_date,
            'provider_id': self.doctor_id.id if self.doctor_id else False,
            'amount_billed': self.amount_total,
            'copay_amount': self.copay_amount,
            'claim_type': 'medical',
            'state': 'draft',
        }

        # Add primary appointment if exists
        if self.primary_appointment_id:
            claim_vals['appointment_id'] = self.primary_appointment_id.id

        # Add diagnosis if available
        if self.primary_diagnosis_id:
            claim_vals['primary_diagnosis_id'] = self.primary_diagnosis_id.id

        secondary_diagnoses = self.diagnosis_ids - self.primary_diagnosis_id
        if secondary_diagnoses:
            claim_vals['secondary_diagnosis_ids'] = [(6, 0, secondary_diagnoses.ids)]

        # Add authorization if available
        if self.prior_authorization:
            claim_vals['authorization_number'] = self.prior_authorization
            claim_vals['authorization_date'] = fields.Date.today()

        claim = self.env['clinic.insurance.claim'].create(claim_vals)

        # Create claim lines from service lines
        for service_line in self.service_line_ids:
            claim_line_vals = {
                'claim_id': claim.id,
                'service_id': service_line.service_id.id,
                'description': service_line.name,
                'quantity': service_line.quantity,
                'unit_price': service_line.unit_price,
                'amount': service_line.subtotal,
            }
            self.env['clinic.claim.line'].create(claim_line_vals)

        _logger.info(f"Insurance claim {claim.claim_number} created for invoice {self.name}")

        return claim

    def action_view_claims(self):
        """View insurance claims for invoice"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Insurance Claims'),
            'res_model': 'clinic.insurance.claim',
            'view_mode': 'tree,form',
            'domain': [('invoice_id', '=', self.id)],
            'context': {
                'default_invoice_id': self.id,
                'default_patient_id': self.patient_id.id,
            }
        }

    def action_view_appointments(self):
        """View appointments for this invoice"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Appointments'),
            'res_model': 'clinic.appointment',
            'view_mode': 'tree,form',
            'domain': [('invoice_id', '=', self.id)],
            'context': {
                'default_invoice_id': self.id,
                'default_patient_id': self.patient_id.id,
            }
        }

    def validate_invoice(self):
        """
        Validate invoice before posting
        Performs various checks to ensure invoice integrity
        """
        self.ensure_one()

        errors = []

        # Check basic requirements
        if not self.patient_id:
            errors.append(_("Invoice must have a patient."))

        if not self.invoice_line_ids:
            errors.append(_("Invoice must have at least one line item."))

        if self.amount_total <= 0:
            errors.append(_("Invoice total must be greater than zero."))

        # Check date validity
        if self.invoice_date > fields.Date.today():
            errors.append(_("Invoice date cannot be in the future."))

        # Check for duplicate invoice
        if self.state == 'draft':
            duplicate = self.search([
                ('patient_id', '=', self.patient_id.id),
                ('invoice_date', '=', self.invoice_date),
                ('amount_total', '=', self.amount_total),
                ('state', '!=', 'cancel'),
                ('id', '!=', self.id)
            ])
            if duplicate:
                errors.append(_("A similar invoice already exists for this patient."))

        # Validate insurance information if applicable
        if self.insurance_policy_id:
            if not self.insurance_policy_id.is_valid:
                errors.append(_("Insurance policy is not valid."))

            if self.insurance_policy_id.expiry_date and self.insurance_policy_id.expiry_date < self.invoice_date:
                errors.append(_("Insurance policy has expired."))

            # Check coverage limits
            if hasattr(self.insurance_policy_id, 'coverage_limit') and self.insurance_policy_id.coverage_limit > 0:
                used_amount = sum(self.env['clinic.invoice'].search([
                    ('insurance_policy_id', '=', self.insurance_policy_id.id),
                    ('state', '=', 'posted'),
                    ('invoice_date', '>=', fields.Date.today().replace(month=1, day=1))
                ]).mapped('insurance_amount'))

                if used_amount + self.insurance_amount > self.insurance_policy_id.coverage_limit:
                    errors.append(_("Insurance coverage limit would be exceeded."))

        # Validate line items
        for line in self.invoice_line_ids:
            if line.quantity <= 0:
                errors.append(_("Line '%s' has invalid quantity.") % line.name)

            if line.price_unit < 0:
                errors.append(_("Line '%s' has negative price.") % line.name)

            # Check tax validity
            if line.tax_ids:
                for tax in line.tax_ids:
                    if not tax.active:
                        errors.append(_("Line '%s' uses inactive tax '%s'.") % (line.name, tax.name))

        # Check payment terms
        if self.invoice_payment_term_id:
            if not self.invoice_payment_term_id.active:
                errors.append(_("Payment terms are not active."))

        # Validate amounts
        if self.copay_amount < 0:
            errors.append(_("Copay amount cannot be negative."))

        if self.insurance_amount < 0:
            errors.append(_("Insurance amount cannot be negative."))

        if self.deductible_amount < 0:
            errors.append(_("Deductible amount cannot be negative."))

        # Check if amounts add up correctly
        expected_patient_amount = self.copay_amount + self.deductible_amount + self.coinsurance_amount
        if abs(self.patient_amount - expected_patient_amount) > 0.01:  # Allow small rounding difference
            errors.append(_("Patient amount calculation is incorrect."))

        if abs(self.amount_total - (self.patient_amount + self.insurance_amount)) > 0.01:
            errors.append(_("Total amount does not match patient + insurance amounts."))

        if errors:
            raise ValidationError('\n'.join(errors))

        return True

    def action_post(self):
        """Override to add validation before posting"""
        for invoice in self:
            invoice.validate_invoice()
        return super(ClinicInvoice, self).action_post()

    def action_collect_copay(self):
        """Mark copay as collected and create payment"""
        self.ensure_one()

        if not self.copay_amount:
            raise UserError(_("No copay amount to collect."))

        self.copay_collected = True

        # Create payment if invoice is posted
        if self.state == 'posted':
            payment_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': self.patient_id.partner_id.id,
                'amount': self.copay_amount,
                'currency_id': self.currency_id.id,
                'journal_id': self._get_default_payment_journal().id,
                'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                'ref': f"Copay for {self.name}",
            }
            payment = self.env['account.payment'].create(payment_vals)
            payment.action_post()

            # Reconcile payment with invoice
            lines_to_reconcile = payment.line_ids + self.line_ids.filtered(
                lambda l: l.account_id.user_type_id.type == 'receivable'
            )
            lines_to_reconcile.reconcile()

        return True

    def _get_default_payment_journal(self):
        """Get default payment journal"""
        journal = self.env['account.journal'].search([
            ('type', '=', 'cash'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal:
            journal = self.env['account.journal'].search([
                ('type', '=', 'bank'),
                ('company_id', '=', self.env.company.id),
            ], limit=1)
        return journal


class ClinicInvoiceServiceLine(models.Model):
    _name = 'clinic.invoice.service.line'
    _description = 'Clinic Invoice Service Line'
    _order = 'sequence, id'

    invoice_id = fields.Many2one(
        'clinic.invoice',
        string='Invoice',
        required=True,
        ondelete='cascade'
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    service_id = fields.Many2one(
        'clinic.service',
        string='Service',
        required=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        related='service_id.product_id',
        store=True
    )

    name = fields.Text(
        string='Description',
        required=True
    )

    quantity = fields.Float(
        string='Quantity',
        default=1.0,
        required=True
    )

    unit_price = fields.Float(
        string='Unit Price',
        required=True,
        digits='Product Price'
    )

    discount = fields.Float(
        string='Discount (%)',
        default=0.0
    )

    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True,
        digits='Product Price'
    )

    is_covered = fields.Boolean(
        string='Insurance Covered',
        default=True,
        help='Is this service covered by insurance?'
    )

    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Appointment',
        help='Appointment where this service was provided'
    )

    doctor_id = fields.Many2one(
        'clinic.doctor',
        string='Doctor',
        help='Doctor who provided this service'
    )

    @api.depends('quantity', 'unit_price', 'discount')
    def _compute_subtotal(self):
        for line in self:
            price = line.unit_price * (1 - line.discount / 100)
            line.subtotal = price * line.quantity

    @api.onchange('service_id')
    def _onchange_service_id(self):
        if self.service_id:
            self.name = self.service_id.description or self.service_id.name
            self.unit_price = self.service_id.list_price
            self.product_id = self.service_id.product_id