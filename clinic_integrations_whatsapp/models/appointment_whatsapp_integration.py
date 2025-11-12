# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AppointmentWhatsAppIntegration(models.Model):
    """
    Extends clinic.appointment with WhatsApp messaging capabilities

    Fase 4.1: Send from Apps - Appointment Integration
    Allows sending WhatsApp messages directly from appointment records
    """
    _inherit = 'clinic.appointment'

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
        help='Number of WhatsApp messages sent for this appointment'
    )

    @api.depends('patient_id', 'patient_id.mobile', 'patient_id.whatsapp_opt_in')
    def _compute_can_send_whatsapp(self):
        """Check if WhatsApp can be sent to this appointment's patient"""
        for appointment in self:
            appointment.can_send_whatsapp = bool(
                appointment.patient_id and
                appointment.patient_id.mobile and
                appointment.patient_id.whatsapp_opt_in
            )

    def _compute_whatsapp_message_count(self):
        """Count WhatsApp messages sent for this appointment"""
        for appointment in self:
            if appointment.patient_id and appointment.patient_id.mobile:
                # Count messages sent to this patient about this appointment
                # (we can filter by message_body containing appointment_number if needed)
                count = self.env['clinic.whatsapp.message'].search_count([
                    ('patient_id', '=', appointment.patient_id.id),
                    ('phone_number', '=', appointment.patient_id.mobile),
                    ('direction', '=', 'outbound'),
                ])
                appointment.whatsapp_message_count = count
            else:
                appointment.whatsapp_message_count = 0

    def action_send_whatsapp_message(self):
        """
        Open WhatsApp message wizard for appointment reminder/notification

        Fase 4.1: Quick send from appointment record

        Returns:
            dict: Action to open message wizard
        """
        self.ensure_one()

        # Validation: Patient required
        if not self.patient_id:
            raise UserError(_("Cannot send WhatsApp: No patient assigned to this appointment."))

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

        # Prepare context with appointment info
        context = {
            'default_patient_id': self.patient_id.id,
            'default_phone_number': self.patient_id.mobile,
            # Pre-fill message body with appointment details (user can edit)
            'default_message_body': self._get_appointment_message_template(),
            'appointment_id': self.id,
            'appointment_number': self.appointment_number,
        }

        return {
            'name': _('Send WhatsApp - Appointment %s') % self.appointment_number,
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.whatsapp.message.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def _get_appointment_message_template(self):
        """
        Generate appointment reminder message template

        Returns:
            str: Pre-filled message body for wizard
        """
        self.ensure_one()

        # Format datetime for patient's timezone
        start_dt = self.start
        if start_dt:
            # Convert to patient's timezone if available, else use UTC
            tz = self.env.user.tz or 'UTC'
            start_local = fields.Datetime.context_timestamp(self, start_dt)
            date_str = start_local.strftime('%A, %B %d at %I:%M %p')
        else:
            date_str = 'TBD'

        # Build message
        message_parts = [
            f"Hello {self.patient_id.name},",
            "",
            f"This is a reminder about your upcoming appointment:",
            f"📅 {date_str}",
        ]

        if self.appointment_type_id:
            message_parts.append(f"🏥 Type: {self.appointment_type_id.name}")

        if self.staff_id:
            message_parts.append(f"👨‍⚕️ With: Dr. {self.staff_id.name}")

        message_parts.extend([
            "",
            "Please arrive 10 minutes early.",
            "",
            "Reply CONFIRM to confirm or CANCEL to reschedule.",
        ])

        return "\n".join(message_parts)

    def action_send_appointment_reminder(self):
        """
        Batch action to send WhatsApp reminders to multiple appointments

        Fase 4.1: Bulk send from tree view selection

        Returns:
            dict: Notification or wizard action
        """
        # Filter appointments that can receive WhatsApp
        valid_appointments = self.filtered('can_send_whatsapp')

        if not valid_appointments:
            raise UserError(
                _("None of the selected appointments can receive WhatsApp messages.\n\n"
                  "Requirements:\n"
                  "- Patient assigned\n"
                  "- Mobile number on record\n"
                  "- WhatsApp opt-in enabled")
            )

        # If only one, open wizard
        if len(valid_appointments) == 1:
            return valid_appointments.action_send_whatsapp_message()

        # If multiple, send batch reminders using templates
        sent_count = 0
        failed_count = 0

        for appointment in valid_appointments:
            try:
                # Get or create thread
                thread = self.env['clinic.whatsapp.thread'].get_or_create_thread(
                    patient_id=appointment.patient_id.id,
                    phone_number=appointment.patient_id.mobile
                )

                # Check if we can send free text or need template
                if thread.can_send_text:
                    # Send free text reminder
                    message_body = appointment._get_appointment_message_template()
                    message = self.env['clinic.whatsapp.message'].create({
                        'patient_id': appointment.patient_id.id,
                        'phone_number': appointment.patient_id.mobile,
                        'message_type': 'text',
                        'message_body': message_body,
                        'direction': 'outbound',
                        'state': 'draft',
                    })
                    message.action_send()
                    sent_count += 1

                else:
                    # Outside 24h window - would need template
                    # For now, skip and count as failed
                    failed_count += 1
                    _logger.warning(
                        f"Cannot send reminder for appointment {appointment.appointment_number}: "
                        f"Outside 24h window and no template specified"
                    )

            except Exception as e:
                failed_count += 1
                _logger.error(
                    f"Error sending WhatsApp reminder for appointment {appointment.appointment_number}: {str(e)}",
                    exc_info=True
                )

        # Return notification
        if sent_count > 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('WhatsApp Reminders Sent'),
                    'message': _('Successfully sent %d reminder(s). %d failed.') % (sent_count, failed_count),
                    'type': 'success' if failed_count == 0 else 'warning',
                    'sticky': False,
                }
            }
        else:
            raise UserError(
                _("Failed to send any reminders.\n\n"
                  "All appointments are outside the 24-hour window and require approved templates.")
            )
