# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import date
from odoo.exceptions import ValidationError


class ClinicPatientInsurance(models.Model):
    _name = 'clinic.patient.insurance'
    _description = 'Patient Insurance Policy'
    _rec_name = 'display_name'
    _order = 'is_primary desc, expiry_date desc'
    
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        ondelete='cascade'
    )

    # Multi-company support
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='patient_id.company_id',
        store=True,
        readonly=True,
        index=True
    )
    
    # TASK-F2-008: Insurance company consolidation - properly linked to clinic_finance
    # This creates a dependency: clinic_patient → clinic_finance
    # This is SAFE because clinic_finance already depends on clinic_patient
    insurance_company_id = fields.Many2one(
        'clinic.insurance.company',
        string='Insurance Company',
        required=True,
        ondelete='restrict',
        index=True,
        help='Insurance company from clinic_finance module'
    )
    
    policy_number = fields.Char(
        string='Policy Number',
        required=True,
        help='Insurance policy number'
    )
    
    group_number = fields.Char(
        string='Group Number',
        help='Insurance group number if applicable'
    )
    
    is_primary = fields.Boolean(
        string='Primary Insurance',
        help='Mark as primary insurance'
    )
    
    policy_type = fields.Selection([
        ('medical', 'Medical'),
        ('dental', 'Dental'),
        ('vision', 'Vision'),
        ('medical_dental', 'Medical & Dental'),
        ('comprehensive', 'Comprehensive')
    ], string='Policy Type', required=True, default='medical')
    
    coverage_type = fields.Selection([
        ('individual', 'Individual'),
        ('family', 'Family'),
        ('employee', 'Employee'),
        ('employee_family', 'Employee + Family')
    ], string='Coverage Type', default='individual')
    
    policy_holder_name = fields.Char(
        string='Policy Holder Name',
        required=True,
        help='Name of the primary policy holder'
    )
    
    policy_holder_relationship = fields.Selection([
        ('self', 'Self'),
        ('spouse', 'Spouse'),
        ('parent', 'Parent'),
        ('child', 'Child'),
        ('other', 'Other')
    ], string='Relationship to Patient', default='self', required=True)
    
    effective_date = fields.Date(
        string='Effective Date',
        required=True,
        help='Policy effective date'
    )
    
    expiry_date = fields.Date(
        string='Expiry Date',
        required=True,
        help='Policy expiration date'
    )
    
    is_active = fields.Boolean(
        string='Active',
        compute='_compute_is_active',
        store=True,
        help='Policy is currently active'
    )
    
    copay_amount = fields.Float(
        string='Copay Amount',
        help='Standard copay amount for visits'
    )
    
    deductible_amount = fields.Float(
        string='Deductible Amount',
        help='Annual deductible amount'
    )
    
    deductible_met = fields.Float(
        string='Deductible Met',
        help='Amount of deductible already met this year'
    )
    
    max_coverage = fields.Float(
        string='Maximum Coverage',
        help='Maximum annual coverage amount'
    )
    
    coverage_used = fields.Float(
        string='Coverage Used',
        help='Amount of coverage used this year'
    )
    
    coverage_remaining = fields.Float(
        string='Coverage Remaining',
        compute='_compute_coverage_remaining',
        store=True,
        help='Remaining coverage for the year'
    )
    
    preauthorization_required = fields.Boolean(
        string='Pre-authorization Required',
        help='Insurance requires pre-authorization for certain procedures'
    )
    
    insurance_card_front = fields.Binary(
        string='Insurance Card (Front)',
        attachment=True
    )
    
    insurance_card_back = fields.Binary(
        string='Insurance Card (Back)',
        attachment=True
    )
    
    notes = fields.Text(string='Notes')
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    # Verification fields
    last_verified_date = fields.Date(
        string='Last Verified',
        help='Date when insurance was last verified'
    )
    
    verified_by = fields.Many2one(
        'res.users',
        string='Verified By',
        help='User who last verified the insurance'
    )
    
    verification_status = fields.Selection([
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('invalid', 'Invalid'),
        ('expired', 'Expired')
    ], string='Verification Status', default='pending')
    
    @api.depends('insurance_company_id', 'policy_number', 'is_primary')
    def _compute_display_name(self):
        for record in self:
            primary = " [PRIMARY]" if record.is_primary else ""
            company = record.insurance_company_id.name if record.insurance_company_id else "No Company"
            record.display_name = f"{company} - {record.policy_number}{primary}"
    
    @api.depends('effective_date', 'expiry_date')
    def _compute_is_active(self):
        today = date.today()
        for record in self:
            record.is_active = (
                record.effective_date and 
                record.expiry_date and
                record.effective_date <= today <= record.expiry_date
            )
    
    @api.depends('max_coverage', 'coverage_used')
    def _compute_coverage_remaining(self):
        for record in self:
            if record.max_coverage:
                record.coverage_remaining = max(0, record.max_coverage - record.coverage_used)
            else:
                record.coverage_remaining = 0
    
    @api.constrains('effective_date', 'expiry_date')
    def _check_dates(self):
        for record in self:
            if record.effective_date and record.expiry_date:
                if record.expiry_date < record.effective_date:
                    raise ValidationError(_("Expiry date cannot be before effective date!"))
    
    @api.constrains('is_primary')
    def _check_primary_insurance(self):
        for record in self:
            if record.is_primary:
                # Check if there's another primary insurance of the same type
                other_primary = self.search([
                    ('patient_id', '=', record.patient_id.id),
                    ('is_primary', '=', True),
                    ('policy_type', '=', record.policy_type),
                    ('id', '!=', record.id)
                ])
                if other_primary:
                    raise ValidationError(_(
                        f"Patient already has a primary {record.policy_type} insurance policy. "
                        "Please unmark the other policy as primary first."
                    ))
    
    def action_verify_insurance(self):
        """Verify insurance coverage"""
        self.ensure_one()
        # This would typically call an external insurance verification API
        # For now, we'll just mark it as verified
        self.write({
            'verification_status': 'verified',
            'last_verified_date': fields.Date.today(),
            'verified_by': self.env.user.id,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Insurance verified successfully!'),
                'type': 'success',
            }
        }
    
    def action_mark_expired(self):
        """Mark insurance as expired"""
        self.ensure_one()
        self.verification_status = 'expired'
        
    @api.model
    def check_expiring_policies(self):
        """Cron job to check for expiring policies"""
        from datetime import timedelta
        
        warning_date = date.today() + timedelta(days=30)
        
        expiring_policies = self.search([
            ('expiry_date', '<=', warning_date),
            ('expiry_date', '>=', date.today()),
            ('is_active', '=', True)
        ])
        
        for policy in expiring_policies:
            # Create activity for staff to renew/update insurance
            policy.patient_id.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=f'Insurance Policy Expiring Soon',
                note=f'Insurance policy {policy.policy_number} expires on {policy.expiry_date}',
                date_deadline=policy.expiry_date
            )


# ==============================================================================
# NOTE (TASK-F2-008): Insurance Company Consolidation
# ==============================================================================
# The ClinicInsuranceCompany model has been REMOVED from this file to eliminate
# duplication. The comprehensive InsuranceCompany model in clinic_finance module
# provides all the necessary functionality including:
#   - EDI settings and claims processing
#   - Payment terms and pre-authorization
#   - Policy and claim statistics
#   - Partner integration
#
# All references to 'clinic.insurance.company' now use the clinic_finance version.
# ==============================================================================