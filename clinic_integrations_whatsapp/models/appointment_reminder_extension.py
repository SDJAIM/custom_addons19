# -*- coding: utf-8 -*-

from odoo import fields, models


class AppointmentReminderConfigExtension(models.Model):
    """Extend appointment reminder config with WhatsApp template field"""
    _inherit = 'clinic.appointment.reminder.config'

    whatsapp_template_id = fields.Many2one(
        'clinic.whatsapp.template',
        string='WhatsApp Template',
        help='WhatsApp template to use for this reminder'
    )


class AppointmentReminderSentExtension(models.Model):
    """Extend appointment reminder sent log with WhatsApp message reference"""
    _inherit = 'clinic.appointment.reminder.sent'

    whatsapp_message_id = fields.Many2one(
        'clinic.whatsapp.message',
        string='WhatsApp Message',
        help='Reference to the sent WhatsApp message'
    )
