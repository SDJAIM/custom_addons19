# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ToothHistory(models.Model):
    _name = 'clinic.tooth.history'
    _description = 'Tooth History'
    _order = 'date desc, create_date desc'
    _rec_name = 'description'
    
    tooth_id = fields.Many2one(
        'clinic.tooth',
        string='Tooth',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        related='tooth_id.patient_id',
        store=True,
        readonly=True
    )
    
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        index=True
    )
    
    action = fields.Selection([
        ('examination', 'Examination'),
        ('procedure', 'Procedure'),
        ('state_change', 'State Change'),
        ('xray', 'X-ray'),
        ('note', 'Note Added'),
        ('update', 'Update'),
    ], string='Action Type', required=True)
    
    description = fields.Text(
        string='Description',
        required=True
    )
    
    # State tracking
    old_state = fields.Selection([
        ('healthy', 'Healthy'),
        ('decayed', 'Decayed'),
        ('filled', 'Filled'),
        ('crown', 'Crown'),
        ('bridge', 'Bridge'),
        ('implant', 'Implant'),
        ('root_canal', 'Root Canal'),
        ('missing', 'Missing'),
        ('impacted', 'Impacted'),
        ('fractured', 'Fractured'),
    ], string='Previous State')
    
    new_state = fields.Selection([
        ('healthy', 'Healthy'),
        ('decayed', 'Decayed'),
        ('filled', 'Filled'),
        ('crown', 'Crown'),
        ('bridge', 'Bridge'),
        ('implant', 'Implant'),
        ('root_canal', 'Root Canal'),
        ('missing', 'Missing'),
        ('impacted', 'Impacted'),
        ('fractured', 'Fractured'),
    ], string='New State')
    
    # Related records
    procedure_id = fields.Many2one(
        'clinic.dental.procedure',
        string='Procedure'
    )
    
    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Appointment'
    )
    
    treatment_id = fields.Many2one(
        'clinic.treatment.plan.line',
        string='Treatment'
    )
    
    # User tracking
    user_id = fields.Many2one(
        'res.users',
        string='Performed By',
        default=lambda self: self.env.user,
        required=True
    )
    
    doctor_id = fields.Many2one(
        'clinic.staff',
        string='Doctor',
        domain=[('is_practitioner', '=', True)]
    )
    
    # Additional information
    notes = fields.Text(
        string='Notes'
    )
    
    attachments = fields.Many2many(
        'ir.attachment',
        string='Attachments'
    )