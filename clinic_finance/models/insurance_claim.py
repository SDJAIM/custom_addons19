# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class InsuranceClaim(models.Model):
    _name = 'clinic.insurance.claim'
    _description = 'Insurance Claim'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'submission_date desc, claim_number desc'
    _rec_name = 'claim_number'

    # Basic Information
    claim_number = fields.Char(
        string='Claim Number',
        required=True,
        readonly=True,
        copy=False,
        default='New',
        tracking=True,
        index=True
    )
    
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        tracking=True,
        index=True
    )

    policy_id = fields.Many2one(
        'clinic.insurance.policy',
        string='Insurance Policy',
        required=True,
        tracking=True,
        domain="[('patient_id', '=', patient_id), ('is_active', '=', True)]"
    )
    
    insurance_company_id = fields.Many2one(
        'clinic.insurance.company',
        string='Insurance Company',
        related='policy_id.insurance_company_id',
        store=True,
        readonly=True
    )
    
    # Claim Type
    claim_type = fields.Selection([
        ('medical', 'Medical'),
        ('dental', 'Dental'),
        ('vision', 'Vision'),
        ('pharmacy', 'Pharmacy'),
        ('mental_health', 'Mental Health'),
    ], string='Claim Type', default='medical', required=True, tracking=True)
    
    priority = fields.Selection([
        ('normal', 'Normal'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency'),
    ], string='Priority', default='normal', tracking=True)
    
    # Related Records
    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Appointment',
        tracking=True
    )

    invoice_id = fields.Many2one(
        'clinic.invoice',
        string='Invoice',
        tracking=True
    )

    treatment_ids = fields.Many2many(
        'clinic.treatment.plan.line',
        string='Treatments'
    )

    prescription_ids = fields.Many2many(
        'clinic.prescription',
        string='Prescriptions'
    )
    
    # Service Information
    service_date = fields.Date(
        string='Service Date',
        required=True,
        tracking=True
    )
    
    service_end_date = fields.Date(
        string='Service End Date',
        help='For multi-day services'
    )
    
    provider_id = fields.Many2one(
        'clinic.staff',
        string='Provider',
        required=True,
        tracking=True,
        domain=[('is_practitioner', '=', True)]
    )
    
    facility_id = fields.Many2one(
        'clinic.branch',
        string='Facility',
        tracking=True
    )
    
    # Diagnosis and Procedures
    primary_diagnosis_id = fields.Many2one(
        'clinic.diagnosis',
        string='Primary Diagnosis',
        required=True,
        tracking=True
    )
    
    secondary_diagnosis_ids = fields.Many2many(
        'clinic.diagnosis',
        'claim_secondary_diagnosis_rel',
        string='Secondary Diagnoses'
    )
    
    procedure_codes = fields.Text(
        string='Procedure Codes',
        help='CPT/HCPCS codes'
    )
    
    # Authorization
    requires_authorization = fields.Boolean(
        string='Requires Authorization',
        related='policy_id.requires_preauth',
        store=True
    )
    
    authorization_number = fields.Char(
        string='Authorization Number',
        tracking=True
    )
    
    authorization_date = fields.Date(
        string='Authorization Date',
        tracking=True
    )
    
    # Claim Lines
    line_ids = fields.One2many(
        'clinic.claim.line',
        'claim_id',
        string='Claim Lines'
    )
    
    # Financial Information
    amount_billed = fields.Float(
        string='Amount Billed',
        digits='Product Price',
        required=True,
        tracking=True
    )
    
    amount_approved = fields.Float(
        string='Amount Approved',
        digits='Product Price',
        tracking=True
    )
    
    amount_paid = fields.Float(
        string='Amount Paid',
        digits='Product Price',
        tracking=True,
        readonly=True
    )
    
    amount_adjusted = fields.Float(
        string='Adjustment',
        digits='Product Price',
        compute='_compute_amounts',
        store=True
    )
    
    copay_amount = fields.Float(
        string='Co-payment',
        digits='Product Price',
        tracking=True
    )
    
    deductible_amount = fields.Float(
        string='Deductible',
        digits='Product Price',
        tracking=True
    )
    
    coinsurance_amount = fields.Float(
        string='Coinsurance',
        digits='Product Price',
        tracking=True
    )
    
    patient_responsibility = fields.Float(
        string='Patient Responsibility',
        digits='Product Price',
        compute='_compute_patient_responsibility',
        store=True
    )
    
    # Workflow State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('in_review', 'In Review'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('partially_paid', 'Partially Paid'),
        ('rejected', 'Rejected'),
        ('appealed', 'Appealed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True, index=True)
    
    # Submission Information
    submission_date = fields.Datetime(
        string='Submission Date',
        tracking=True,
        readonly=True
    )
    
    submission_method = fields.Selection([
        ('electronic', 'Electronic (EDI)'),
        ('paper', 'Paper'),
        ('portal', 'Web Portal'),
        ('fax', 'Fax'),
    ], string='Submission Method', tracking=True)
    
    submission_reference = fields.Char(
        string='Submission Reference',
        help='EDI transmission ID or tracking number'
    )
    
    submitted_by = fields.Many2one(
        'res.users',
        string='Submitted By',
        readonly=True
    )
    
    # Response Information
    response_date = fields.Datetime(
        string='Response Date',
        tracking=True
    )
    
    response_code = fields.Char(
        string='Response Code'
    )
    
    eob_number = fields.Char(
        string='EOB Number',
        help='Explanation of Benefits number'
    )
    
    # Payment Information
    payment_date = fields.Date(
        string='Payment Date',
        tracking=True
    )
    
    payment_method = fields.Selection([
        ('check', 'Check'),
        ('eft', 'Electronic Transfer'),
        ('credit_card', 'Credit Card'),
        ('cash', 'Cash'),
    ], string='Payment Method')
    
    payment_reference = fields.Char(
        string='Payment Reference',
        help='Check number or transaction ID'
    )
    
    # Rejection/Denial
    rejection_reason = fields.Text(
        string='Rejection Reason',
        tracking=True
    )
    
    rejection_code = fields.Char(
        string='Rejection Code'
    )
    
    can_appeal = fields.Boolean(
        string='Can Appeal',
        default=True
    )
    
    # Appeal Information
    appeal_date = fields.Date(
        string='Appeal Date',
        tracking=True
    )
    
    appeal_reason = fields.Text(
        string='Appeal Reason'
    )
    
    appeal_outcome = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
        ('partial', 'Partially Approved'),
    ], string='Appeal Outcome')
    
    # Documents
    claim_form = fields.Binary(
        string='Claim Form',
        attachment=True
    )
    
    supporting_documents = fields.Many2many(
        'ir.attachment',
        string='Supporting Documents'
    )
    
    eob_document = fields.Binary(
        string='EOB Document',
        attachment=True
    )
    
    # Tracking
    days_outstanding = fields.Integer(
        string='Days Outstanding',
        compute='_compute_days_outstanding',
        store=True
    )
    
    follow_up_date = fields.Date(
        string='Follow-up Date',
        tracking=True
    )
    
    follow_up_count = fields.Integer(
        string='Follow-ups',
        default=0,
        tracking=True
    )
    
    # Notes
    internal_notes = fields.Text(
        string='Internal Notes'
    )
    
    payer_notes = fields.Text(
        string='Payer Notes'
    )
    
    @api.depends('amount_billed', 'amount_paid')
    def _compute_amounts(self):
        for claim in self:
            claim.amount_adjusted = claim.amount_billed - claim.amount_paid
    
    @api.depends('copay_amount', 'deductible_amount', 'coinsurance_amount')
    def _compute_patient_responsibility(self):
        for claim in self:
            claim.patient_responsibility = (
                claim.copay_amount + 
                claim.deductible_amount + 
                claim.coinsurance_amount
            )
    
    @api.depends('submission_date', 'state')
    def _compute_days_outstanding(self):
        today = fields.Datetime.now()
        for claim in self:
            if claim.submission_date and claim.state in ['submitted', 'in_review', 'approved']:
                delta = today - claim.submission_date
                claim.days_outstanding = delta.days
            else:
                claim.days_outstanding = 0
    
    @api.model
    def create(self, vals):
        if vals.get('claim_number', 'New') == 'New':
            vals['claim_number'] = self.env['ir.sequence'].next_by_code('clinic.insurance.claim') or 'New'
        
        # Calculate patient responsibility if policy provided
        if vals.get('policy_id') and vals.get('amount_billed'):
            policy = self.env['clinic.insurance.policy'].browse(vals['policy_id'])
            vals['patient_responsibility'] = policy.calculate_patient_responsibility(vals['amount_billed'])
        
        return super().create(vals)
    
    @api.constrains('service_date', 'service_end_date')
    def _check_service_dates(self):
        for claim in self:
            if claim.service_end_date and claim.service_date > claim.service_end_date:
                raise ValidationError(_("Service end date must be after service date."))
    
    @api.constrains('amount_approved', 'amount_billed')
    def _check_approved_amount(self):
        for claim in self:
            if claim.amount_approved > claim.amount_billed:
                raise ValidationError(_("Approved amount cannot exceed billed amount."))
    
    @api.constrains('amount_paid', 'amount_approved')
    def _check_paid_amount(self):
        for claim in self:
            if claim.amount_paid > claim.amount_approved and claim.amount_approved > 0:
                raise ValidationError(_("Paid amount cannot exceed approved amount."))

    @api.constrains('patient_id', 'state')
    def _check_patient_id_on_update(self):
        """Enforce patient_id readonly constraint based on state"""
        for claim in self:
            if claim.state not in ('draft',) and not self.env.context.get('skip_state_checks'):
                # Patient cannot be changed after draft
                if claim.id and claim.state != 'draft':
                    original = self.env['clinic.insurance.claim'].browse(claim.id)
                    if original.patient_id != claim.patient_id:
                        raise ValidationError(
                            _("Patient cannot be changed once the claim is submitted. "
                              "Current state: %s") % claim.state
                        )

    @api.constrains('provider_id', 'state')
    def _check_provider_id_on_update(self):
        """Enforce provider_id readonly constraint based on state"""
        for claim in self:
            if claim.state in ('submitted', 'approved', 'paid', 'rejected') and not self.env.context.get('skip_state_checks'):
                # Provider cannot be changed in these states
                if claim.id:
                    original = self.env['clinic.insurance.claim'].browse(claim.id)
                    if original.provider_id != claim.provider_id:
                        raise ValidationError(
                            _("Provider cannot be changed in %s state.") % claim.state
                        )

    @api.constrains('amount_billed', 'state')
    def _check_amount_billed_on_update(self):
        """Enforce amount_billed readonly constraint based on state"""
        for claim in self:
            if claim.state in ('submitted', 'approved', 'paid') and not self.env.context.get('skip_state_checks'):
                # Amount billed cannot be changed in these states
                if claim.id:
                    original = self.env['clinic.insurance.claim'].browse(claim.id)
                    if original.amount_billed != claim.amount_billed:
                        raise ValidationError(
                            _("Billed amount cannot be changed in %s state.") % claim.state
                        )
    
    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        if self.patient_id:
            # Get active policies for the patient
            active_policies = self.env['clinic.insurance.policy'].search([
                ('patient_id', '=', self.patient_id.id),
                ('is_active', '=', True)
            ])
            
            if len(active_policies) == 1:
                self.policy_id = active_policies[0]
            
            return {'domain': {'policy_id': [('patient_id', '=', self.patient_id.id), ('is_active', '=', True)]}}
    
    @api.onchange('appointment_id')
    def _onchange_appointment_id(self):
        if self.appointment_id:
            self.patient_id = self.appointment_id.patient_id
            self.provider_id = self.appointment_id.doctor_id
            self.service_date = self.appointment_id.appointment_date.date()
            
            # Get invoice if exists
            if self.appointment_id.invoice_id:
                self.invoice_id = self.appointment_id.invoice_id
                self.amount_billed = self.invoice_id.amount_total
    
    @api.onchange('policy_id', 'amount_billed')
    def _onchange_calculate_responsibility(self):
        if self.policy_id and self.amount_billed:
            # Set copay from policy
            self.copay_amount = self.policy_id.copay_amount
            
            # Calculate patient responsibility
            responsibility = self.policy_id.calculate_patient_responsibility(self.amount_billed)
            
            # Distribute responsibility
            remaining = responsibility
            
            # Apply deductible first
            if self.policy_id.deductible_remaining > 0:
                self.deductible_amount = min(remaining, self.policy_id.deductible_remaining)
                remaining -= self.deductible_amount
            
            # Apply coinsurance
            if remaining > 0 and self.policy_id.coinsurance_percentage > 0:
                self.coinsurance_amount = remaining
    
    def action_submit(self):
        """Submit claim to insurance"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_("Only draft claims can be submitted."))
        
        if self.requires_authorization and not self.authorization_number:
            raise UserError(_("Authorization number is required for this claim."))
        
        if not self.line_ids:
            raise UserError(_("Please add claim lines before submitting."))
        
        self.write({
            'state': 'submitted',
            'submission_date': fields.Datetime.now(),
            'submitted_by': self.env.user.id,
        })
        
        # Create follow-up activity
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            summary='Follow up on claim',
            date_deadline=fields.Date.today() + timedelta(days=14),
            user_id=self.env.user.id
        )
        
        # Send to insurance (in real implementation)
        self._send_to_insurance()
        
        return True
    
    def action_approve(self):
        """Approve claim"""
        self.ensure_one()
        
        if self.state not in ['submitted', 'in_review']:
            raise UserError(_("Only submitted or in-review claims can be approved."))
        
        if not self.amount_approved:
            raise UserError(_("Please enter approved amount."))
        
        self.write({
            'state': 'approved',
            'response_date': fields.Datetime.now(),
        })
        
        return True
    
    def action_pay(self):
        """Mark claim as paid"""
        self.ensure_one()
        
        if self.state != 'approved':
            raise UserError(_("Only approved claims can be marked as paid."))
        
        return {
            'name': _('Record Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.claim.payment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_claim_id': self.id,
                'default_amount': self.amount_approved,
            }
        }
    
    def action_reject(self):
        """Reject claim"""
        self.ensure_one()
        
        if self.state not in ['submitted', 'in_review', 'approved']:
            raise UserError(_("Cannot reject claim in current state."))
        
        return {
            'name': _('Reject Claim'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.claim.rejection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_claim_id': self.id,
            }
        }
    
    def action_appeal(self):
        """Appeal rejected claim"""
        self.ensure_one()
        
        if self.state != 'rejected':
            raise UserError(_("Only rejected claims can be appealed."))
        
        if not self.can_appeal:
            raise UserError(_("This claim cannot be appealed."))
        
        return {
            'name': _('Appeal Claim'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.claim.appeal.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_claim_id': self.id,
            }
        }
    
    def action_cancel(self):
        """Cancel claim"""
        self.ensure_one()
        
        if self.state in ['paid', 'cancelled']:
            raise UserError(_("Cannot cancel claim in current state."))
        
        self.state = 'cancelled'
        
        return True
    
    def action_follow_up(self):
        """Follow up on claim"""
        self.ensure_one()
        
        self.follow_up_count += 1
        self.follow_up_date = fields.Date.today()
        
        # Create note
        self.message_post(
            body=f"Follow-up #{self.follow_up_count} on claim {self.claim_number}",
            subject="Claim Follow-up"
        )
        
        return True
    
    def action_print_claim(self):
        """Print claim form"""
        self.ensure_one()
        
        return self.env.ref('clinic_finance.action_report_insurance_claim').report_action(self)
    
    def _send_to_insurance(self):
        """Send claim to insurance company (EDI or API)"""
        # This would integrate with insurance EDI system
        # For now, just log the action
        self.message_post(
            body=f"Claim {self.claim_number} submitted to {self.insurance_company_id.name}",
            subject="Claim Submitted"
        )
    
    @api.model
    def check_outstanding_claims(self):
        """Cron job to check outstanding claims"""
        # Claims outstanding for more than 30 days
        outstanding_date = fields.Datetime.now() - timedelta(days=30)
        
        claims = self.search([
            ('state', 'in', ['submitted', 'in_review']),
            ('submission_date', '<', outstanding_date),
        ])
        
        for claim in claims:
            # Create activity for follow-up
            claim.activity_schedule(
                'mail.mail_activity_data_warning',
                summary=f'Claim {claim.claim_number} outstanding for {claim.days_outstanding} days',
                user_id=claim.submitted_by.id if claim.submitted_by else self.env.user.id
            )
    
    def name_get(self):
        result = []
        for claim in self:
            name = claim.claim_number
            if claim.patient_id:
                name = f"{name} - {claim.patient_id.name}"
            result.append((claim.id, name))
        return result