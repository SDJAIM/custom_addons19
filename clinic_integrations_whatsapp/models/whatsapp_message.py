# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import requests
import json
import base64
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class WhatsAppMessage(models.Model):
    _name = 'clinic.whatsapp.message'
    _description = 'WhatsApp Message'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'display_name'
    
    # Basic Information
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    message_id = fields.Char(
        string='Message ID',
        readonly=True,
        copy=False,
        help='WhatsApp message ID'
    )
    
    # Contact Information
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        tracking=True,
        index=True
    )
    
    phone_number = fields.Char(
        string='Phone Number',
        required=True,
        tracking=True
    )
    
    whatsapp_number = fields.Char(
        string='WhatsApp Number',
        compute='_compute_whatsapp_number',
        store=True
    )
    
    # Message Content
    message_type = fields.Selection([
        ('text', 'Text'),
        ('template', 'Template'),
        ('image', 'Image'),
        ('document', 'Document'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('location', 'Location'),
    ], string='Type', default='text', required=True)
    
    template_id = fields.Many2one(
        'clinic.whatsapp.template',
        string='Template'
    )

    # Fase 2.4: Template preview fields
    template_header = fields.Text(
        string='Template Header',
        related='template_id.header',
        readonly=True
    )

    template_footer = fields.Text(
        string='Template Footer',
        related='template_id.footer',
        readonly=True
    )

    template_meta_status = fields.Selection(
        string='Template Status',
        related='template_id.meta_status',
        readonly=True
    )

    message_body = fields.Text(
        string='Message',
        required=True
    )
    
    media_url = fields.Char(
        string='Media URL'
    )
    
    media_attachment = fields.Binary(
        string='Media Attachment',
        attachment=True
    )
    
    # Direction
    direction = fields.Selection([
        ('outbound', 'Outbound'),
        ('inbound', 'Inbound'),
    ], string='Direction', default='outbound', required=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('queued', 'Queued'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)
    
    # Timestamps
    scheduled_date = fields.Datetime(
        string='Scheduled Date',
        tracking=True
    )
    
    sent_date = fields.Datetime(
        string='Sent Date',
        readonly=True
    )
    
    delivered_date = fields.Datetime(
        string='Delivered Date',
        readonly=True
    )
    
    read_date = fields.Datetime(
        string='Read Date',
        readonly=True
    )
    
    # Error Handling
    error_message = fields.Text(
        string='Error Message',
        readonly=True
    )
    
    retry_count = fields.Integer(
        string='Retry Count',
        default=0,
        readonly=True
    )
    
    max_retries = fields.Integer(
        string='Max Retries',
        default=3
    )
    
    # Related Records
    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Related Appointment'
    )
    
    prescription_id = fields.Many2one(
        'clinic.prescription',
        string='Related Prescription'
    )
    
    treatment_id = fields.Many2one(
        'clinic.treatment.plan.line',
        string='Related Treatment'
    )
    
    # Message Category
    category = fields.Selection([
        ('appointment_reminder', 'Appointment Reminder'),
        ('appointment_confirmation', 'Appointment Confirmation'),
        ('appointment_cancellation', 'Appointment Cancellation'),
        ('prescription_reminder', 'Prescription Reminder'),
        ('lab_result', 'Lab Result'),
        ('follow_up', 'Follow-up'),
        ('marketing', 'Marketing'),
        ('general', 'General'),
        ('emergency', 'Emergency'),
    ], string='Category', default='general', tracking=True)
    
    # Priority
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='normal')
    
    # Campaign (model not implemented yet)
    # campaign_id = fields.Many2one(
    #     'clinic.whatsapp.campaign',
    #     string='Campaign'
    # )
    
    # Reply Handling
    is_reply_expected = fields.Boolean(
        string='Reply Expected',
        default=False
    )
    
    reply_to_id = fields.Many2one(
        'clinic.whatsapp.message',
        string='Reply To'
    )
    
    replies = fields.One2many(
        'clinic.whatsapp.message',
        'reply_to_id',
        string='Replies'
    )
    
    # Webhook Data
    webhook_data = fields.Text(
        string='Webhook Data',
        readonly=True
    )
    
    @api.depends('patient_id', 'category', 'create_date')
    def _compute_display_name(self):
        for msg in self:
            parts = []
            if msg.patient_id:
                parts.append(msg.patient_id.name)
            if msg.category:
                parts.append(dict(self._fields['category'].selection).get(msg.category))
            if msg.create_date:
                parts.append(msg.create_date.strftime('%Y-%m-%d %H:%M'))
            msg.display_name = ' - '.join(parts) if parts else 'New Message'
    
    @api.depends('phone_number')
    def _compute_whatsapp_number(self):
        for msg in self:
            if msg.phone_number:
                # Format phone number for WhatsApp (remove special characters, add country code)
                phone = ''.join(filter(str.isdigit, msg.phone_number))
                if not phone.startswith('+'):
                    # Get default country code from configuration
                    config_helper = self.env['clinic.whatsapp.config.helper']
                    default_country_code = config_helper.get_config_value('default_country_code', '+1')
                    phone = default_country_code + phone
                msg.whatsapp_number = phone
            else:
                msg.whatsapp_number = False
    
    def action_send(self):
        """Send WhatsApp message with rate limiting and 24h window validation"""
        self.ensure_one()

        if self.state not in ['draft', 'failed']:
            raise UserError(_("Message cannot be sent in current state."))

        # Check patient opt-in (if required by configuration)
        config_helper = self.env['clinic.whatsapp.config.helper']
        require_opt_in = config_helper.get_config_value('require_opt_in', 'True') == 'True'

        if require_opt_in and not self.patient_id.whatsapp_opt_in:
            raise UserError(_("Patient has not opted in for WhatsApp messages."))

        # 🔒 CRITICAL: Check 24h window for text messages
        if self.message_type == 'text' and self.patient_id:
            Thread = self.env['clinic.whatsapp.thread'].sudo()
            thread = Thread.search([
                ('patient_id', '=', self.patient_id.id),
                ('phone_number', '=', self.phone_number),
            ], limit=1)

            if thread:
                window_status = thread.can_send_free_text()
                if not window_status['allowed']:
                    raise UserError(
                        _("Cannot send free text message: %s\n\n"
                          "Please use an approved template instead, or wait for customer to reply.")
                        % window_status['reason']
                    )

        # Check rate limits
        RateLimit = self.env['clinic.whatsapp.rate_limit']
        rate_check = RateLimit.check_rate_limit(
            patient_id=self.patient_id.id if self.patient_id else None,
            phone_number=self.phone_number,
            raise_error=True  # Will raise ValidationError if limit exceeded
        )

        if not rate_check['allowed']:
            # This should not happen since raise_error=True, but handle it anyway
            raise ValidationError(
                _("Rate limit exceeded. Please wait %d seconds before sending.") % rate_check['wait_time']
            )

        # Queue message
        self.state = 'queued'

        # Send immediately or schedule
        if not self.scheduled_date or self.scheduled_date <= fields.Datetime.now():
            self._send_message()

        return True
    
    def _send_message(self):
        """Actually send the message via WhatsApp API"""
        self.ensure_one()

        # Get secure configuration from ir.config_parameter
        try:
            config_helper = self.env['clinic.whatsapp.config.helper']
            config = config_helper.get_api_config()
        except Exception as e:
            self.write({
                'state': 'failed',
                'error_message': f'Configuration error: {str(e)}'
            })
            return False

        # Get credentials (new Cloud API first, then legacy fallback)
        access_token = config.get('access_token') or config.get('api_token')
        phone_number_id = config.get('phone_number_id') or config.get('phone_number')

        if not access_token:
            self.write({
                'state': 'failed',
                'error_message': 'WhatsApp Access Token not configured. Please configure in Settings > WhatsApp Configuration.'
            })
            return False

        if not phone_number_id:
            self.write({
                'state': 'failed',
                'error_message': 'WhatsApp Phone Number ID not configured. Please configure in Settings > WhatsApp Configuration.'
            })
            return False

        try:
            self.state = 'sending'

            # Prepare API request
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            # Build message payload based on type
            if self.message_type == 'template':
                payload = self._build_template_payload(config)
            else:
                payload = self._build_text_payload(config)

            # Send API request
            api_url = config.get('api_url', 'https://graph.facebook.com/v18.0')
            response = requests.post(
                f"{api_url}/{phone_number_id}/messages",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.write({
                    'state': 'sent',
                    'sent_date': fields.Datetime.now(),
                    'message_id': result.get('messages', [{}])[0].get('id'),
                    'error_message': False,
                })

                # Increment rate limit counter
                RateLimit = self.env['clinic.whatsapp.rate_limit']
                RateLimit.increment_counter(
                    patient_id=self.patient_id.id if self.patient_id else None,
                    phone_number=self.phone_number
                )

                # Log to patient timeline
                self._log_to_patient_timeline()

                # Update conversation thread (outbound message does NOT reset 24h window)
                if self.patient_id:
                    self._update_conversation_thread(
                        self.patient_id,
                        inbound=False,
                        message_body=self.message_body,
                        phone_number=self.phone_number
                    )

                return True
            else:
                raise Exception(f"API Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            _logger.error(f"WhatsApp send error: {str(e)}")
            
            # Handle retry
            config_helper = self.env['clinic.whatsapp.config.helper']
            max_retries = int(config_helper.get_config_value('max_retries', '3'))
            retry_delay = int(config_helper.get_config_value('retry_delay', '5'))

            if self.retry_count < max_retries:
                self.retry_count += 1
                self.state = 'queued'

                # Schedule retry
                self.env['clinic.whatsapp.message'].with_delay(
                    eta=datetime.now() + timedelta(minutes=retry_delay * self.retry_count)
                ).browse(self.id)._send_message()
            else:
                self.write({
                    'state': 'failed',
                    'error_message': str(e)
                })
            
            return False
    
    def _build_text_payload(self, config=None):
        """Build payload for text message"""
        return {
            'messaging_product': 'whatsapp',
            'to': self.whatsapp_number,
            'type': 'text',
            'text': {
                'body': self.message_body
            }
        }
    
    def _build_template_payload(self, config=None):
        """Build payload for template message"""
        if not self.template_id:
            raise ValidationError(_("Template is required for template messages."))

        # Parse template parameters
        params = self._get_template_parameters()

        return {
            'messaging_product': 'whatsapp',
            'to': self.whatsapp_number,
            'type': 'template',
            'template': {
                'name': self.template_id.template_name,
                'language': {
                    'code': self.template_id.language_code or 'en'
                },
                'components': [{
                    'type': 'body',
                    'parameters': params
                }]
            }
        }
    
    def _get_template_parameters(self):
        """Get template parameters based on context"""
        params = []
        
        if self.appointment_id:
            params.extend([
                {'type': 'text', 'text': self.patient_id.name},
                {'type': 'text', 'text': self.appointment_id.appointment_date.strftime('%B %d, %Y')},
                {'type': 'text', 'text': self.appointment_id.appointment_date.strftime('%I:%M %p')},
                {'type': 'text', 'text': self.appointment_id.doctor_id.name if self.appointment_id.doctor_id else ''},
            ])
        elif self.prescription_id:
            params.extend([
                {'type': 'text', 'text': self.patient_id.name},
                {'type': 'text', 'text': self.prescription_id.prescription_number},
            ])
        
        return params
    
    def _log_to_patient_timeline(self):
        """Log message to patient timeline"""
        self.ensure_one()
        
        body = f"""
        <div class="o_mail_notification">
            <strong>WhatsApp Message Sent</strong><br/>
            Category: {dict(self._fields['category'].selection).get(self.category)}<br/>
            Message: {self.message_body[:100]}...
        </div>
        """
        
        self.patient_id.message_post(
            body=body,
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )
    
    def action_cancel(self):
        """Cancel queued message"""
        self.ensure_one()
        
        if self.state not in ['draft', 'queued']:
            raise UserError(_("Only draft or queued messages can be cancelled."))
        
        self.state = 'cancelled'
        
        return True
    
    def action_retry(self):
        """Retry failed message"""
        self.ensure_one()
        
        if self.state != 'failed':
            raise UserError(_("Only failed messages can be retried."))
        
        self.retry_count = 0
        self.action_send()
        
        return True
    
    @api.model
    def process_webhook(self, data):
        """Process incoming webhook from WhatsApp"""
        try:
            # Parse webhook data
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    
                    # Handle status updates
                    if 'statuses' in value:
                        for status in value['statuses']:
                            self._process_status_update(status)
                    
                    # Handle incoming messages
                    if 'messages' in value:
                        for message in value['messages']:
                            self._process_incoming_message(message, value.get('contacts', []))
            
            return True
            
        except Exception as e:
            _logger.error(f"Webhook processing error: {str(e)}")
            return False
    
    def _process_status_update(self, status):
        """Process message status update"""
        message_id = status.get('id')
        status_type = status.get('status')
        
        message = self.search([('message_id', '=', message_id)], limit=1)
        if message:
            if status_type == 'delivered':
                message.write({
                    'state': 'delivered',
                    'delivered_date': fields.Datetime.now()
                })
            elif status_type == 'read':
                message.write({
                    'state': 'read',
                    'read_date': fields.Datetime.now()
                })
            elif status_type == 'failed':
                message.write({
                    'state': 'failed',
                    'error_message': status.get('errors', [{}])[0].get('title', 'Unknown error')
                })
    
    def _process_incoming_message(self, message, contacts):
        """Process incoming message from patient"""
        from_number = message.get('from')
        message_body = message.get('text', {}).get('body', '')
        message_type = message.get('type', 'text')
        
        # Find patient
        patient = self.env['clinic.patient'].search([
            ('whatsapp_number', '=', from_number)
        ], limit=1)
        
        if not patient and contacts:
            # Try to find by phone number
            contact = contacts[0]
            phone = contact.get('wa_id')
            patient = self.env['clinic.patient'].search([
                '|',
                ('phone', 'like', phone),
                ('mobile', 'like', phone)
            ], limit=1)
        
        if patient:
            # Create inbound message record
            self.create({
                'patient_id': patient.id,
                'phone_number': from_number,
                'direction': 'inbound',
                'message_type': message_type,
                'message_body': message_body,
                'state': 'delivered',
                'delivered_date': fields.Datetime.now(),
                'webhook_data': json.dumps(message),
            })
            
            # Check for automated responses
            self._check_automated_response(patient, message_body)
    
    def _check_automated_response(self, thread, message_body):
        """
        Check if automated response is needed (Enhanced v2)

        Fase 5.3: Uses new whatsapp_autoresponder model

        Args:
            thread (recordset): WhatsApp thread
            message_body (str): Incoming message text
        """
        if not thread or not message_body:
            return

        # Use new auto-responder system
        AutoResponder = self.env['clinic.whatsapp.autoresponder'].sudo()
        response_sent = AutoResponder.process_incoming_message(thread, message_body)

        if response_sent:
            _logger.info(f"✅ Auto-response sent for thread {thread.id}")

        # Legacy: Keep appointment confirmation logic as fallback
        self._check_appointment_confirmation_legacy(thread.patient_id, message_body)

    def _check_appointment_confirmation_legacy(self, patient, message_body):
        """
        Legacy appointment confirmation logic (kept for backward compatibility)

        Args:
            patient (recordset): Patient record
            message_body (str): Incoming message text
        """
        if not patient or not message_body:
            return

        message_lower = message_body.lower()

        # Check for appointment confirmation
        if 'confirm' in message_lower or 'confirmar' in message_lower:
            # Find pending appointments
            appointments = self.env['clinic.appointment'].search([
                ('patient_id', '=', patient.id),
                ('state', '=', 'confirmed'),
                ('appointment_date', '>', fields.Datetime.now()),
            ], order='appointment_date', limit=1)

            if appointments:
                # Send confirmation response
                self.create({
                    'patient_id': patient.id,
                    'phone_number': patient.whatsapp_number or patient.mobile,
                    'message_type': 'text',
                    'message_body': f"Thank you for confirming your appointment on {appointments[0].appointment_date.strftime('%B %d at %I:%M %p')}. See you then!",
                    'category': 'appointment_confirmation',
                    'state': 'queued',
                }).action_send()
    
    @api.model
    def send_appointment_reminders(self):
        """Cron job to send appointment reminders"""
        # Check if reminders are enabled
        config_helper = self.env['clinic.whatsapp.config.helper']
        feature_config = config_helper.get_feature_config()

        if not feature_config.get('enable_reminders', True):
            _logger.info("Appointment reminders are disabled in configuration")
            return

        # Check if WhatsApp is configured
        if not config_helper.is_configured():
            _logger.warning("WhatsApp is not properly configured, skipping reminder job")
            return

        # Find appointments for tomorrow
        tomorrow = fields.Date.today() + timedelta(days=1)
        appointments = self.env['clinic.appointment'].search([
            ('appointment_date', '>=', tomorrow.strftime('%Y-%m-%d 00:00:00')),
            ('appointment_date', '<=', tomorrow.strftime('%Y-%m-%d 23:59:59')),
            ('state', '=', 'confirmed'),
            ('reminder_sent', '=', False),
        ])

        template = self.env['clinic.whatsapp.template'].search([
            ('template_type', '=', 'appointment_reminder'),
            ('active', '=', True)
        ], limit=1)

        sent_count = 0
        for appointment in appointments:
            # Check opt-in if required
            require_opt_in = feature_config.get('require_opt_in', True)
            if require_opt_in and not appointment.patient_id.whatsapp_opt_in:
                continue

            try:
                self.create({
                    'patient_id': appointment.patient_id.id,
                    'phone_number': appointment.patient_id.whatsapp_number,
                    'appointment_id': appointment.id,
                    'template_id': template.id if template else False,
                    'message_type': 'template' if template else 'text',
                    'message_body': self._prepare_reminder_message(appointment),
                    'category': 'appointment_reminder',
                    'priority': 'high',
                    'state': 'queued',
                }).action_send()

                appointment.reminder_sent = True
                sent_count += 1

            except Exception as e:
                _logger.error(f"Failed to send reminder for appointment {appointment.id}: {str(e)}")

        _logger.info(f"Sent {sent_count} appointment reminders")
    
    def _prepare_reminder_message(self, appointment):
        """Prepare appointment reminder message"""
        return _("""
Hello %s,

This is a reminder for your appointment:
📅 Date: %s
⏰ Time: %s
👨‍⚕️ Doctor: %s
📍 Location: %s

Please reply 'CONFIRM' to confirm your attendance or call us to reschedule.

Thank you!
        """) % (
            appointment.patient_id.name,
            appointment.appointment_date.strftime('%B %d, %Y'),
            appointment.appointment_date.strftime('%I:%M %p'),
            appointment.doctor_id.name if appointment.doctor_id else 'TBD',
            appointment.branch_id.name if appointment.branch_id else 'Main Clinic'
        )

    @api.model
    def send_pending_messages(self, limit=100):
        """Send pending/queued WhatsApp messages

        Called by scheduled action to process queued messages.
        """
        _logger.info("Starting send_pending_messages cron job...")

        # Check if WhatsApp is properly configured
        config_helper = self.env['clinic.whatsapp.config.helper']
        if not config_helper.is_configured():
            _logger.warning('WhatsApp not configured; skipping send_pending_messages')
            return

        # Search for queued messages that are ready to send
        domain = [('state', '=', 'queued')]

        # Only send messages that are scheduled for now or in the past
        domain.append('|')
        domain.append(('scheduled_date', '=', False))
        domain.append(('scheduled_date', '<=', fields.Datetime.now()))

        msgs = self.sudo().search(domain, limit=limit, order='priority desc, create_date asc')

        _logger.info("Found %d queued messages to send", len(msgs))

        sent_count = 0
        failed_count = 0

        for msg in msgs:
            try:
                if hasattr(msg, '_send_message') and callable(msg._send_message):
                    msg._send_message()
                    sent_count += 1
                else:
                    _logger.warning("Missing _send_message() method on clinic.whatsapp.message id=%s", msg.id)
                    msg.write({'state': 'failed', 'error_message': 'Internal error: _send_message method not found'})
                    failed_count += 1
            except Exception as e:
                _logger.exception("Failed to send WhatsApp message id=%s: %s", msg.id, e)
                failed_count += 1

        _logger.info("Completed send_pending_messages: sent=%d, failed=%d", sent_count, failed_count)

    @api.model
    def retry_failed_messages(self, limit=100):
        """Retry failed WhatsApp messages

        Called by scheduled action to retry failed messages that haven't exceeded max retries.
        """
        _logger.info("Starting retry_failed_messages cron job...")

        # Check if WhatsApp is properly configured
        config_helper = self.env['clinic.whatsapp.config.helper']
        if not config_helper.is_configured():
            _logger.warning('WhatsApp not configured; skipping retry_failed_messages')
            return

        # Search for failed messages that haven't exceeded max retries
        domain = [
            ('state', '=', 'failed'),
            ('retry_count', '<', 3),  # Default max retries
        ]

        # Check if 'next_try' field exists
        if 'next_try' in self._fields:
            now = fields.Datetime.now()
            domain.append('|')
            domain.append(('next_try', '=', False))
            domain.append(('next_try', '<=', now))
            order = 'next_try asc, write_date asc'
        else:
            order = 'write_date asc'

        msgs = self.sudo().search(domain, limit=limit, order=order)

        _logger.info("Found %d failed messages to retry", len(msgs))

        retried_count = 0
        skipped_count = 0

        for msg in msgs:
            try:
                # Check if max retries exceeded
                if msg.retry_count >= msg.max_retries:
                    _logger.debug("Message id=%s exceeded max retries (%d), skipping", msg.id, msg.max_retries)
                    skipped_count += 1
                    continue

                if hasattr(msg, '_send_message') and callable(msg._send_message):
                    _logger.info("Retrying WhatsApp message id=%s (attempt %d/%d)", msg.id, msg.retry_count + 1, msg.max_retries)
                    msg._send_message()
                    retried_count += 1
                else:
                    _logger.warning("Missing _send_message() method on retry for id=%s", msg.id)
                    skipped_count += 1
            except Exception as e:
                _logger.exception("Retry failed for WhatsApp message id=%s: %s", msg.id, e)
                skipped_count += 1

        _logger.info("Completed retry_failed_messages: retried=%d, skipped=%d", retried_count, skipped_count)

    @api.model
    def clean_old_messages(self, days=90):
        """
        Clean up old WhatsApp messages beyond retention period

        Called by scheduled action to remove old messages and free up database space.
        Only deletes successfully delivered messages; keeps failed/pending for debugging.

        Args:
            days (int): Number of days to retain messages (default: 90)

        Returns:
            int: Number of messages deleted
        """
        _logger.info("Starting clean_old_messages cron job (retention: %d days)...", days)

        cutoff_date = fields.Datetime.now() - timedelta(days=days)

        # Find old messages that can be safely deleted
        # Keep failed/pending messages regardless of age for debugging
        domain = [
            ('create_date', '<', cutoff_date),
            ('state', 'in', ['sent', 'delivered', 'read', 'cancelled']),
        ]

        old_messages = self.sudo().search(domain)
        count = len(old_messages)

        if count > 0:
            _logger.info(f"🗑️ Cleaning up {count} WhatsApp messages older than {days} days")

            try:
                old_messages.unlink()
                _logger.info(f"✅ Successfully deleted {count} old messages")
            except Exception as e:
                _logger.error(f"❌ Error deleting old messages: {e}")
                return 0
        else:
            _logger.info("No old messages to clean up")

        return count

    def name_get(self):
        return [(msg.id, msg.display_name) for msg in self]

    @api.model
    def handle_incoming_webhook(self, message_data, metadata):
        """
        Handle incoming message webhook with idempotency

        🔄 IDEMPOTENT: Checks webhook_event table before processing
        Called by webhook controller after signature validation

        Args:
            message_data (dict): Message data from Meta webhook
            metadata (dict): Metadata (phone_number_id, display_phone_number, etc.)

        Returns:
            recordset: Created message record or empty recordset if duplicate
        """
        message_id = message_data.get('id')
        from_number = message_data.get('from')
        timestamp = message_data.get('timestamp')
        message_type = message_data.get('type', 'text')

        _logger.info(f"📥 Processing incoming message: {message_id} from {from_number}")

        # 🔄 IDEMPOTENCY CHECK
        WebhookEvent = self.env['clinic.whatsapp.webhook.event'].sudo()

        if WebhookEvent.is_duplicate(message_id):
            WebhookEvent.mark_duplicate(message_id, 'message')
            _logger.info(f"🔄 Duplicate message {message_id} - skipping")
            return self.env['clinic.whatsapp.message']

        # Process message (not a duplicate)
        try:
            # Extract message content based on type
            message_body = ''
            media_url = None

            if message_type == 'text':
                message_body = message_data.get('text', {}).get('body', '')
            elif message_type == 'image':
                message_body = message_data.get('image', {}).get('caption', '(Image)')
                media_url = message_data.get('image', {}).get('id')  # Media ID, needs download
            elif message_type == 'document':
                message_body = message_data.get('document', {}).get('caption', '(Document)')
                media_url = message_data.get('document', {}).get('id')
            elif message_type == 'audio':
                message_body = '(Voice message)'
                media_url = message_data.get('audio', {}).get('id')
            elif message_type == 'video':
                message_body = message_data.get('video', {}).get('caption', '(Video)')
                media_url = message_data.get('video', {}).get('id')
            elif message_type == 'location':
                location = message_data.get('location', {})
                message_body = f"Location: {location.get('latitude')}, {location.get('longitude')}"
            else:
                message_body = f"(Unsupported message type: {message_type})"

            # Find patient by WhatsApp number
            patient = self.env['clinic.patient'].sudo().search([
                '|',
                ('whatsapp_number', '=', from_number),
                '|',
                ('phone', 'like', from_number[-10:]),  # Last 10 digits
                ('mobile', 'like', from_number[-10:]),
            ], limit=1)

            if not patient:
                _logger.warning(
                    f"⚠️ No patient found for WhatsApp number {from_number}. "
                    f"Message will be logged but not linked to patient."
                )
                # Option 1: Skip creating message
                WebhookEvent.mark_error(
                    message_id,
                    'message',
                    message_data,
                    f"No patient found for number {from_number}"
                )
                return self.env['clinic.whatsapp.message']

                # Option 2: Create orphan message (uncomment if preferred)
                # patient = self.env.ref('base.main_partner')  # Link to generic partner

            # Create inbound message record
            new_message = self.sudo().create({
                'message_id': message_id,
                'patient_id': patient.id,
                'phone_number': from_number,
                'direction': 'inbound',
                'message_type': message_type,
                'message_body': message_body,
                'media_url': media_url,
                'state': 'delivered',
                'delivered_date': fields.Datetime.now(),
                'webhook_data': json.dumps(message_data),
            })

            # Fase 5.4: Download media if present
            if media_url and message_type in ('image', 'document', 'audio', 'video'):
                self._download_whatsapp_media(new_message, message_data)

            # Mark webhook as processed
            WebhookEvent.mark_processed(
                message_id,
                'message',
                message_data,
                message_id=new_message.id,
                from_number=from_number
            )

            # Update conversation thread (for 24h window tracking)
            thread = None
            if patient:
                thread = self._update_conversation_thread(
                    patient,
                    inbound=True,
                    message_body=message_body,
                    phone_number=from_number
                )

            # Fase 5.2: Route to Discuss channel
            if thread:
                self._route_to_discuss_channel(thread, new_message)

            # Check for automated responses (Fase 5.3)
            if thread and message_type == 'text':
                self._check_automated_response(thread, message_body)

            # Post to patient chatter
            if patient:
                patient.message_post(
                    body=f"📱 <strong>WhatsApp Received:</strong><br/>{message_body}",
                    message_type='comment',
                    subtype_xmlid='mail.mt_note'
                )

            _logger.info(f"✅ Message {message_id} processed successfully")
            return new_message

        except Exception as e:
            _logger.error(f"❌ Error processing incoming message {message_id}: {e}", exc_info=True)

            # Mark as error in webhook log
            WebhookEvent.mark_error(message_id, 'message', message_data, str(e))

            return self.env['clinic.whatsapp.message']

    @api.model
    def handle_status_webhook(self, status_data):
        """
        Handle status update webhook with idempotency

        🔄 IDEMPOTENT: Checks webhook_event table before processing
        Called by webhook controller after signature validation

        Status progression: sent → delivered → read (or failed)

        Args:
            status_data (dict): Status data from Meta webhook

        Returns:
            bool: True if processed successfully
        """
        status_id = status_data.get('id')  # This is the message_id
        status = status_data.get('status')
        timestamp = status_data.get('timestamp')
        recipient = status_data.get('recipient_id')

        _logger.info(f"📊 Processing status update: {status_id} → {status}")

        # 🔄 IDEMPOTENCY CHECK
        # For status updates, we use a composite key: message_id + status
        # Because same message can have multiple statuses (sent → delivered → read)
        event_id = f"{status_id}:{status}"

        WebhookEvent = self.env['clinic.whatsapp.webhook.event'].sudo()

        if WebhookEvent.is_duplicate(event_id):
            WebhookEvent.mark_duplicate(event_id, 'status')
            _logger.info(f"🔄 Duplicate status update {event_id} - skipping")
            return True

        # Process status update (not a duplicate)
        try:
            # Find message by message_id
            message = self.sudo().search([('message_id', '=', status_id)], limit=1)

            if not message:
                _logger.warning(
                    f"⚠️ Message {status_id} not found for status update. "
                    f"This can happen if message was sent outside Odoo or webhook arrived before send confirmation."
                )
                # Still mark as processed to avoid reprocessing
                WebhookEvent.mark_processed(event_id, 'status', status_data)
                return False

            # Update message status
            update_vals = {}

            if status == 'sent':
                update_vals = {
                    'state': 'sent',
                    'sent_date': fields.Datetime.now(),
                }
            elif status == 'delivered':
                update_vals = {
                    'state': 'delivered',
                    'delivered_date': fields.Datetime.now(),
                }
            elif status == 'read':
                update_vals = {
                    'state': 'read',
                    'read_date': fields.Datetime.now(),
                }
            elif status == 'failed':
                errors = status_data.get('errors', [])
                error_msg = errors[0].get('title', 'Unknown error') if errors else 'Unknown error'
                error_code = errors[0].get('code') if errors else None

                update_vals = {
                    'state': 'failed',
                    'error_message': f"[{error_code}] {error_msg}" if error_code else error_msg,
                }

                _logger.error(f"❌ Message {status_id} failed: {error_msg}")

            if update_vals:
                message.write(update_vals)

            # Mark webhook as processed
            WebhookEvent.mark_processed(
                event_id,
                'status',
                status_data,
                message_id=message.id,
                from_number=recipient
            )

            _logger.info(f"✅ Status update {event_id} processed successfully")
            return True

        except Exception as e:
            _logger.error(f"❌ Error processing status update {event_id}: {e}", exc_info=True)

            # Mark as error in webhook log
            WebhookEvent.mark_error(event_id, 'status', status_data, str(e))

            return False

    def _update_conversation_thread(self, patient, inbound=False, message_body=None, phone_number=None):
        """
        Update conversation thread for 24h window tracking

        Args:
            patient (recordset): Patient record
            inbound (bool): True if customer sent message (resets 24h window)
            message_body (str): Optional message preview
            phone_number (str): Optional phone number (if not in context)

        Returns:
            recordset: WhatsApp thread or empty recordset
        """
        if not patient:
            return self.env['clinic.whatsapp.thread']

        # Get phone number
        phone = phone_number or self.phone_number if hasattr(self, 'phone_number') else None
        if not phone and hasattr(patient, 'whatsapp_number'):
            phone = patient.whatsapp_number

        if not phone:
            _logger.warning(f"Cannot update thread for patient {patient.id}: no phone number")
            return self.env['clinic.whatsapp.thread']

        # Get or create thread
        Thread = self.env['clinic.whatsapp.thread'].sudo()
        thread = Thread.get_or_create_thread(
            patient_id=patient.id,
            phone_number=phone,
            phone_number_id=None  # TODO: Add multi-account support
        )

        # Update thread based on message direction
        if inbound:
            thread.update_inbound_message(message_body=message_body)
        else:
            thread.update_outbound_message(message_body=message_body)

        return thread

    def _route_to_discuss_channel(self, thread, message):
        """
        Route incoming WhatsApp message to Discuss channel

        Fase 5.2: Discuss Integration

        Creates or updates Discuss channel for this conversation
        Posts message to channel
        Notifies assigned operator

        Args:
            thread (recordset): WhatsApp thread
            message (recordset): WhatsApp message record
        """
        if not thread or not message:
            return

        # Check if thread already has a Discuss channel
        if not thread.discuss_channel_id:
            # Create new Discuss channel
            channel = self._create_discuss_channel(thread)

            if not channel:
                _logger.warning(f"Could not create Discuss channel for thread {thread.id}")
                return

            # Assign operator if not already assigned
            if not thread.assigned_operator_id:
                operator = thread.assign_to_operator()
                if operator:
                    # Add operator to channel
                    channel.write({
                        'channel_partner_ids': [(4, operator.partner_id.id)]
                    })

            # Link channel to thread
            thread.write({'discuss_channel_id': channel.id})
        else:
            channel = thread.discuss_channel_id

        # Post message to Discuss channel
        self._post_to_discuss_channel(channel, thread, message)

        # Notify operator
        if thread.assigned_operator_id:
            self._notify_operator(thread, message)

        _logger.info(
            f"✅ Message routed to Discuss channel {channel.id} "
            f"for operator {thread.assigned_operator_id.name if thread.assigned_operator_id else 'None'}"
        )

    def _create_discuss_channel(self, thread):
        """
        Create a new Discuss channel for WhatsApp conversation

        Args:
            thread (recordset): WhatsApp thread

        Returns:
            recordset: discuss.channel or False
        """
        try:
            Channel = self.env['discuss.channel'].sudo()

            channel_name = f"WhatsApp: {thread.patient_id.name}"

            # Check if channel already exists
            existing_channel = Channel.search([
                ('name', '=', channel_name),
            ], limit=1)

            if existing_channel:
                return existing_channel

            # Create new channel
            channel = Channel.create({
                'name': channel_name,
                'description': f"WhatsApp conversation with {thread.patient_id.name} ({thread.phone_number})",
                'channel_type': 'chat',  # Private chat
                'public': 'private',  # Only invited members
                'email_send': False,  # Don't send emails
            })

            _logger.info(f"📢 Created Discuss channel {channel.id}: {channel_name}")
            return channel

        except Exception as e:
            _logger.error(f"❌ Error creating Discuss channel: {e}", exc_info=True)
            return False

    def _post_to_discuss_channel(self, channel, thread, message):
        """
        Post WhatsApp message to Discuss channel

        Args:
            channel (recordset): discuss.channel
            thread (recordset): WhatsApp thread
            message (recordset): WhatsApp message
        """
        if not channel or not message:
            return

        # Format message body
        message_html = self._format_message_for_discuss(message, thread)

        # Post to channel
        try:
            channel.message_post(
                body=message_html,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                author_id=thread.patient_id.partner_id.id if thread.patient_id.partner_id else False,
            )

            _logger.debug(f"Posted message to Discuss channel {channel.id}")

        except Exception as e:
            _logger.error(f"❌ Error posting to Discuss channel: {e}", exc_info=True)

    def _format_message_for_discuss(self, message, thread):
        """
        Format WhatsApp message for display in Discuss

        Args:
            message (recordset): WhatsApp message
            thread (recordset): WhatsApp thread

        Returns:
            str: HTML formatted message
        """
        # Customer name
        author = thread.patient_id.name if thread.patient_id else message.phone_number

        # Message type indicator
        type_icon = {
            'text': '💬',
            'image': '🖼️',
            'document': '📄',
            'audio': '🎤',
            'video': '🎥',
            'location': '📍',
        }.get(message.message_type, '📱')

        # Format timestamp
        timestamp = fields.Datetime.to_string(message.create_date)

        # Build HTML
        html = f"""
        <div class="whatsapp_message">
            <div class="message_header">
                <strong>{type_icon} {author}</strong>
                <span class="text-muted" style="font-size: 0.85em; margin-left: 10px;">
                    {timestamp}
                </span>
            </div>
            <div class="message_body" style="margin-top: 5px;">
                {message.message_body or '(No content)'}
            </div>
        """

        # Add media info if present
        if message.media_url:
            html += f"""
            <div class="message_media" style="margin-top: 5px; font-style: italic; color: #666;">
                Media ID: {message.media_url}
            </div>
            """

        html += "</div>"

        return html

    def _notify_operator(self, thread, message):
        """
        Notify operator about new incoming message

        Creates activity and sends notification

        Args:
            thread (recordset): WhatsApp thread
            message (recordset): WhatsApp message
        """
        if not thread.assigned_operator_id:
            return

        operator = thread.assigned_operator_id

        try:
            # Create activity
            thread.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=operator.id,
                summary=f'New WhatsApp message from {thread.patient_id.name}',
                note=f'{message.message_body[:100]}...' if len(message.message_body or '') > 100 else message.message_body,
            )

            # Send notification via bus
            if thread.discuss_channel_id:
                thread.discuss_channel_id._notify_thread(
                    message={'body': f'New message from {thread.patient_id.name}'},
                    partner_ids=operator.partner_id.ids
                )

            _logger.info(f"📬 Notified operator {operator.name} about new message in thread {thread.id}")

        except Exception as e:
            _logger.error(f"❌ Error notifying operator: {e}", exc_info=True)

    # ===== Fase 5.4: Enhanced Media Support =====

    def _download_whatsapp_media(self, message, message_data):
        """
        Download media from WhatsApp Cloud API and attach to message

        Fase 5.4: Enhanced Media Support

        Steps:
        1. Get media_id from message_data
        2. Call GET /v18.0/{media_id} to get download URL
        3. Download file from URL
        4. Validate size and MIME type
        5. Create ir.attachment
        6. Link to message and patient

        Args:
            message (recordset): WhatsApp message record
            message_data (dict): Original webhook payload

        Returns:
            recordset: ir.attachment or False
        """
        if not message or not message_data:
            return False

        try:
            # Get access token from settings
            access_token = self.env['ir.config_parameter'].sudo().get_param(
                'clinic.whatsapp.access_token'
            )

            if not access_token:
                _logger.error("❌ WhatsApp access token not configured - cannot download media")
                return False

            # Extract media_id based on message type
            media_id = self._extract_media_id(message_data, message.message_type)

            if not media_id:
                _logger.warning(f"⚠️ No media_id found in message {message.id}")
                return False

            # Step 1: Get media URL from Meta API
            media_url, mime_type, file_size = self._get_media_url(media_id, access_token)

            if not media_url:
                _logger.error(f"❌ Could not get media URL for {media_id}")
                return False

            # Step 2: Validate size
            if not self._validate_media_size(file_size, mime_type):
                _logger.warning(f"⚠️ Media {media_id} exceeds size limits: {file_size} bytes")
                message.write({
                    'message_body': f"{message.message_body}\n\n⚠️ Media too large to download ({file_size / (1024*1024):.2f} MB)"
                })
                return False

            # Step 3: Download file
            file_content = self._download_media_file(media_url, access_token)

            if not file_content:
                _logger.error(f"❌ Could not download media from {media_url}")
                return False

            # Step 4: Create attachment
            attachment = self._create_media_attachment(
                message,
                file_content,
                media_id,
                mime_type
            )

            if attachment:
                _logger.info(
                    f"✅ Media downloaded successfully: {attachment.name} "
                    f"({len(file_content) / 1024:.2f} KB)"
                )

            return attachment

        except Exception as e:
            _logger.error(f"❌ Error downloading WhatsApp media: {e}", exc_info=True)
            return False

    def _extract_media_id(self, message_data, message_type):
        """
        Extract media_id from webhook payload

        Args:
            message_data (dict): Webhook payload
            message_type (str): Type of message (image, document, audio, video)

        Returns:
            str: Media ID or False
        """
        media_id = None

        if message_type == 'image':
            media_id = message_data.get('image', {}).get('id')
        elif message_type == 'document':
            media_id = message_data.get('document', {}).get('id')
        elif message_type == 'audio':
            media_id = message_data.get('audio', {}).get('id')
        elif message_type == 'video':
            media_id = message_data.get('video', {}).get('id')

        return media_id

    def _get_media_url(self, media_id, access_token):
        """
        Get media download URL from Meta API

        API: GET https://graph.facebook.com/v18.0/{media_id}

        Args:
            media_id (str): Media ID from webhook
            access_token (str): WhatsApp access token

        Returns:
            tuple: (url, mime_type, file_size) or (False, False, False)
        """
        try:
            url = f"https://graph.facebook.com/v18.0/{media_id}"
            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            media_url = data.get('url')
            mime_type = data.get('mime_type')
            file_size = data.get('file_size', 0)

            return media_url, mime_type, file_size

        except requests.exceptions.RequestException as e:
            _logger.error(f"❌ Error getting media URL from Meta: {e}")
            return False, False, False

    def _validate_media_size(self, file_size, mime_type):
        """
        Validate media file size against WhatsApp limits

        Limits (Meta documentation):
        - Documents: 100 MB
        - Images: 5 MB
        - Audio: 16 MB
        - Video: 16 MB

        Args:
            file_size (int): File size in bytes
            mime_type (str): MIME type

        Returns:
            bool: True if within limits
        """
        if not file_size:
            return True  # Unknown size, allow

        # Define limits in bytes
        MAX_DOCUMENT_SIZE = 100 * 1024 * 1024  # 100 MB
        MAX_IMAGE_SIZE = 5 * 1024 * 1024       # 5 MB
        MAX_MEDIA_SIZE = 16 * 1024 * 1024      # 16 MB

        # Check by MIME type
        if mime_type and mime_type.startswith('image/'):
            return file_size <= MAX_IMAGE_SIZE
        elif mime_type and mime_type.startswith('application/'):
            return file_size <= MAX_DOCUMENT_SIZE
        elif mime_type and (mime_type.startswith('audio/') or mime_type.startswith('video/')):
            return file_size <= MAX_MEDIA_SIZE

        # Default: use document limit
        return file_size <= MAX_DOCUMENT_SIZE

    def _download_media_file(self, media_url, access_token):
        """
        Download media file from Meta CDN

        Args:
            media_url (str): Media download URL
            access_token (str): WhatsApp access token

        Returns:
            bytes: File content or False
        """
        try:
            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            response = requests.get(media_url, headers=headers, timeout=30)
            response.raise_for_status()

            return response.content

        except requests.exceptions.RequestException as e:
            _logger.error(f"❌ Error downloading media file: {e}")
            return False

    def _create_media_attachment(self, message, file_content, media_id, mime_type):
        """
        Create ir.attachment for media file

        Args:
            message (recordset): WhatsApp message
            file_content (bytes): File binary content
            media_id (str): Meta media ID
            mime_type (str): MIME type

        Returns:
            recordset: ir.attachment or False
        """
        try:
            # Determine file extension
            extension = self._get_file_extension(mime_type, message.message_type)

            # Generate filename
            filename = f"whatsapp_{message.message_type}_{media_id}{extension}"

            # Create attachment
            attachment = self.env['ir.attachment'].sudo().create({
                'name': filename,
                'datas': base64.b64encode(file_content),
                'res_model': 'clinic.whatsapp.message',
                'res_id': message.id,
                'mimetype': mime_type or 'application/octet-stream',
                'description': f'WhatsApp {message.message_type} from {message.patient_id.name}',
            })

            # Link attachment to message
            message.write({
                'attachment_ids': [(4, attachment.id)]
            })

            # Also attach to patient chatter
            if message.patient_id:
                message.patient_id.message_post(
                    body=f"📎 <strong>WhatsApp Media Received:</strong> {filename}",
                    attachment_ids=[attachment.id],
                    message_type='comment',
                    subtype_xmlid='mail.mt_note'
                )

            _logger.info(f"✅ Created attachment {attachment.id}: {filename}")
            return attachment

        except Exception as e:
            _logger.error(f"❌ Error creating attachment: {e}", exc_info=True)
            return False

    def _get_file_extension(self, mime_type, message_type):
        """
        Get file extension based on MIME type

        Args:
            mime_type (str): MIME type
            message_type (str): Message type (image, document, audio, video)

        Returns:
            str: File extension with dot (e.g., '.jpg')
        """
        # MIME type mapping
        mime_extensions = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp',
            'application/pdf': '.pdf',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/vnd.ms-excel': '.xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
            'audio/mpeg': '.mp3',
            'audio/ogg': '.ogg',
            'audio/aac': '.aac',
            'video/mp4': '.mp4',
            'video/3gpp': '.3gp',
        }

        if mime_type in mime_extensions:
            return mime_extensions[mime_type]

        # Fallback based on message type
        type_extensions = {
            'image': '.jpg',
            'document': '.pdf',
            'audio': '.mp3',
            'video': '.mp4',
        }

        return type_extensions.get(message_type, '')