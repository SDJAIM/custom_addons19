# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PatientWhatsAppExtension(models.Model):
    """
    Extend clinic.patient with WhatsApp thread information

    Fase 3.2: Add 24h window indicators to patient form
    """
    _inherit = 'clinic.patient'

    # WhatsApp thread relationship
    whatsapp_thread_id = fields.Many2one(
        'clinic.whatsapp.thread',
        string='WhatsApp Thread',
        compute='_compute_whatsapp_thread',
        help='Active WhatsApp conversation thread'
    )

    # Fase 3.2: UI indicators from thread
    whatsapp_window_status = fields.Char(
        string='WhatsApp Window Status',
        related='whatsapp_thread_id.window_status_text',
        readonly=True
    )

    whatsapp_time_remaining = fields.Char(
        string='WhatsApp Time Remaining',
        related='whatsapp_thread_id.window_time_remaining',
        readonly=True
    )

    whatsapp_urgency_level = fields.Selection(
        string='WhatsApp Urgency',
        related='whatsapp_thread_id.window_urgency_level',
        readonly=True
    )

    whatsapp_can_send_text = fields.Boolean(
        string='Can Send Free Text',
        related='whatsapp_thread_id.can_send_text',
        readonly=True
    )

    whatsapp_requires_template = fields.Boolean(
        string='Requires Template',
        related='whatsapp_thread_id.requires_template',
        readonly=True
    )

    whatsapp_last_message = fields.Text(
        string='Last WhatsApp Message',
        related='whatsapp_thread_id.last_message_body',
        readonly=True
    )

    whatsapp_message_count = fields.Integer(
        string='WhatsApp Messages',
        compute='_compute_whatsapp_stats',
        help='Total WhatsApp messages exchanged'
    )

    whatsapp_has_active_thread = fields.Boolean(
        string='Has WhatsApp Thread',
        compute='_compute_whatsapp_thread',
        help='True if patient has an active WhatsApp conversation'
    )

    @api.depends('mobile', 'phone')
    def _compute_whatsapp_thread(self):
        """
        Find active WhatsApp thread for this patient

        Uses mobile first, then phone
        """
        for patient in self:
            phone = patient.mobile or patient.phone

            if phone:
                thread = self.env['clinic.whatsapp.thread'].search([
                    ('patient_id', '=', patient.id),
                    ('active', '=', True),
                ], limit=1, order='last_inbound_at desc')

                patient.whatsapp_thread_id = thread.id if thread else False
                patient.whatsapp_has_active_thread = bool(thread)
            else:
                patient.whatsapp_thread_id = False
                patient.whatsapp_has_active_thread = False

    def _compute_whatsapp_stats(self):
        """
        Compute WhatsApp message statistics
        """
        for patient in self:
            if patient.whatsapp_thread_id:
                patient.whatsapp_message_count = (
                    patient.whatsapp_thread_id.inbound_count +
                    patient.whatsapp_thread_id.outbound_count
                )
            else:
                patient.whatsapp_message_count = 0

    def action_send_whatsapp_message(self):
        """
        Open wizard to send WhatsApp message

        Fase 3.4: Context includes window status for smart defaults
        """
        self.ensure_one()

        if not self.mobile and not self.phone:
            raise UserError(
                _("Patient has no phone number configured.\n\n"
                  "Please add a mobile or phone number first.")
            )

        # Get or create thread
        phone = self.mobile or self.phone
        thread = self.env['clinic.whatsapp.thread'].get_or_create_thread(
            patient_id=self.id,
            phone_number=phone
        )

        # Determine if can send free text
        window_status = thread.can_send_free_text()

        return {
            'name': 'Send WhatsApp Message',
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.whatsapp.message.wizard',  # To be created in Fase 3.4
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_patient_id': self.id,
                'default_phone_number': phone,
                'whatsapp_window_open': window_status['allowed'],
                'whatsapp_window_status': thread.window_status_text,
                'whatsapp_requires_template': thread.requires_template,
            }
        }

    def action_view_whatsapp_thread(self):
        """
        Open WhatsApp thread for this patient
        """
        self.ensure_one()

        if not self.whatsapp_thread_id:
            raise UserError(
                _("No WhatsApp conversation found for this patient.")
            )

        return {
            'name': f'WhatsApp - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.whatsapp.thread',
            'res_id': self.whatsapp_thread_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_whatsapp_messages(self):
        """
        View all WhatsApp messages for this patient
        """
        self.ensure_one()

        return {
            'name': f'WhatsApp Messages - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.whatsapp.message',
            'view_mode': 'tree,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {
                'default_patient_id': self.id,
            }
        }
