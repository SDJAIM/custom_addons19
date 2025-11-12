# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    """
    Extend mail.message to intercept operator replies in WhatsApp Discuss channels

    🎯 PURPOSE: When operator replies in Discuss → send message via WhatsApp Cloud API

    Fase 5.6: Operator Reply from Discuss
    """
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to intercept messages posted in WhatsApp Discuss channels

        Flow:
        1. Create message normally
        2. Check if message is in WhatsApp channel
        3. Check if author is operator (not system/bot)
        4. Send message via WhatsApp API
        5. Update thread metadata
        """
        messages = super(MailMessage, self).create(vals_list)

        # Process each created message
        for message in messages:
            try:
                self._process_whatsapp_operator_reply(message)
            except Exception as e:
                # Log error but don't block message creation
                _logger.error(
                    f"Error processing WhatsApp operator reply for message {message.id}: {e}",
                    exc_info=True
                )

        return messages

    def _process_whatsapp_operator_reply(self, message):
        """
        Process message to determine if it's an operator reply that should be sent via WhatsApp

        Args:
            message: mail.message record

        Returns:
            bool: True if processed as WhatsApp reply
        """
        # Skip if no body
        if not message.body:
            return False

        # Skip system messages (notifications, tracking, etc.)
        if message.message_type in ('notification', 'user_notification', 'auto_comment'):
            return False

        # Skip if no author (system message)
        if not message.author_id:
            return False

        # Check if message is in a WhatsApp channel
        if not message.model or message.model != 'discuss.channel':
            return False

        # Get the channel
        channel = self.env['discuss.channel'].browse(message.res_id)
        if not channel.exists():
            return False

        # Find WhatsApp thread linked to this channel
        thread = self.env['clinic.whatsapp.thread'].search([
            ('discuss_channel_id', '=', channel.id)
        ], limit=1)

        if not thread:
            return False

        # Check if author is operator (has user associated)
        author_user = self.env['res.users'].search([
            ('partner_id', '=', message.author_id.id)
        ], limit=1)

        if not author_user:
            # Not a user, might be the patient posting back (shouldn't happen in WhatsApp channels)
            return False

        # Skip if author is OdooBot or system user
        if author_user.id in (self.env.ref('base.user_root').id, self.env.ref('base.partner_root').id):
            return False

        _logger.info(
            f"Processing WhatsApp operator reply: thread={thread.id}, "
            f"operator={author_user.name}, channel={channel.name}"
        )

        # Send message via WhatsApp
        return self._send_operator_reply_via_whatsapp(thread, message, author_user)

    def _send_operator_reply_via_whatsapp(self, thread, discuss_message, operator):
        """
        Send operator's Discuss message via WhatsApp Cloud API

        Args:
            thread: clinic.whatsapp.thread record
            discuss_message: mail.message record from Discuss
            operator: res.users record

        Returns:
            bool: True if sent successfully
        """
        try:
            # Extract plain text from HTML body
            from lxml import html
            try:
                doc = html.fromstring(discuss_message.body)
                message_text = doc.text_content().strip()
            except:
                # Fallback: strip HTML tags with regex
                import re
                message_text = re.sub('<[^<]+?>', '', discuss_message.body).strip()

            if not message_text:
                _logger.warning(f"Empty message text after HTML extraction for message {discuss_message.id}")
                return False

            # Check if within 24h window
            if not thread.is_within_24h_window:
                # Outside window - cannot send free text
                _logger.warning(
                    f"Cannot send operator reply: thread {thread.id} outside 24h window. "
                    f"Last inbound: {thread.last_inbound_at}"
                )

                # Post warning in Discuss channel
                thread.discuss_channel_id.message_post(
                    body=_(
                        "⚠️ <b>Cannot send message</b><br/>"
                        "This conversation is outside the 24-hour window. "
                        "You must use an approved template to message this customer.<br/>"
                        f"Last customer message: {thread.last_inbound_at}"
                    ),
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment'
                )
                return False

            # Get WhatsApp config
            config = self.env['clinic.whatsapp.config'].search([('active', '=', True)], limit=1)
            if not config:
                _logger.error("No active WhatsApp configuration found")
                return False

            # Create outbound WhatsApp message record
            whatsapp_message = self.env['clinic.whatsapp.message'].create({
                'patient_id': thread.patient_id.id,
                'thread_id': thread.id,
                'direction': 'outbound',
                'message_type': 'text',
                'body': message_text,
                'phone_number': thread.phone_number,
                'phone_number_id': thread.phone_number_id or config.phone_number_id,
                'status': 'queued',
                'sent_by_user_id': operator.id,
            })

            # Send via API
            success = whatsapp_message._send_message()

            if success:
                _logger.info(
                    f"Operator reply sent successfully: thread={thread.id}, "
                    f"message={whatsapp_message.id}, operator={operator.name}"
                )

                # Update thread metadata
                thread.write({
                    'last_operator_reply_at': fields.Datetime.now(),
                    'last_outbound_at': fields.Datetime.now(),
                })

                # Auto-resolve escalation if was escalated
                if thread.escalation_status in ('warning', 'escalated'):
                    old_status = thread.escalation_status
                    thread.write({
                        'escalation_status': 'normal',
                    })
                    _logger.info(
                        f"Auto-resolved escalation: thread={thread.id}, "
                        f"{old_status} → normal"
                    )

                    # Log in chatter
                    thread.message_post(
                        body=_(
                            f"✅ Escalation resolved automatically<br/>"
                            f"Operator <b>{operator.name}</b> replied to customer"
                        ),
                        message_type='notification',
                        subtype_xmlid='mail.mt_note'
                    )

                return True
            else:
                _logger.error(f"Failed to send operator reply: message={whatsapp_message.id}")

                # Post error in Discuss channel
                thread.discuss_channel_id.message_post(
                    body=_(
                        "❌ <b>Failed to send message</b><br/>"
                        "There was an error sending your message via WhatsApp. "
                        "Please check the logs or try again."
                    ),
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment'
                )
                return False

        except Exception as e:
            _logger.error(
                f"Error sending operator reply via WhatsApp: thread={thread.id}, error={e}",
                exc_info=True
            )
            return False
