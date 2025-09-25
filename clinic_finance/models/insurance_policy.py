# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class InsurancePolicy(models.Model):
    _name = 'clinic.insurance.policy'
    _description = 'Patient Insurance Policy'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'patient_id, start_date desc'
    _rec_name = 'display_name'
    
    # Basic Information
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        tracking=True,
        index=True,
        ondelete='restrict'
    )
    
    insurance_company_id = fields.Many2one(
        'clinic.insurance.company',
        string='Insurance Company',
        required=True,
        tracking=True,
        index=True
    )
    
    policy_number = fields.Char(
        string='Policy Number',
        required=True,
        tracking=True,
        index=True,
        copy=False
    )
    
    group_number = fields.Char(
        string='Group Number',
        tracking=True
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    # Policy Type
    policy_type = fields.Selection([
        ('primary', 'Primary Insurance'),
        ('secondary', 'Secondary Insurance'),
        ('tertiary', 'Tertiary Insurance'),
        ('supplemental', 'Supplemental'),
    ], string='Policy Type', default='primary', required=True, tracking=True)
    
    plan_type = fields.Selection([
        ('hmo', 'HMO - Health Maintenance Organization'),
        ('ppo', 'PPO - Preferred Provider Organization'),
        ('pos', 'POS - Point of Service'),
        ('epo', 'EPO - Exclusive Provider Organization'),
        ('pffs', 'PFFS - Private Fee-for-Service'),
        ('government', 'Government Insurance'),
        ('other', 'Other'),
    ], string='Plan Type', required=True, tracking=True)
    
    # Validity
    start_date = fields.Date(
        string='Start Date',
        required=True,
        tracking=True,
        default=fields.Date.context_today
    )
    
    end_date = fields.Date(
        string='End Date',
        tracking=True
    )
    
    is_active = fields.Boolean(
        string='Active',
        compute='_compute_is_active',
        store=True,
        index=True
    )
    
    # Subscriber Information
    subscriber_name = fields.Char(
        string='Subscriber Name',
        required=True,
        tracking=True
    )
    
    subscriber_id = fields.Char(
        string='Subscriber ID',
        required=True,
        tracking=True
    )
    
    relationship_to_subscriber = fields.Selection([
        ('self', 'Self'),
        ('spouse', 'Spouse'),
        ('child', 'Child'),
        ('parent', 'Parent'),
        ('other', 'Other'),
    ], string='Relationship', default='self', required=True)
    
    subscriber_dob = fields.Date(
        string='Subscriber DOB'
    )
    
    subscriber_gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], string='Subscriber Gender')
    
    # Coverage Details
    coverage_type = fields.Selection([
        ('medical', 'Medical'),
        ('dental', 'Dental'),
        ('vision', 'Vision'),
        ('medical_dental', 'Medical & Dental'),
        ('comprehensive', 'Comprehensive'),
    ], string='Coverage Type', default='medical', required=True)
    
    # Financial Information
    copay_amount = fields.Float(
        string='Co-payment',
        digits='Product Price',
        tracking=True,
        help='Fixed amount for office visits'
    )
    
    copay_specialist = fields.Float(
        string='Specialist Co-pay',
        digits='Product Price',
        help='Co-payment for specialist visits'
    )
    
    copay_emergency = fields.Float(
        string='Emergency Co-pay',
        digits='Product Price',
        help='Co-payment for emergency visits'
    )
    
    deductible_amount = fields.Float(
        string='Annual Deductible',
        digits='Product Price',
        tracking=True
    )
    
    deductible_met = fields.Float(
        string='Deductible Met',
        digits='Product Price',
        tracking=True,
        help='Amount of deductible already met this year'
    )
    
    deductible_remaining = fields.Float(
        string='Deductible Remaining',
        compute='_compute_deductible_remaining',
        store=True,
        digits='Product Price'
    )
    
    out_of_pocket_max = fields.Float(
        string='Out-of-Pocket Maximum',
        digits='Product Price',
        tracking=True
    )
    
    out_of_pocket_met = fields.Float(
        string='Out-of-Pocket Met',
        digits='Product Price',
        tracking=True
    )
    
    coinsurance_percentage = fields.Float(
        string='Coinsurance %',
        tracking=True,
        help='Percentage patient pays after deductible'
    )
    
    # Coverage Limits
    annual_max_benefit = fields.Float(
        string='Annual Maximum Benefit',
        digits='Product Price'
    )
    
    lifetime_max_benefit = fields.Float(
        string='Lifetime Maximum Benefit',
        digits='Product Price'
    )
    
    annual_benefit_used = fields.Float(
        string='Annual Benefit Used',
        digits='Product Price',
        compute='_compute_benefits_used',
        store=True
    )
    
    lifetime_benefit_used = fields.Float(
        string='Lifetime Benefit Used',
        digits='Product Price',
        compute='_compute_benefits_used',
        store=True
    )
    
    # Pre-authorization
    requires_preauth = fields.Boolean(
        string='Requires Pre-authorization',
        default=False,
        tracking=True
    )
    
    preauth_phone = fields.Char(
        string='Pre-auth Phone'
    )
    
    preauth_website = fields.Char(
        string='Pre-auth Website'
    )
    
    # Network Information
    in_network = fields.Boolean(
        string='In-Network Provider',
        default=True,
        tracking=True,
        help='Is our clinic in-network for this insurance?'
    )
    
    network_name = fields.Char(
        string='Network Name'
    )
    
    # Verification
    is_verified = fields.Boolean(
        string='Verified',
        default=False,
        tracking=True
    )
    
    verification_date = fields.Datetime(
        string='Verification Date',
        tracking=True
    )
    
    verified_by = fields.Many2one(
        'res.users',
        string='Verified By',
        tracking=True
    )
    
    verification_method = fields.Selection([
        ('phone', 'Phone'),
        ('website', 'Website'),
        ('edi', 'Electronic (EDI)'),
        ('manual', 'Manual Entry'),
    ], string='Verification Method')
    
    verification_reference = fields.Char(
        string='Verification Reference',
        help='Reference number from verification'
    )
    
    verification_notes = fields.Text(
        string='Verification Notes'
    )
    
    # Documents
    insurance_card_front = fields.Binary(
        string='Insurance Card (Front)',
        attachment=True
    )
    
    insurance_card_back = fields.Binary(
        string='Insurance Card (Back)',
        attachment=True
    )
    
    authorization_form = fields.Binary(
        string='Authorization Form',
        attachment=True
    )
    
    # Claims
    claim_ids = fields.One2many(
        'clinic.insurance.claim',
        'policy_id',
        string='Claims'
    )
    
    claim_count = fields.Integer(
        string='Claims',
        compute='_compute_claim_count'
    )
    
    # Statistics
    total_claimed = fields.Float(
        string='Total Claimed',
        compute='_compute_claim_statistics',
        store=True,
        digits='Product Price'
    )
    
    total_approved = fields.Float(
        string='Total Approved',
        compute='_compute_claim_statistics',
        store=True,
        digits='Product Price'
    )
    
    total_paid = fields.Float(
        string='Total Paid',
        compute='_compute_claim_statistics',
        store=True,
        digits='Product Price'
    )
    
    approval_rate = fields.Float(
        string='Approval Rate (%)',
        compute='_compute_claim_statistics',
        store=True
    )
    
    # Notes
    notes = fields.Text(
        string='Internal Notes'
    )
    
    special_requirements = fields.Text(
        string='Special Requirements',
        help='Special billing requirements for this policy'
    )
    
    @api.depends('patient_id', 'insurance_company_id', 'policy_number')
    def _compute_display_name(self):
        for policy in self:
            parts = []
            if policy.patient_id:
                parts.append(policy.patient_id.name)
            if policy.insurance_company_id:
                parts.append(policy.insurance_company_id.name)
            if policy.policy_number:
                parts.append(f"[{policy.policy_number}]")
            policy.display_name = ' - '.join(parts) if parts else 'New Policy'
    
    @api.depends('start_date', 'end_date')
    def _compute_is_active(self):
        today = fields.Date.today()
        for policy in self:
            if not policy.start_date:
                policy.is_active = False
            elif policy.end_date:
                policy.is_active = policy.start_date <= today <= policy.end_date
            else:
                policy.is_active = policy.start_date <= today
    
    @api.depends('deductible_amount', 'deductible_met')
    def _compute_deductible_remaining(self):
        for policy in self:
            policy.deductible_remaining = max(0, policy.deductible_amount - policy.deductible_met)
    
    @api.depends('claim_ids.amount_billed', 'claim_ids.state')
    def _compute_benefits_used(self):
        for policy in self:
            current_year = fields.Date.today().year
            annual_claims = policy.claim_ids.filtered(
                lambda c: c.state == 'paid' and c.service_date and c.service_date.year == current_year
            )
            policy.annual_benefit_used = sum(annual_claims.mapped('amount_paid'))
            
            lifetime_claims = policy.claim_ids.filtered(lambda c: c.state == 'paid')
            policy.lifetime_benefit_used = sum(lifetime_claims.mapped('amount_paid'))
    
    @api.depends('claim_ids')
    def _compute_claim_count(self):
        for policy in self:
            policy.claim_count = len(policy.claim_ids)
    
    @api.depends('claim_ids.amount_billed', 'claim_ids.amount_approved', 'claim_ids.amount_paid', 'claim_ids.state')
    def _compute_claim_statistics(self):
        for policy in self:
            claims = policy.claim_ids
            policy.total_claimed = sum(claims.mapped('amount_billed'))
            
            approved_claims = claims.filtered(lambda c: c.state in ['approved', 'paid'])
            policy.total_approved = sum(approved_claims.mapped('amount_approved'))
            
            paid_claims = claims.filtered(lambda c: c.state == 'paid')
            policy.total_paid = sum(paid_claims.mapped('amount_paid'))
            
            if len(claims) > 0:
                policy.approval_rate = (len(approved_claims) / len(claims)) * 100
            else:
                policy.approval_rate = 0.0
    
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for policy in self:
            if policy.end_date and policy.start_date and policy.end_date < policy.start_date:
                raise ValidationError(_("End date cannot be before start date."))
    
    @api.constrains('policy_number', 'insurance_company_id', 'patient_id')
    def _check_duplicate_policy(self):
        for policy in self:
            duplicate = self.search([
                ('policy_number', '=', policy.policy_number),
                ('insurance_company_id', '=', policy.insurance_company_id.id),
                ('patient_id', '=', policy.patient_id.id),
                ('id', '!=', policy.id)
            ])
            if duplicate:
                raise ValidationError(_(
                    "Policy number %s already exists for this patient and insurance company."
                ) % policy.policy_number)
    
    @api.constrains('deductible_met', 'deductible_amount')
    def _check_deductible(self):
        for policy in self:
            if policy.deductible_met > policy.deductible_amount:
                raise ValidationError(_("Deductible met cannot exceed deductible amount."))
    
    @api.constrains('out_of_pocket_met', 'out_of_pocket_max')
    def _check_out_of_pocket(self):
        for policy in self:
            if policy.out_of_pocket_met > policy.out_of_pocket_max:
                raise ValidationError(_("Out-of-pocket met cannot exceed out-of-pocket maximum."))
    
    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        if self.patient_id:
            self.subscriber_name = self.patient_id.name
            self.subscriber_dob = self.patient_id.date_of_birth
            self.subscriber_gender = self.patient_id.gender
            self.relationship_to_subscriber = 'self'
    
    @api.onchange('insurance_company_id')
    def _onchange_insurance_company_id(self):
        if self.insurance_company_id:
            # Set default values from insurance company
            if self.insurance_company_id.default_copay:
                self.copay_amount = self.insurance_company_id.default_copay
            if self.insurance_company_id.requires_preauth:
                self.requires_preauth = True
                self.preauth_phone = self.insurance_company_id.preauth_phone
                self.preauth_website = self.insurance_company_id.preauth_website
    
    def action_verify_insurance(self):
        """Verify insurance eligibility"""
        self.ensure_one()
        
        # In real implementation, this would call insurance API
        # For now, open verification wizard
        return {
            'name': _('Verify Insurance'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.insurance.verification.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_policy_id': self.id,
                'default_patient_id': self.patient_id.id,
                'default_insurance_company_id': self.insurance_company_id.id,
            }
        }
    
    def action_view_claims(self):
        """View all claims for this policy"""
        self.ensure_one()
        
        return {
            'name': _('Insurance Claims'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.insurance.claim',
            'view_mode': 'tree,form',
            'domain': [('policy_id', '=', self.id)],
            'context': {
                'default_policy_id': self.id,
                'default_patient_id': self.patient_id.id,
            }
        }
    
    def action_check_benefits(self):
        """Check remaining benefits"""
        self.ensure_one()
        
        message = f"""
        <b>Benefits Summary for {self.display_name}</b><br/>
        <br/>
        <b>Deductible:</b><br/>
        - Annual Deductible: ${self.deductible_amount:,.2f}<br/>
        - Deductible Met: ${self.deductible_met:,.2f}<br/>
        - Remaining: ${self.deductible_remaining:,.2f}<br/>
        <br/>
        <b>Out-of-Pocket:</b><br/>
        - Maximum: ${self.out_of_pocket_max:,.2f}<br/>
        - Met: ${self.out_of_pocket_met:,.2f}<br/>
        - Remaining: ${self.out_of_pocket_max - self.out_of_pocket_met:,.2f}<br/>
        <br/>
        <b>Annual Benefits:</b><br/>
        - Maximum: ${self.annual_max_benefit:,.2f}<br/>
        - Used: ${self.annual_benefit_used:,.2f}<br/>
        - Remaining: ${self.annual_max_benefit - self.annual_benefit_used:,.2f}<br/>
        """
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Benefits Summary'),
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }
    
    def calculate_patient_responsibility(self, service_amount):
        """Calculate patient responsibility for a service amount"""
        self.ensure_one()
        
        if not self.is_active:
            return service_amount  # Full amount if policy not active
        
        patient_responsibility = 0.0
        remaining_amount = service_amount
        
        # Apply deductible if not met
        if self.deductible_remaining > 0:
            deductible_portion = min(remaining_amount, self.deductible_remaining)
            patient_responsibility += deductible_portion
            remaining_amount -= deductible_portion
        
        # Apply coinsurance after deductible
        if remaining_amount > 0 and self.coinsurance_percentage > 0:
            coinsurance_amount = remaining_amount * (self.coinsurance_percentage / 100)
            patient_responsibility += coinsurance_amount
            remaining_amount = remaining_amount - coinsurance_amount
        
        # Apply copay (usually for office visits)
        # This would be determined by service type
        
        # Check out-of-pocket maximum
        if self.out_of_pocket_max > 0:
            max_patient_pay = self.out_of_pocket_max - self.out_of_pocket_met
            patient_responsibility = min(patient_responsibility, max_patient_pay)
        
        return patient_responsibility
    
    @api.model
    def check_expiring_policies(self):
        """Cron job to check for expiring policies"""
        # Policies expiring in next 30 days
        expiry_date = fields.Date.today() + timedelta(days=30)
        
        expiring_policies = self.search([
            ('is_active', '=', True),
            ('end_date', '<=', expiry_date),
            ('end_date', '>', fields.Date.today()),
        ])
        
        for policy in expiring_policies:
            # Create activity for renewal reminder
            policy.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=f'Insurance policy expiring soon',
                note=f'Policy {policy.policy_number} expires on {policy.end_date}',
                date_deadline=policy.end_date - timedelta(days=7),
                user_id=policy.patient_id.user_id.id if policy.patient_id.user_id else self.env.user.id
            )
    
    def name_get(self):
        return [(policy.id, policy.display_name) for policy in self]