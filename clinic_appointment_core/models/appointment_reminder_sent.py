# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AppointmentReminderSent(models.Model):
    """
    Track which reminders have been sent for each appointment (TASK-F1-003)
    Allows multiple reminders per appointment
    """
    _name = 'clinic.appointment.reminder.sent'
    _description = 'Appointment Reminder Sent Log'
    _order = 'sent_date desc'

    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Appointment',
        required=True,
        ondelete='cascade',
        index=True
    )

    reminder_config_id = fields.Many2one(
        'clinic.appointment.reminder.config',
        string='Reminder Configuration',
        required=True,
        ondelete='restrict'
    )

    channel = fields.Selection(
        related='reminder_config_id.channel',
        string='Channel',
        store=True
    )

    hours_before = fields.Integer(
        related='reminder_config_id.hours_before',
        string='Hours Before',
        store=True
    )

    sent_date = fields.Datetime(
        string='Sent Date',
        default=fields.Datetime.now,
        required=True
    )

    status = fields.Selection([
        ('success', 'Sent Successfully'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ], string='Status', default='pending', required=True)

    error_message = fields.Text(string='Error Message')

    # Optional: reference to mail/sms/whatsapp message
    mail_message_id = fields.Many2one('mail.message', string='Email Message')
    sms_message_id = fields.Many2one('sms.sms', string='SMS Message')
    # whatsapp_message_id moved to clinic_integrations_whatsapp to avoid dependency

    def name_get(self):
        result = []
        for record in self:
            name = f"{record.appointment_id.appointment_number} - {record.hours_before}h before ({record.channel})"
            result.append((record.id, name))
        return result
