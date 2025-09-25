# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class WhatsAppTemplate(models.Model):
    _name = 'clinic.whatsapp.template'
    _description = 'WhatsApp Message Template'
    
    name = fields.Char(string='Template Name', required=True)
    template_name = fields.Char(string='WhatsApp Template ID')
    template_type = fields.Selection([
        ('appointment_reminder', 'Appointment Reminder'),
        ('appointment_confirmation', 'Appointment Confirmation'),
        ('prescription_reminder', 'Prescription Reminder'),
        ('general', 'General'),
    ], string='Type', default='general')
    
    language_code = fields.Char(string='Language Code', default='en')
    message_body = fields.Text(string='Message Template')
    active = fields.Boolean(string='Active', default=True)