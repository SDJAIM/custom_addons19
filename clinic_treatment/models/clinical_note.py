# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime
from odoo.exceptions import AccessError


class ClinicalNote(models.Model):
    _name = 'clinic.clinical.note'
    _description = 'Clinical Note'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    _rec_name = 'display_name'
    
    # ========================
    # Basic Information
    # ========================
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        tracking=True,
        ondelete='restrict'
    )
    
    doctor_id = fields.Many2one(
        'clinic.staff',
        string='Doctor/Clinician',
        required=True,
        default=lambda self: self._get_default_doctor(),
        tracking=True,
        domain="[('staff_type', 'in', ['doctor', 'dentist', 'nurse'])]"
    )
    
    date = fields.Datetime(
        string='Date & Time',
        required=True,
        default=fields.Datetime.now,
        tracking=True
    )
    
    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Related Appointment',
        help='Appointment this note is related to'
    )
    
    treatment_plan_id = fields.Many2one(
        'clinic.treatment.plan',
        string='Treatment Plan',
        help='Treatment plan this note belongs to'
    )
    
    # ========================
    # Note Content
    # ========================
    note_type = fields.Selection([
        ('progress', 'Progress Note'),
        ('consultation', 'Consultation Note'),
        ('procedure', 'Procedure Note'),
        ('discharge', 'Discharge Summary'),
        ('referral', 'Referral Note'),
        ('follow_up', 'Follow-up Note'),
        ('phone', 'Phone Consultation'),
        ('other', 'Other')
    ], string='Note Type', required=True, default='progress')
    
    chief_complaint = fields.Text(
        string='Chief Complaint',
        help='Main reason for visit'
    )
    
    subjective = fields.Text(
        string='Subjective (S)',
        help='Patient\'s description of symptoms/concerns'
    )
    
    objective = fields.Text(
        string='Objective (O)',
        help='Clinical findings and observations'
    )
    
    assessment = fields.Text(
        string='Assessment (A)',
        help='Clinical assessment and diagnosis'
    )
    
    plan = fields.Text(
        string='Plan (P)',
        help='Treatment plan and next steps'
    )
    
    # Combined SOAP note
    soap_note = fields.Html(
        string='SOAP Note',
        compute='_compute_soap_note',
        store=True
    )
    
    # ========================
    # Vital Signs
    # ========================
    blood_pressure_systolic = fields.Integer(
        string='BP Systolic (mmHg)'
    )
    
    blood_pressure_diastolic = fields.Integer(
        string='BP Diastolic (mmHg)'
    )
    
    pulse = fields.Integer(
        string='Pulse (bpm)'
    )
    
    temperature = fields.Float(
        string='Temperature (°C)'
    )
    
    respiratory_rate = fields.Integer(
        string='Respiratory Rate (rpm)'
    )
    
    weight = fields.Float(
        string='Weight (kg)'
    )
    
    height = fields.Float(
        string='Height (cm)'
    )
    
    bmi = fields.Float(
        string='BMI',
        compute='_compute_bmi',
        store=True
    )
    
    # ========================
    # Confidentiality (KEY FEATURE)
    # ========================
    is_confidential = fields.Boolean(
        string='Confidential',
        default=False,
        tracking=True,
        help='Mark this note as confidential - only accessible to authorized personnel'
    )
    
    confidentiality_reason = fields.Text(
        string='Confidentiality Reason',
        help='Reason for marking this note as confidential'
    )
    
    authorized_user_ids = fields.Many2many(
        'res.users',
        'clinical_note_authorized_users_rel',
        'note_id',
        'user_id',
        string='Authorized Users',
        help='Additional users who can access this confidential note'
    )
    
    # ========================
    # Additional Information
    # ========================
    medications_given = fields.Text(
        string='Medications Given'
    )
    
    procedures_performed = fields.Text(
        string='Procedures Performed'
    )
    
    lab_results = fields.Text(
        string='Lab Results'
    )
    
    imaging_results = fields.Text(
        string='Imaging Results'
    )
    
    allergies_noted = fields.Text(
        string='New Allergies Noted'
    )
    
    # ========================
    # Follow-up
    # ========================
    requires_follow_up = fields.Boolean(
        string='Requires Follow-up',
        default=False
    )
    
    follow_up_date = fields.Date(
        string='Follow-up Date'
    )
    
    follow_up_instructions = fields.Text(
        string='Follow-up Instructions'
    )
    
    # ========================
    # Attachments
    # ========================
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'clinical_note_attachment_rel',
        'note_id',
        'attachment_id',
        string='Attachments'
    )
    
    attachment_count = fields.Integer(
        string='Attachments',
        compute='_compute_attachment_count'
    )
    
    # ========================
    # Review & Signature
    # ========================
    reviewed_by = fields.Many2one(
        'res.users',
        string='Reviewed By'
    )
    
    review_date = fields.Datetime(
        string='Review Date'
    )
    
    is_signed = fields.Boolean(
        string='Signed',
        default=False,
        tracking=True
    )
    
    signature_date = fields.Datetime(
        string='Signature Date'
    )
    
    # ========================
    # Display
    # ========================
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    summary = fields.Char(
        string='Summary',
        help='Brief summary of the note'
    )
    
    # ========================
    # Methods
    # ========================
    def _get_default_doctor(self):
        """Get default doctor from current user's staff record"""
        staff = self.env['clinic.staff'].search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        return staff.id if staff else False
    
    @api.depends('patient_id', 'date', 'note_type')
    def _compute_display_name(self):
        type_names = dict(self._fields['note_type'].selection)
        for record in self:
            if record.patient_id and record.date:
                date_str = record.date.strftime('%Y-%m-%d %H:%M')
                type_str = type_names.get(record.note_type, 'Note')
                record.display_name = f"{record.patient_id.name} - {type_str} - {date_str}"
            else:
                record.display_name = "Clinical Note"
    
    @api.depends('subjective', 'objective', 'assessment', 'plan')
    def _compute_soap_note(self):
        for record in self:
            html_parts = []
            if record.subjective:
                html_parts.append(f"<p><b>Subjective:</b><br/>{record.subjective}</p>")
            if record.objective:
                html_parts.append(f"<p><b>Objective:</b><br/>{record.objective}</p>")
            if record.assessment:
                html_parts.append(f"<p><b>Assessment:</b><br/>{record.assessment}</p>")
            if record.plan:
                html_parts.append(f"<p><b>Plan:</b><br/>{record.plan}</p>")
            
            record.soap_note = ''.join(html_parts) if html_parts else False
    
    @api.depends('weight', 'height')
    def _compute_bmi(self):
        for record in self:
            if record.weight and record.height:
                height_m = record.height / 100  # Convert cm to meters
                record.bmi = record.weight / (height_m ** 2)
            else:
                record.bmi = 0
    
    def _compute_attachment_count(self):
        for record in self:
            record.attachment_count = len(record.attachment_ids)
    
    @api.model
    def create(self, vals):
        # Auto-sign if created by doctor
        note = super().create(vals)
        if note.doctor_id.user_id == self.env.user:
            note.action_sign()
        return note
    
    def write(self, vals):
        # Check confidential access
        if self.filtered(lambda n: n.is_confidential):
            self._check_confidential_access()
        return super().write(vals)
    
    def read(self, fields=None, load='_classic_read'):
        # Check confidential access for reading
        if self.filtered(lambda n: n.is_confidential):
            self._check_confidential_access()
        return super().read(fields, load)
    
    def _check_confidential_access(self):
        """Check if current user can access confidential notes"""
        for record in self.filtered(lambda n: n.is_confidential):
            # Check if user is the doctor who created it
            if record.doctor_id.user_id == self.env.user:
                continue
            
            # Check if user is in authorized users
            if self.env.user in record.authorized_user_ids:
                continue
            
            # Check if user has special group
            if self.env.user.has_group('clinic_treatment.group_clinical_confidential'):
                continue
            
            # Check if user is clinic manager
            if self.env.user.has_group('clinic_treatment.group_treatment_manager'):
                continue
            
            raise AccessError(_(
                "You don't have access to this confidential clinical note. "
                "Only authorized personnel can view confidential notes."
            ))
    
    def action_sign(self):
        """Sign the clinical note"""
        for record in self:
            if record.is_signed:
                continue
            
            # Check if user is the doctor
            if record.doctor_id.user_id != self.env.user:
                raise AccessError(_("Only the attending doctor can sign this note."))
            
            record.write({
                'is_signed': True,
                'signature_date': fields.Datetime.now()
            })
    
    def action_request_review(self):
        """Request review from supervisor"""
        for record in self:
            # Create activity for review
            record.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Review Clinical Note'),
                note=_(f'Please review clinical note for patient {record.patient_id.name}'),
                user_id=record.doctor_id.user_id.id if record.doctor_id.user_id else self.env.user.id
            )
    
    def action_mark_reviewed(self):
        """Mark note as reviewed"""
        for record in self:
            record.write({
                'reviewed_by': self.env.user.id,
                'review_date': fields.Datetime.now()
            })
    
    def action_print_note(self):
        """Print clinical note"""
        self.ensure_one()

        # Check if custom report exists
        report = self.env.ref('clinic_treatment.report_clinical_note', raise_if_not_found=False)

        if report:
            return report.report_action(self)
        else:
            # If no custom report, use standard method
            return {
                'type': 'ir.actions.report',
                'report_name': 'clinic_treatment.clinical_note_report',
                'report_type': 'qweb-pdf',
                'data': None,
                'context': self.env.context,
                'res_ids': self.ids,
            }
    
    @api.onchange('requires_follow_up')
    def _onchange_requires_follow_up(self):
        if not self.requires_follow_up:
            self.follow_up_date = False
            self.follow_up_instructions = False