# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PrescriptionWhatsAppIntegration(models.Model):
    """
    Extends clinic.prescription with WhatsApp messaging capabilities

    Fase 4.2: Send from Apps - Prescription Integration
    Allows sending WhatsApp messages directly from prescription records
    """
    _inherit = 'clinic.prescription'

    # WhatsApp-related computed fields
    whatsapp_phone = fields.Char(
        string='WhatsApp Phone',
        related='patient_id.mobile',
        readonly=True,
        help='Patient mobile number for WhatsApp'
    )

    can_send_whatsapp = fields.Boolean(
        string='Can Send WhatsApp',
        compute='_compute_can_send_whatsapp',
        store=True,
        help='True if patient has mobile number and WhatsApp opt-in'
    )

    whatsapp_message_count = fields.Integer(
        string='WhatsApp Messages',
        compute='_compute_whatsapp_message_count',
        help='Number of WhatsApp messages sent for this prescription'
    )

    @api.depends('patient_id', 'patient_id.mobile', 'patient_id.whatsapp_opt_in')
    def _compute_can_send_whatsapp(self):
        """Check if WhatsApp can be sent to this prescription's patient"""
        for prescription in self:
            prescription.can_send_whatsapp = bool(
                prescription.patient_id and
                prescription.patient_id.mobile and
                prescription.patient_id.whatsapp_opt_in
            )

    def _compute_whatsapp_message_count(self):
        """Count WhatsApp messages sent for this prescription"""
        for prescription in self:
            if prescription.patient_id and prescription.patient_id.mobile:
                count = self.env['clinic.whatsapp.message'].search_count([
                    ('patient_id', '=', prescription.patient_id.id),
                    ('phone_number', '=', prescription.patient_id.mobile),
                    ('direction', '=', 'outbound'),
                ])
                prescription.whatsapp_message_count = count
            else:
                prescription.whatsapp_message_count = 0

    def action_send_whatsapp_message(self):
        """
        Open WhatsApp message wizard for prescription reminder/notification

        Fase 4.2: Quick send from prescription record

        Returns:
            dict: Action to open message wizard
        """
        self.ensure_one()

        # Validation: Patient required
        if not self.patient_id:
            raise UserError(_("Cannot send WhatsApp: No patient assigned to this prescription."))

        # Validation: Mobile number required
        if not self.patient_id.mobile:
            raise UserError(
                _("Cannot send WhatsApp to %s: No mobile number on record.")
                % self.patient_id.name
            )

        # Validation: Opt-in required
        if not self.patient_id.whatsapp_opt_in:
            raise UserError(
                _("Cannot send WhatsApp to %s: Patient has not opted in to WhatsApp notifications.\n\n"
                  "Please update patient record to enable WhatsApp opt-in.")
                % self.patient_id.name
            )

        # Prepare context with prescription info
        context = {
            'default_patient_id': self.patient_id.id,
            'default_phone_number': self.patient_id.mobile,
            # Pre-fill message body with prescription details (user can edit)
            'default_message_body': self._get_prescription_message_template(),
            'prescription_id': self.id,
            'prescription_number': self.prescription_number,
        }

        return {
            'name': _('Send WhatsApp - Prescription %s') % self.prescription_number,
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.whatsapp.message.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def _get_prescription_message_template(self):
        """
        Generate prescription notification message template

        Returns:
            str: Pre-filled message body for wizard
        """
        self.ensure_one()

        # Build message
        message_parts = [
            f"Hello {self.patient_id.name},",
            "",
            f"Your prescription {self.prescription_number} is ready.",
            "",
        ]

        # Add medication details (limited for PHI compliance)
        if self.prescription_line_ids:
            message_parts.append("📋 Medications:")
            for line in self.prescription_line_ids[:3]:  # Max 3 for brevity
                med_name = line.medication_id.name if line.medication_id else "Medication"
                message_parts.append(f"  • {med_name}")

            if len(self.prescription_line_ids) > 3:
                message_parts.append(f"  • ... and {len(self.prescription_line_ids) - 3} more")

        message_parts.extend([
            "",
            "⚠️ IMPORTANT:",
            "• Take medications exactly as prescribed",
            "• Check our patient portal for full instructions",
            "• Call us if you have any questions",
            "",
        ])

        if self.doctor_id:
            message_parts.append(f"Prescribed by: Dr. {self.doctor_id.name}")

        message_parts.extend([
            "",
            "Reply PICKUP to confirm pickup time.",
        ])

        return "\n".join(message_parts)

    def action_send_prescription_notification(self):
        """
        Batch action to send WhatsApp notifications to multiple prescriptions

        Fase 4.2: Bulk send from tree view selection

        Returns:
            dict: Notification or wizard action
        """
        # Filter prescriptions that can receive WhatsApp
        valid_prescriptions = self.filtered('can_send_whatsapp')

        if not valid_prescriptions:
            raise UserError(
                _("None of the selected prescriptions can receive WhatsApp messages.\n\n"
                  "Requirements:\n"
                  "- Patient assigned\n"
                  "- Mobile number on record\n"
                  "- WhatsApp opt-in enabled")
            )

        # If only one, open wizard
        if len(valid_prescriptions) == 1:
            return valid_prescriptions.action_send_whatsapp_message()

        # If multiple, send batch notifications
        sent_count = 0
        failed_count = 0

        for prescription in valid_prescriptions:
            try:
                # Get or create thread
                thread = self.env['clinic.whatsapp.thread'].get_or_create_thread(
                    patient_id=prescription.patient_id.id,
                    phone_number=prescription.patient_id.mobile
                )

                # Check if we can send free text or need template
                if thread.can_send_text:
                    # Send free text notification
                    message_body = prescription._get_prescription_message_template()
                    message = self.env['clinic.whatsapp.message'].create({
                        'patient_id': prescription.patient_id.id,
                        'phone_number': prescription.patient_id.mobile,
                        'message_type': 'text',
                        'message_body': message_body,
                        'direction': 'outbound',
                        'state': 'draft',
                    })
                    message.action_send()
                    sent_count += 1

                else:
                    # Outside 24h window - would need template
                    failed_count += 1
                    _logger.warning(
                        f"Cannot send notification for prescription {prescription.prescription_number}: "
                        f"Outside 24h window and no template specified"
                    )

            except Exception as e:
                failed_count += 1
                _logger.error(
                    f"Error sending WhatsApp notification for prescription {prescription.prescription_number}: {str(e)}",
                    exc_info=True
                )

        # Return notification
        if sent_count > 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('WhatsApp Notifications Sent'),
                    'message': _('Successfully sent %d notification(s). %d failed.') % (sent_count, failed_count),
                    'type': 'success' if failed_count == 0 else 'warning',
                    'sticky': False,
                }
            }
        else:
            raise UserError(
                _("Failed to send any notifications.\n\n"
                  "All prescriptions are outside the 24-hour window and require approved templates.")
            )
