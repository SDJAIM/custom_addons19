# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ClinicAppointmentType(models.Model):
    _name = 'clinic.appointment.type'
    _description = 'Appointment Type'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Type Name',
        required=True,
        translate=True
    )
    
    code = fields.Char(
        string='Code',
        help='Short code for the appointment type'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    service_type = fields.Selection([
        ('medical', 'Medical'),
        ('dental', 'Dental'),
        ('telemed', 'Telemedicine'),
        ('emergency', 'Emergency'),
        ('all', 'All Services')
    ], string='Service Type', default='all', required=True)

    branch_ids = fields.Many2many(
        'clinic.branch',
        'clinic_appointment_type_branch_rel',
        'type_id',
        'branch_id',
        string='Available at Branches',
        help='Branches where this appointment type is available'
    )

    duration = fields.Float(
        string='Default Duration (hours)',
        default=0.5,
        required=True,
        help='Default appointment duration'
    )
    
    color = fields.Integer(
        string='Color',
        default=1,
        help='Color for calendar view'
    )
    
    # Billing
    price = fields.Float(
        string='Standard Price',
        help='Standard price for this appointment type'
    )
    
    auto_invoice = fields.Boolean(
        string='Auto-create Invoice',
        default=False,
        help='Automatically create invoice when appointment is done'
    )
    
    # Insurance
    requires_authorization = fields.Boolean(
        string='Requires Insurance Authorization',
        default=False,
        help='Insurance pre-authorization required'
    )
    
    # Scheduling
    allow_online_booking = fields.Boolean(
        string='Allow Online Booking',
        default=True,
        help='Can be booked through patient portal'
    )
    
    advance_booking_days = fields.Integer(
        string='Advance Booking Days',
        default=30,
        help='How many days in advance can this be booked'
    )
    
    min_advance_hours = fields.Integer(
        string='Minimum Advance Hours',
        default=24,
        help='Minimum hours before appointment can be booked'
    )
    
    max_per_day = fields.Integer(
        string='Max Per Day',
        help='Maximum appointments of this type per day per doctor'
    )
    
    # Follow-up
    follow_up_days = fields.Integer(
        string='Default Follow-up Days',
        help='Default days after for follow-up appointment'
    )
    
    requires_follow_up = fields.Boolean(
        string='Requires Follow-up',
        default=False,
        help='This type typically requires a follow-up'
    )
    
    # Resources
    requires_special_room = fields.Boolean(
        string='Requires Special Room',
        default=False
    )
    
    room_type_required = fields.Selection([
        ('consultation', 'Consultation'),
        ('surgery', 'Surgery'),
        ('emergency', 'Emergency'),
        ('imaging', 'Imaging/X-Ray'),
        ('laboratory', 'Laboratory')
    ], string='Room Type Required')
    
    # Instructions
    patient_instructions = fields.Html(
        string='Patient Instructions',
        help='Instructions shown to patient when booking'
    )
    
    preparation_required = fields.Html(
        string='Preparation Required',
        help='Preparation instructions for patient'
    )
    
    # Settings
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    is_emergency = fields.Boolean(
        string='Emergency Type',
        default=False
    )
    
    priority = fields.Selection([
        ('low', 'Low Priority'),
        ('medium', 'Medium Priority'),
        ('high', 'High Priority'),
        ('urgent', 'Urgent')
    ], string='Default Priority', default='medium')
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Appointment type code must be unique!'),
    ]
    
    @api.onchange('is_emergency')
    def _onchange_is_emergency(self):
        if self.is_emergency:
            self.priority = 'urgent'
            self.min_advance_hours = 0
            self.allow_online_booking = False