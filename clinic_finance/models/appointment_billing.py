# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class AppointmentBilling(models.Model):
    _inherit = 'clinic.appointment'
    
    # Billing Fields
    invoice_id = fields.Many2one(
        'clinic.invoice',
        string='Invoice',
        readonly=True,
        copy=False,
        tracking=True
    )
    
    invoice_state = fields.Selection(
        related='invoice_id.state',
        string='Invoice Status',
        store=True
    )
    
    is_billable = fields.Boolean(
        string='Billable',
        default=True,
        tracking=True,
        help='Uncheck if appointment should not generate invoice'
    )
    
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
    
    copay_amount = fields.Float(
        string='Co-payment',
        digits='Product Price',
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
    
    # Service Lines
    service_line_ids = fields.One2many(
        'clinic.appointment.service.line',
        'appointment_id',
        string='Services'
    )
    
    total_amount = fields.Float(
        string='Total Amount',
        compute='_compute_amounts',
        store=True,
        digits='Product Price'
    )
    
    insurance_amount = fields.Float(
        string='Insurance Amount',
        compute='_compute_amounts',
        store=True,
        digits='Product Price'
    )
    
    patient_amount = fields.Float(
        string='Patient Amount',
        compute='_compute_amounts',
        store=True,
        digits='Product Price'
    )
    
    # Claims
    claim_ids = fields.One2many(
        'clinic.insurance.claim',
        'appointment_id',
        string='Insurance Claims'
    )
    
    claim_count = fields.Integer(
        string='Claims',
        compute='_compute_claim_count'
    )
    
    @api.depends('insurance_policy_id')
    def _compute_copay_amount(self):
        for appointment in self:
            if appointment.insurance_policy_id:
                appointment.copay_amount = appointment.insurance_policy_id.copay_amount
            else:
                appointment.copay_amount = 0.0
    
    @api.depends('service_line_ids.subtotal', 'billing_type', 'insurance_policy_id', 'copay_amount')
    def _compute_amounts(self):
        for appointment in self:
            appointment.total_amount = sum(appointment.service_line_ids.mapped('subtotal'))
            
            if appointment.billing_type == 'insurance' and appointment.insurance_policy_id:
                # Calculate patient responsibility
                appointment.patient_amount = appointment.insurance_policy_id.calculate_patient_responsibility(
                    appointment.total_amount
                )
                appointment.insurance_amount = appointment.total_amount - appointment.patient_amount
            elif appointment.billing_type == 'insurance_cash':
                appointment.patient_amount = appointment.copay_amount
                appointment.insurance_amount = appointment.total_amount - appointment.copay_amount
            else:
                appointment.patient_amount = appointment.total_amount
                appointment.insurance_amount = 0.0
    
    @api.depends('claim_ids')
    def _compute_claim_count(self):
        for appointment in self:
            appointment.claim_count = len(appointment.claim_ids)
    
    @api.onchange('billing_type')
    def _onchange_billing_type(self):
        if self.billing_type == 'free':
            self.is_billable = False
        else:
            self.is_billable = True
        
        if self.billing_type not in ['insurance', 'insurance_cash']:
            self.insurance_policy_id = False
            self.prior_authorization = False
    
    @api.onchange('patient_id')
    def _onchange_patient_billing(self):
        """Extended from base to handle billing"""
        if self.patient_id:
            # Check for active insurance
            active_policies = self.env['clinic.insurance.policy'].search([
                ('patient_id', '=', self.patient_id.id),
                ('is_active', '=', True),
                ('policy_type', '=', 'primary')
            ], limit=1)
            
            if active_policies:
                self.insurance_policy_id = active_policies[0]
                self.billing_type = 'insurance_cash'
    
    def action_done(self):
        """Override to create invoice when appointment is done"""
        res = super().action_done()
        
        for appointment in self:
            if appointment.is_billable and not appointment.invoice_id:
                appointment._create_invoice()
        
        return res
    
    def validate_billing(self):
        """Validate billing information before creating invoice"""
        self.ensure_one()

        errors = []

        # Check basic requirements
        if not self.patient_id:
            errors.append(_("Billing must have a patient."))

        if not self.appointment_id and not self.service_line_ids:
            errors.append(_("Billing must be linked to an appointment or have service lines."))

        if self.billing_type not in ['cash', 'insurance', 'insurance_cash']:
            errors.append(_("Invalid billing type."))

        # Validate insurance if applicable
        if self.billing_type in ['insurance', 'insurance_cash']:
            if not self.insurance_policy_id:
                errors.append(_("Insurance policy is required for insurance billing."))
            elif not self.insurance_policy_id.is_valid:
                errors.append(_("Insurance policy is not valid."))
            elif self.insurance_policy_id.expiry_date and self.insurance_policy_id.expiry_date < fields.Date.today():
                errors.append(_("Insurance policy has expired."))

        # Validate amounts
        if self.total_amount < 0:
            errors.append(_("Total amount cannot be negative."))

        if self.discount_amount < 0:
            errors.append(_("Discount amount cannot be negative."))

        if self.discount_amount > self.total_amount:
            errors.append(_("Discount cannot exceed total amount."))

        if self.copay_amount < 0:
            errors.append(_("Copay amount cannot be negative."))

        if self.deductible_amount < 0:
            errors.append(_("Deductible amount cannot be negative."))

        if self.coinsurance_amount < 0:
            errors.append(_("Coinsurance amount cannot be negative."))

        # Validate service lines
        if self.service_line_ids:
            for line in self.service_line_ids:
                if line.quantity <= 0:
                    errors.append(_("Service '%s' has invalid quantity.") % line.service_id.name)
                if line.unit_price < 0:
                    errors.append(_("Service '%s' has negative price.") % line.service_id.name)

        # Check if patient amounts are correct
        if self.billing_type == 'insurance':
            patient_total = self.copay_amount + self.deductible_amount + self.coinsurance_amount
            if abs(self.patient_amount - patient_total) > 0.01:
                errors.append(_("Patient amount calculation is incorrect."))

            insurance_total = self.total_amount - patient_total
            if abs(self.insurance_amount - insurance_total) > 0.01:
                errors.append(_("Insurance amount calculation is incorrect."))

        # Check for duplicate billing
        if not self.invoice_id:  # Only check if no invoice created yet
            duplicate = self.search([
                ('patient_id', '=', self.patient_id.id),
                ('appointment_id', '=', self.appointment_id.id) if self.appointment_id else ('id', '=', False),
                ('total_amount', '=', self.total_amount),
                ('state', '!=', 'cancelled'),
                ('id', '!=', self.id)
            ])
            if duplicate:
                errors.append(_("Similar billing already exists for this patient/appointment."))

        # Check authorization if required
        if self.requires_authorization and not self.prior_authorization:
            errors.append(_("Prior authorization is required but not provided."))

        if errors:
            raise ValidationError('\n'.join(errors))

        return True

    def _create_invoice(self):
        """Create invoice for appointment"""
        self.ensure_one()

        # Validate billing first
        self.validate_billing()

        if not self.is_billable:
            return False

        if self.invoice_id:
            raise UserError(_("Invoice already exists for this appointment."))

        if not self.service_line_ids:
            raise UserError(_("No services to invoice."))
        
        # Prepare invoice values
        invoice_vals = self._prepare_invoice_vals()
        
        # Create invoice
        invoice = self.env['clinic.invoice'].create(invoice_vals)
        
        # Link invoice to appointment
        self.invoice_id = invoice
        
        # Create insurance claim if applicable
        if self.billing_type in ['insurance', 'insurance_cash'] and self.insurance_policy_id:
            self._create_insurance_claim()
        
        # Post invoice if configured
        if self.env.company.clinic_auto_post_invoice:
            invoice.action_post()
        
        _logger.info(f"Invoice {invoice.name} created for appointment {self.name}")
        
        return invoice
    
    def _prepare_invoice_vals(self):
        """Prepare invoice values"""
        self.ensure_one()

        # Determine partner (patient or insurance company)
        if self.billing_type == 'insurance' and self.insurance_policy_id:
            partner = self.insurance_policy_id.insurance_company_id.partner_id
        else:
            partner = self.patient_id.partner_id

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'patient_id': self.patient_id.id,
            'primary_appointment_id': self.id,
            'doctor_id': self.doctor_id.id if self.doctor_id else False,
            'billing_type': self.billing_type,
            'insurance_policy_id': self.insurance_policy_id.id if self.insurance_policy_id else False,
            'copay_amount': self.copay_amount,
            'prior_authorization': self.prior_authorization,
            'invoice_date': fields.Date.today(),
            'invoice_origin': self.name,
            'narration': f"Services for appointment {self.name} on {self.appointment_date}",
            'invoice_line_ids': [],
            'service_line_ids': [],
        }

        # Add diagnoses if available
        if self.treatment_ids:
            diagnoses = self.treatment_ids.mapped('diagnosis_id')
            if diagnoses:
                invoice_vals['diagnosis_ids'] = [(6, 0, diagnoses.ids)]

        # Add invoice lines
        for line in self.service_line_ids:
            invoice_line = self._prepare_invoice_line(line)
            invoice_vals['invoice_line_ids'].append((0, 0, invoice_line))

            # Add service line
            service_line = self._prepare_service_line(line)
            invoice_vals['service_line_ids'].append((0, 0, service_line))

        return invoice_vals
    
    def _prepare_invoice_line(self, service_line):
        """Prepare invoice line from service line"""

        # Get or create product for the service
        product = service_line.product_id or self._get_service_product(service_line)

        return {
            'product_id': product.id,
            'name': service_line.description or product.name,
            'quantity': service_line.quantity,
            'price_unit': service_line.unit_price,
            'discount': service_line.discount,
            'tax_ids': [(6, 0, product.taxes_id.ids)],
            'analytic_account_id': self.doctor_id.analytic_account_id.id if self.doctor_id.analytic_account_id else False,
        }

    def _prepare_service_line(self, service_line):
        """Prepare service line for clinic invoice"""

        return {
            'service_id': service_line.service_id.id,
            'name': service_line.description or service_line.service_id.name,
            'quantity': service_line.quantity,
            'unit_price': service_line.unit_price,
            'discount': service_line.discount,
            'is_covered': service_line.is_covered,
            'appointment_id': self.id,
            'doctor_id': self.doctor_id.id if self.doctor_id else False,
        }
    
    def _get_service_product(self, service_line):
        """Get or create product for service"""
        
        # Look for existing service product
        product = self.env['product.product'].search([
            ('name', '=', service_line.service_id.name),
            ('type', '=', 'service'),
        ], limit=1)
        
        if not product:
            # Create service product
            product = self.env['product.product'].create({
                'name': service_line.service_id.name,
                'type': 'service',
                'list_price': service_line.unit_price,
                'standard_price': 0.0,
                'categ_id': self.env.ref('product.product_category_all').id,
            })
        
        return product
    
    def process_insurance_claim(self):
        """Process insurance claim for this billing"""
        self.ensure_one()

        if not self.insurance_policy_id:
            raise UserError(_("No insurance policy selected for this billing."))

        if self.insurance_claim_id:
            # Claim already exists, just process it
            if self.insurance_claim_id.state == 'draft':
                self.insurance_claim_id.action_submit()
            return self.insurance_claim_id

        # Create new claim
        return self._create_insurance_claim()

    def _create_insurance_claim(self):
        """Create insurance claim for appointment"""
        self.ensure_one()

        if not self.insurance_policy_id:
            return False
        
        claim_vals = {
            'patient_id': self.patient_id.id,
            'policy_id': self.insurance_policy_id.id,
            'appointment_id': self.id,
            'invoice_id': self.invoice_id.id,
            'service_date': self.appointment_date.date(),
            'provider_id': self.doctor_id.id,
            'amount_billed': self.total_amount,
            'copay_amount': self.copay_amount,
            'claim_type': 'medical',
            'state': 'draft',
        }
        
        # Add diagnosis if available
        if self.treatment_ids:
            diagnoses = self.treatment_ids.mapped('diagnosis_id')
            if diagnoses:
                claim_vals['primary_diagnosis_id'] = diagnoses[0].id
                if len(diagnoses) > 1:
                    claim_vals['secondary_diagnosis_ids'] = [(6, 0, diagnoses[1:].ids)]
        
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
                'description': service_line.description,
                'quantity': service_line.quantity,
                'unit_price': service_line.unit_price,
                'amount': service_line.subtotal,
            }
            self.env['clinic.claim.line'].create(claim_line_vals)
        
        # Link claim to billing record
        self.insurance_claim_id = claim

        # Automatically submit the claim if configured
        if self.env['ir.config_parameter'].sudo().get_param('clinic.auto_submit_claims', 'False') == 'True':
            claim.action_submit()
            self.message_post(
                body=_("Insurance claim %s automatically submitted") % claim.claim_number,
                message_type='notification'
            )
        else:
            self.message_post(
                body=_("Insurance claim %s created. Please review and submit.") % claim.claim_number,
                message_type='notification'
            )

        _logger.info(f"Insurance claim {claim.claim_number} created for appointment {self.name}")

        return claim
    
    def action_view_invoice(self):
        """View invoice for appointment"""
        self.ensure_one()
        
        if not self.invoice_id:
            raise UserError(_("No invoice exists for this appointment."))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoice'),
            'res_model': 'clinic.invoice',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_claims(self):
        """View insurance claims for appointment"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Insurance Claims'),
            'res_model': 'clinic.insurance.claim',
            'view_mode': 'tree,form',
            'domain': [('appointment_id', '=', self.id)],
            'context': {
                'default_appointment_id': self.id,
                'default_patient_id': self.patient_id.id,
            }
        }
    
    def action_collect_copay(self):
        """Mark copay as collected"""
        self.ensure_one()
        
        if not self.copay_amount:
            raise UserError(_("No copay amount to collect."))
        
        self.copay_collected = True
        
        # Create payment if invoice exists
        if self.invoice_id and self.invoice_id.state == 'posted':
            # Create payment for copay amount
            payment_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': self.patient_id.partner_id.id,
                'amount': self.copay_amount,
                'move_id': self.invoice_id.id,
                'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
            }
            payment = self.env['account.payment'].create(payment_vals)
            payment.action_post()
        
        return True


class AppointmentServiceLine(models.Model):
    _name = 'clinic.appointment.service.line'
    _description = 'Appointment Service Line'
    _order = 'sequence, id'
    
    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Appointment',
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
    
    description = fields.Text(
        string='Description'
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
    
    @api.depends('quantity', 'unit_price', 'discount')
    def _compute_subtotal(self):
        for line in self:
            price = line.unit_price * (1 - line.discount / 100)
            line.subtotal = price * line.quantity
    
    @api.onchange('service_id')
    def _onchange_service_id(self):
        if self.service_id:
            self.description = self.service_id.description
            self.unit_price = self.service_id.list_price