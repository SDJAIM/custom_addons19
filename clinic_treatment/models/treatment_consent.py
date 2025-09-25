# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime


class TreatmentConsent(models.Model):
    _name = 'clinic.treatment.consent'
    _description = 'Treatment Consent Form'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'consent_date desc'
    
    name = fields.Char(
        string='Consent Reference',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New')
    )
    
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        tracking=True
    )
    
    treatment_plan_id = fields.Many2one(
        'clinic.treatment.plan',
        string='Treatment Plan',
        required=True
    )
    
    consent_type = fields.Selection([
        ('treatment', 'Treatment Consent'),
        ('surgery', 'Surgical Consent'),
        ('anesthesia', 'Anesthesia Consent'),
        ('research', 'Research Participation'),
        ('photography', 'Photography/Recording'),
        ('data_sharing', 'Data Sharing')
    ], string='Consent Type', required=True, default='treatment')
    
    consent_date = fields.Datetime(
        string='Consent Date',
        required=True,
        default=fields.Datetime.now,
        tracking=True
    )
    
    # Consent details
    procedure_names = fields.Text(
        string='Procedures',
        compute='_compute_procedure_names',
        store=True
    )
    
    risks_explained = fields.Boolean(
        string='Risks Explained',
        default=True,
        tracking=True
    )
    
    benefits_explained = fields.Boolean(
        string='Benefits Explained',
        default=True,
        tracking=True
    )
    
    alternatives_explained = fields.Boolean(
        string='Alternatives Explained',
        default=True,
        tracking=True
    )
    
    questions_answered = fields.Boolean(
        string='Questions Answered',
        default=True,
        tracking=True
    )
    
    # Consent content
    consent_text = fields.Html(
        string='Consent Form Text',
        required=True
    )
    
    additional_notes = fields.Text(
        string='Additional Notes'
    )
    
    # Signatures
    patient_signature = fields.Binary(
        string='Patient Signature',
        attachment=True
    )
    
    patient_signed_date = fields.Datetime(
        string='Patient Signed Date'
    )
    
    witness_name = fields.Char(
        string='Witness Name'
    )
    
    witness_signature = fields.Binary(
        string='Witness Signature',
        attachment=True
    )
    
    witness_signed_date = fields.Datetime(
        string='Witness Signed Date'
    )
    
    doctor_id = fields.Many2one(
        'clinic.staff',
        string='Doctor',
        required=True,
        domain="[('staff_type', 'in', ['doctor', 'dentist'])]"
    )
    
    doctor_signature = fields.Binary(
        string='Doctor Signature',
        attachment=True
    )
    
    doctor_signed_date = fields.Datetime(
        string='Doctor Signed Date'
    )
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Signature'),
        ('signed', 'Signed'),
        ('revoked', 'Revoked')
    ], string='Status', default='draft', tracking=True)
    
    revoke_date = fields.Datetime(
        string='Revoke Date'
    )
    
    revoke_reason = fields.Text(
        string='Revoke Reason'
    )
    
    # Validity
    valid_until = fields.Date(
        string='Valid Until',
        help='Leave empty for indefinite validity'
    )
    
    is_expired = fields.Boolean(
        string='Expired',
        compute='_compute_is_expired'
    )
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('clinic.treatment.consent') or _('New')
        return super().create(vals)
    
    @api.depends('treatment_plan_id.line_ids.procedure_id')
    def _compute_procedure_names(self):
        for record in self:
            if record.treatment_plan_id and record.treatment_plan_id.line_ids:
                procedures = record.treatment_plan_id.line_ids.mapped('procedure_id.name')
                record.procedure_names = ', '.join(procedures)
            else:
                record.procedure_names = ''
    
    @api.depends('valid_until', 'state')
    def _compute_is_expired(self):
        today = fields.Date.today()
        for record in self:
            record.is_expired = (
                record.valid_until and 
                record.valid_until < today and 
                record.state == 'signed'
            )
    
    def action_request_signature(self):
        """Send consent form for signature"""
        for record in self:
            if record.state != 'draft':
                continue
            
            record.state = 'pending'
            
            # Send notification to patient
            # This would integrate with digital signature solution
    
    def action_sign_patient(self):
        """Record patient signature"""
        for record in self:
            if record.state != 'pending':
                continue
            
            record.patient_signed_date = fields.Datetime.now()
            
            # Check if all signatures collected
            if record.doctor_signature:
                record.state = 'signed'
    
    def action_sign_doctor(self):
        """Record doctor signature"""
        for record in self:
            if record.state not in ['pending', 'draft']:
                continue
            
            record.doctor_signed_date = fields.Datetime.now()
            
            # Check if all signatures collected
            if record.patient_signature:
                record.state = 'signed'
    
    def action_revoke(self):
        """Revoke consent"""
        for record in self:
            if record.state != 'signed':
                continue
            
            record.write({
                'state': 'revoked',
                'revoke_date': fields.Datetime.now()
            })
    
    def action_print_consent(self):
        """Print consent form"""
        self.ensure_one()

        # Check if custom report exists
        report = self.env.ref('clinic_treatment.report_treatment_consent', raise_if_not_found=False)

        if report:
            return report.report_action(self)
        else:
            # If no custom report, use standard method
            return {
                'type': 'ir.actions.report',
                'report_name': 'clinic_treatment.consent_form_report',
                'report_type': 'qweb-pdf',
                'data': None,
                'context': self.env.context,
                'res_ids': self.ids,
            }


class Diagnosis(models.Model):
    _name = 'clinic.diagnosis'
    _description = 'Medical Diagnosis'
    _order = 'code'
    
    name = fields.Char(
        string='Diagnosis',
        required=True
    )
    
    code = fields.Char(
        string='ICD Code',
        required=True,
        help='ICD-10 or other classification code'
    )
    
    category = fields.Char(
        string='Category'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Diagnosis code must be unique!'),
    ]