# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SendWhatsAppWizard(models.TransientModel):
    _name = 'clinic.whatsapp.send.wizard'
    _description = 'Send WhatsApp Message Wizard'

    recipient_type = fields.Selection([
        ('patient', 'Patient'),
        ('staff', 'Staff Member'),
        ('custom', 'Custom Number')
    ], string='Recipient Type', required=True, default='patient')

    patient_id = fields.Many2one('clinic.patient', string='Patient')
    staff_id = fields.Many2one('clinic.staff', string='Staff Member')
    custom_number = fields.Char(string='Phone Number')

    template_id = fields.Many2one(
        'clinic.whatsapp.template',
        string='Message Template'
    )
    message = fields.Text(string='Message', required=True)

    @api.onchange('template_id')
    def _onchange_template(self):
        if self.template_id:
            self.message = self.template_id.body

    @api.onchange('recipient_type')
    def _onchange_recipient_type(self):
        if self.recipient_type == 'patient':
            self.staff_id = False
            self.custom_number = False
        elif self.recipient_type == 'staff':
            self.patient_id = False
            self.custom_number = False
        else:
            self.patient_id = False
            self.staff_id = False

    def action_send(self):
        """Send WhatsApp message"""
        self.ensure_one()

        # Get phone number
        if self.recipient_type == 'patient' and self.patient_id:
            phone = self.patient_id.mobile or self.patient_id.phone
        elif self.recipient_type == 'staff' and self.staff_id:
            phone = self.staff_id.mobile or self.staff_id.phone
        else:
            phone = self.custom_number

        if not phone:
            raise ValueError("No phone number available")

        # Create message record
        self.env['clinic.whatsapp.message'].create({
            'phone': phone,
            'message': self.message,
            'status': 'pending',
            'patient_id': self.patient_id.id if self.patient_id else False,
        })

        return {'type': 'ir.actions.act_window_close'}
