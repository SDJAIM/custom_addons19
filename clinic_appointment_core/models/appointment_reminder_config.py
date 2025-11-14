# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AppointmentReminderConfig(models.Model):
    """
    Reminder Configuration for Appointment Types
    Allows multiple reminders per appointment type (TASK-F1-003)
    """
    _name = 'clinic.appointment.reminder.config'
    _description = 'Appointment Reminder Configuration'
    _order = 'type_id, hours_before desc'

    # Basic Information
    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True
    )

    type_id = fields.Many2one(
        'clinic.appointment.type',
        string='Appointment Type',
        required=True,
        ondelete='cascade'
    )

    # Timing
    hours_before = fields.Integer(
        string='Hours Before',
        required=True,
        help='Send reminder X hours before appointment (e.g., 168=7 days, 24=1 day, 2=2 hours)'
    )

    # Channel
    channel = fields.Selection([
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('whatsapp', 'WhatsApp'),
    ], string='Channel', required=True, default='email')

    # Templates (optional - uses default if not set)
    email_template_id = fields.Many2one(
        'mail.template',
        string='Email Template',
        domain="[('model', '=', 'clinic.appointment')]"
    )

    sms_template_id = fields.Many2one(
        'sms.template',
        string='SMS Template',
        domain="[('model', '=', 'clinic.appointment')]"
    )

    # whatsapp_template_id moved to clinic_integrations_whatsapp to avoid dependency

    # Status
    active = fields.Boolean(string='Active', default=True)

    @api.depends('type_id.name', 'hours_before', 'channel')
    def _compute_name(self):
        for reminder in self:
            if reminder.type_id:
                # Convert hours to human-readable format
                if reminder.hours_before >= 168:  # 7+ days
                    days = reminder.hours_before // 24
                    time_str = f"{days} day{'s' if days > 1 else ''}"
                elif reminder.hours_before >= 24:  # 1+ days
                    days = reminder.hours_before // 24
                    time_str = f"{days} day{'s' if days > 1 else ''}"
                else:
                    time_str = f"{reminder.hours_before} hour{'s' if reminder.hours_before > 1 else ''}"

                reminder.name = f"{reminder.type_id.name} - {time_str} before ({reminder.channel})"
            else:
                reminder.name = _('New Reminder')

    @api.constrains('hours_before')
    def _check_hours_before(self):
        for reminder in self:
            if reminder.hours_before <= 0:
                raise ValidationError(_('Hours before must be greater than 0'))
            if reminder.hours_before > 720:  # 30 days
                raise ValidationError(_('Hours before cannot exceed 720 hours (30 days)'))

    @api.constrains('type_id', 'hours_before', 'channel')
    def _check_unique_reminder(self):
        """Prevent duplicate reminders for same time/channel"""
        for reminder in self:
            duplicates = self.search([
                ('id', '!=', reminder.id),
                ('type_id', '=', reminder.type_id.id),
                ('hours_before', '=', reminder.hours_before),
                ('channel', '=', reminder.channel),
                ('active', '=', True)
            ])
            if duplicates:
                raise ValidationError(
                    _('A reminder for this time and channel already exists for this appointment type')
                )
