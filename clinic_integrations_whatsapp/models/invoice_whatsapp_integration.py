# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class InvoiceWhatsAppIntegration(models.Model):
    """
    Extends clinic.invoice with WhatsApp messaging capabilities

    Fase 4.3: Send from Apps - Invoice Integration
    Allows sending WhatsApp payment reminders directly from invoice records
    """
    _inherit = 'clinic.invoice'

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
        help='Number of WhatsApp messages sent for this invoice'
    )

    @api.depends('patient_id', 'patient_id.mobile', 'patient_id.whatsapp_opt_in')
    def _compute_can_send_whatsapp(self):
        """Check if WhatsApp can be sent to this invoice's patient"""
        for invoice in self:
            invoice.can_send_whatsapp = bool(
                invoice.patient_id and
                invoice.patient_id.mobile and
                invoice.patient_id.whatsapp_opt_in
            )

    def _compute_whatsapp_message_count(self):
        """Count WhatsApp messages sent for this invoice"""
        for invoice in self:
            if invoice.patient_id and invoice.patient_id.mobile:
                count = self.env['clinic.whatsapp.message'].search_count([
                    ('patient_id', '=', invoice.patient_id.id),
                    ('phone_number', '=', invoice.patient_id.mobile),
                    ('direction', '=', 'outbound'),
                ])
                invoice.whatsapp_message_count = count
            else:
                invoice.whatsapp_message_count = 0

    def action_send_whatsapp_message(self):
        """
        Open WhatsApp message wizard for payment reminder

        Fase 4.3: Quick send from invoice record

        Returns:
            dict: Action to open message wizard
        """
        self.ensure_one()

        # Validation: Patient required
        if not self.patient_id:
            raise UserError(_("Cannot send WhatsApp: No patient assigned to this invoice."))

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

        # Prepare context with invoice info
        context = {
            'default_patient_id': self.patient_id.id,
            'default_phone_number': self.patient_id.mobile,
            # Pre-fill message body with invoice details (user can edit)
            'default_message_body': self._get_invoice_message_template(),
            'invoice_id': self.id,
            'invoice_name': self.name,
        }

        return {
            'name': _('Send WhatsApp - Invoice %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.whatsapp.message.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def _get_invoice_message_template(self):
        """
        Generate invoice/payment reminder message template

        Returns:
            str: Pre-filled message body for wizard
        """
        self.ensure_one()

        # Build message based on invoice state
        message_parts = [
            f"Hello {self.patient_id.name},",
            "",
        ]

        if self.state == 'draft':
            message_parts.extend([
                f"Your invoice {self.name} has been prepared:",
                f"💰 Amount: {self.amount_total:,.2f} {self.currency_id.name}",
                "",
                "This invoice will be sent for payment soon.",
            ])

        elif self.state == 'posted':
            if self.payment_state in ['paid', 'in_payment']:
                message_parts.extend([
                    f"✅ Payment Received - Invoice {self.name}",
                    f"💰 Amount: {self.amount_total:,.2f} {self.currency_id.name}",
                    "",
                    "Thank you for your payment!",
                    "Receipt will be sent shortly.",
                ])
            elif self.payment_state == 'partial':
                remaining = self.amount_residual
                message_parts.extend([
                    f"⚠️ Partial Payment - Invoice {self.name}",
                    f"💰 Total: {self.amount_total:,.2f} {self.currency_id.name}",
                    f"📊 Remaining: {remaining:,.2f} {self.currency_id.name}",
                    "",
                    "Please complete payment at your earliest convenience.",
                ])
            else:  # not_paid
                message_parts.extend([
                    f"📄 Invoice {self.name} - Payment Due",
                    f"💰 Amount: {self.amount_total:,.2f} {self.currency_id.name}",
                    "",
                ])

                if self.invoice_date_due:
                    due_str = self.invoice_date_due.strftime('%B %d, %Y')
                    message_parts.append(f"📅 Due Date: {due_str}")

                message_parts.extend([
                    "",
                    "💳 Payment Methods:",
                    "• Cash at reception",
                    "• Credit/Debit card",
                    "• Online payment portal",
                ])

        message_parts.extend([
            "",
            "View invoice details on our patient portal.",
            "",
            "Reply PAY to receive payment link.",
        ])

        return "\n".join(message_parts)

    def action_send_payment_reminder(self):
        """
        Batch action to send WhatsApp payment reminders to multiple invoices

        Fase 4.3: Bulk send from tree view selection

        Returns:
            dict: Notification or wizard action
        """
        # Filter invoices that can receive WhatsApp and are unpaid/partial
        valid_invoices = self.filtered(
            lambda inv: inv.can_send_whatsapp and inv.payment_state in ['not_paid', 'partial']
        )

        if not valid_invoices:
            raise UserError(
                _("None of the selected invoices can receive WhatsApp reminders.\n\n"
                  "Requirements:\n"
                  "- Patient assigned\n"
                  "- Mobile number on record\n"
                  "- WhatsApp opt-in enabled\n"
                  "- Invoice not fully paid")
            )

        # If only one, open wizard
        if len(valid_invoices) == 1:
            return valid_invoices.action_send_whatsapp_message()

        # If multiple, send batch reminders
        sent_count = 0
        failed_count = 0

        for invoice in valid_invoices:
            try:
                # Get or create thread
                thread = self.env['clinic.whatsapp.thread'].get_or_create_thread(
                    patient_id=invoice.patient_id.id,
                    phone_number=invoice.patient_id.mobile
                )

                # Check if we can send free text or need template
                if thread.can_send_text:
                    # Send free text reminder
                    message_body = invoice._get_invoice_message_template()
                    message = self.env['clinic.whatsapp.message'].create({
                        'patient_id': invoice.patient_id.id,
                        'phone_number': invoice.patient_id.mobile,
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
                        f"Cannot send reminder for invoice {invoice.name}: "
                        f"Outside 24h window and no template specified"
                    )

            except Exception as e:
                failed_count += 1
                _logger.error(
                    f"Error sending WhatsApp reminder for invoice {invoice.name}: {str(e)}",
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
                  "All invoices are outside the 24-hour window and require approved templates.")
            )
