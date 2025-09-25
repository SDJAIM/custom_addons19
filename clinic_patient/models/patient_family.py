# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ClinicPatientFamily(models.Model):
    _name = 'clinic.patient.family'
    _description = 'Patient Family Member'
    _rec_name = 'member_name'
    
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
    
    member_name = fields.Char(
        string='Family Member Name',
        required=True
    )
    
    relationship = fields.Selection([
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('spouse', 'Spouse'),
        ('son', 'Son'),
        ('daughter', 'Daughter'),
        ('brother', 'Brother'),
        ('sister', 'Sister'),
        ('grandfather', 'Grandfather'),
        ('grandmother', 'Grandmother'),
        ('uncle', 'Uncle'),
        ('aunt', 'Aunt'),
        ('cousin', 'Cousin'),
        ('other', 'Other')
    ], string='Relationship', required=True)
    
    is_patient = fields.Boolean(
        string='Is Also a Patient',
        help='Check if this family member is also registered as a patient'
    )
    
    related_patient_id = fields.Many2one(
        'clinic.patient',
        string='Related Patient Record',
        domain="[('id', '!=', patient_id)]",
        help='Link to patient record if family member is also a patient'
    )
    
    date_of_birth = fields.Date(string='Date of Birth')
    
    age = fields.Integer(
        string='Age',
        compute='_compute_age',
        store=True
    )
    
    phone = fields.Char(string='Phone Number')
    email = fields.Char(string='Email')
    
    medical_conditions = fields.Text(
        string='Medical Conditions',
        help='Relevant medical conditions for family history'
    )
    
    is_emergency_contact = fields.Boolean(
        string='Emergency Contact',
        help='Use as emergency contact for the patient'
    )
    
    notes = fields.Text(string='Notes')
    
    @api.depends('date_of_birth')
    def _compute_age(self):
        from datetime import date
        today = date.today()
        for record in self:
            if record.date_of_birth:
                born = record.date_of_birth
                age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
                record.age = age
            else:
                record.age = 0
    
    @api.onchange('is_patient')
    def _onchange_is_patient(self):
        if not self.is_patient:
            self.related_patient_id = False
    
    @api.constrains('patient_id', 'related_patient_id')
    def _check_related_patient(self):
        for record in self:
            if record.related_patient_id and record.related_patient_id == record.patient_id:
                raise ValidationError(_("A patient cannot be their own family member!"))
    
    @api.model_create_multi
    def create(self, vals_list):
        # If marked as emergency contact, update patient's emergency contact
        family_members = super().create(vals_list)
        for family_member in family_members:
            if family_member.is_emergency_contact:
                family_member.patient_id.write({
                    'emergency_contact_name': family_member.member_name,
                    'emergency_contact_phone': family_member.phone,
                    'emergency_contact_relation': dict(self._fields['relationship'].selection).get(family_member.relationship),
                    'emergency_contact_email': family_member.email,
                })
        return family_members
    
    def write(self, vals):
        res = super().write(vals)
        # Update emergency contact if needed
        if vals.get('is_emergency_contact'):
            for record in self:
                if record.is_emergency_contact:
                    record.patient_id.write({
                        'emergency_contact_name': record.member_name,
                        'emergency_contact_phone': record.phone,
                        'emergency_contact_relation': dict(self._fields['relationship'].selection).get(record.relationship),
                        'emergency_contact_email': record.email,
                    })
        return res