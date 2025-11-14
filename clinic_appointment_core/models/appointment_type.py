# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import qrcode  # TASK-F1-002: QR code generation
import base64
from io import BytesIO


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

    # SEASONAL AVAILABILITY (Enterprise parity - TASK-F1-004)
    active_from = fields.Date(
        string='Active From',
        help='Leave empty for permanent availability'
    )
    active_to = fields.Date(
        string='Active To',
        help='Leave empty for permanent availability'
    )

    # CAPACITY
    capacity_per_slot = fields.Integer(string='Capacity per Slot', default=1)

    # GUESTS (TASK-F2-002)
    allow_guests = fields.Boolean(
        string='Allow Guests',
        default=False,
        help='Allow patients to bring accompanying guests to appointments'
    )
    max_guests = fields.Integer(
        string='Maximum Guests',
        default=3,
        help='Maximum number of guests allowed per appointment (0-3)'
    )

    # STAFF ASSIGNMENT
    assign_mode = fields.Selection([
        ('random', 'Random'),
        ('round_robin', 'Round Robin'),
        ('by_skill', 'By Skill'),
        ('by_team', 'By Team'),
        ('customer_choice', 'Customer Choice'),
    ], string='Assignment Mode', default='customer_choice', required=True)

    # Team Assignment (TASK-F2-001)
    team_id = fields.Many2one(
        'clinic.appointment.team',
        string='Appointment Team',
        help='Team responsible for appointments of this type'
    )

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

    # REMINDERS (Legacy single reminder - kept for backward compatibility)
    reminder_hours_before = fields.Integer(string='Reminder Hours Before', default=24)
    send_confirmation_email = fields.Boolean(string='Send Confirmation Email', default=True)

    # Multiple Reminders Config (TASK-F1-003)
    reminder_ids = fields.One2many(
        'clinic.appointment.reminder.config',
        'type_id',
        string='Reminders',
        help='Configure multiple reminders at different times and channels'
    )

    # STATISTICS
    appointment_count = fields.Integer(compute='_compute_appointment_count')
    rule_count = fields.Integer(compute='_compute_rule_count')

    # SHAREABLE BOOKING LINK (TASK-F1-002)
    shareable_url = fields.Char(
        string='Shareable Booking URL',
        compute='_compute_shareable_url',
        help='Public URL that allows direct booking for this appointment type'
    )
    qr_code = fields.Binary(
        string='QR Code',
        compute='_compute_qr_code',
        help='QR code for the shareable booking URL'
    )

    @api.depends('allowed_staff_ids')
    def _compute_appointment_count(self):
        for rec in self:
            rec.appointment_count = self.env['clinic.appointment'].search_count([('appointment_type_id', '=', rec.id)])

    @api.depends('allowed_staff_ids')
    def _compute_rule_count(self):
        for rec in self:
            rec.rule_count = self.env['clinic.appointment.rule'].search_count([('type_id', '=', rec.id)])

    def _compute_shareable_url(self):
        """TASK-F1-002: Generate shareable booking URL"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            if rec.id:
                rec.shareable_url = f"{base_url}/appointments/{rec.id}/book"
            else:
                rec.shareable_url = False

    def _compute_qr_code(self):
        """TASK-F1-002: Generate QR code for shareable URL"""
        for rec in self:
            if rec.shareable_url:
                try:
                    # Generate QR code
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(rec.shareable_url)
                    qr.make(fit=True)

                    # Create image
                    img = qr.make_image(fill_color="black", back_color="white")

                    # Convert to base64
                    buffer = BytesIO()
                    img.save(buffer, format='PNG')
                    rec.qr_code = base64.b64encode(buffer.getvalue())
                except Exception as e:
                    # If QR code generation fails, log but don't block
                    import logging
                    _logger = logging.getLogger(__name__)
                    _logger.warning("Failed to generate QR code for appointment type %s: %s", rec.name, str(e))
                    rec.qr_code = False
            else:
                rec.qr_code = False

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

    def action_share_link(self):
        """TASK-F1-002: Open share dialog with URL and QR code"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Share Booking Link'),
            'res_model': 'clinic.appointment.type',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('clinic_appointment_core.view_appointment_type_share_dialog').id,
            'target': 'new',
            'context': {'dialog_size': 'medium'},
        }

    def get_total_duration_with_buffers(self):
        self.ensure_one()
        return self.default_duration + self.buffer_before + self.buffer_after

    @api.model
    def get_available_types(self, date=None):
        """
        Return only active appointment types for given date (seasonal filtering)

        Args:
            date: date object or False (defaults to today)

        Returns:
            recordset: Available appointment types
        """
        today = date or fields.Date.today()

        domain = [
            ('allow_online_booking', '=', True),
            '|', ('active_from', '=', False), ('active_from', '<=', today),
            '|', ('active_to', '=', False), ('active_to', '>=', today),
        ]

        return self.search(domain)

    def write(self, vals):
        """Update type and invalidate cache if critical fields change"""
        result = super().write(vals)

        # ⚡ CACHE INVALIDATION (P0-003): Only invalidate if fields affecting slots change
        critical_fields = ['default_duration', 'buffer_before', 'buffer_after', 'capacity_per_slot']
        if any(field in vals for field in critical_fields):
            self.env['clinic.appointment.slot.engine']._invalidate_slot_cache()

        return result
