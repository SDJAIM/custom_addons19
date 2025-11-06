# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AppointmentType(models.Model):
    """
    Appointment Type Configuration
    Replicates Odoo Enterprise Appointments functionality in Community
    """
    _name = 'clinic.appointment.type'
    _description = 'Appointment Type'
    _order = 'sequence, name'

    # BASIC INFORMATION
    name = fields.Char(string='Name', required=True, translate=True)
    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Html(string='Description', translate=True)
    color = fields.Integer(string='Color')

    # DURATION & SCHEDULING
    default_duration = fields.Float(string='Default Duration', required=True, default=1.0, help='Duration in hours')
    buffer_before = fields.Float(string='Buffer Before', default=0.0, help='Hours before appointment')
    buffer_after = fields.Float(string='Buffer After', default=0.0, help='Hours after appointment')

    # ONLINE BOOKING
    allow_online_booking = fields.Boolean(string='Allow Online Booking', default=True)
    min_notice_hours = fields.Integer(string='Minimum Notice (hours)', default=24)
    max_days_ahead = fields.Integer(string='Maximum Days Ahead', default=30)

    # CAPACITY
    capacity_per_slot = fields.Integer(string='Capacity per Slot', default=1)

    # STAFF ASSIGNMENT
    assign_mode = fields.Selection([
        ('random', 'Random'),
        ('round_robin', 'Round Robin'),
        ('by_skill', 'By Skill'),
        ('customer_choice', 'Customer Choice'),
    ], string='Assignment Mode', default='customer_choice', required=True)

    allowed_staff_ids = fields.Many2many('hr.employee', 'appointment_type_staff_rel', string='Allowed Staff')

    # MEETING MODE
    meeting_mode = fields.Selection([
        ('onsite', 'On-site'),
        ('online', 'Online'),
        ('phone', 'Phone'),
    ], string='Meeting Mode', default='onsite', required=True)

    location_id = fields.Many2one('res.partner', string='Location')
    conferencing_url_template = fields.Char(string='Conferencing URL')

    # RESCHEDULE & CANCEL
    allow_reschedule = fields.Boolean(string='Allow Rescheduling', default=True)
    reschedule_limit_hours = fields.Integer(string='Reschedule Limit (hours)', default=24)
    allow_cancel = fields.Boolean(string='Allow Cancellation', default=True)
    cancel_limit_hours = fields.Integer(string='Cancellation Limit (hours)', default=24)

    # REMINDERS
    reminder_hours_before = fields.Integer(string='Reminder Hours Before', default=24)
    send_confirmation_email = fields.Boolean(string='Send Confirmation Email', default=True)

    # STATISTICS
    appointment_count = fields.Integer(compute='_compute_appointment_count')
    rule_count = fields.Integer(compute='_compute_rule_count')

    @api.depends('allowed_staff_ids')
    def _compute_appointment_count(self):
        for rec in self:
            rec.appointment_count = self.env['clinic.appointment'].search_count([('appointment_type_id', '=', rec.id)])

    @api.depends('allowed_staff_ids')
    def _compute_rule_count(self):
        for rec in self:
            rec.rule_count = self.env['clinic.appointment.rule'].search_count([('type_id', '=', rec.id)])

    @api.constrains('default_duration')
    def _check_default_duration(self):
        for rec in self:
            if rec.default_duration <= 0:
                raise ValidationError(_('Duration must be greater than 0'))

    def action_view_appointments(self):
        self.ensure_one()
        return {
            'name': _('Appointments: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.appointment',
            'view_mode': 'tree,form,calendar',
            'domain': [('appointment_type_id', '=', self.id)],
        }

    def get_total_duration_with_buffers(self):
        self.ensure_one()
        return self.default_duration + self.buffer_before + self.buffer_after
