# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import requests
import json
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
        """Send WhatsApp message with rate limiting"""
        self.ensure_one()

        if self.state not in ['draft', 'failed']:
            raise UserError(_("Message cannot be sent in current state."))

        # Check patient opt-in (if required by configuration)
        config_helper = self.env['clinic.whatsapp.config.helper']
        require_opt_in = config_helper.get_config_value('require_opt_in', 'True') == 'True'

        if require_opt_in and not self.patient_id.whatsapp_opt_in:
            raise UserError(_("Patient has not opted in for WhatsApp messages."))

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

        if not config.get('api_token'):
            self.write({
                'state': 'failed',
                'error_message': 'WhatsApp API token not configured. Please configure in Settings > WhatsApp Configuration.'
            })
            return False

        if not config.get('phone_number'):
            self.write({
                'state': 'failed',
                'error_message': 'WhatsApp phone number not configured. Please configure in Settings > WhatsApp Configuration.'
            })
            return False

        try:
            self.state = 'sending'

            # Prepare API request
            headers = {
                'Authorization': f'Bearer {config["api_token"]}',
                'Content-Type': 'application/json'
            }

            # Build message payload based on type
            if self.message_type == 'template':
                payload = self._build_template_payload(config)
            else:
                payload = self._build_text_payload(config)

            # Send API request
            response = requests.post(
                f"{config['api_url']}/{config['phone_number']}/messages",
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
    
    def _check_automated_response(self, patient, message_body):
        """Check if automated response is needed"""
        message_lower = message_body.lower()
        
        # Check for appointment confirmation
        if 'confirm' in message_lower:
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
                    'phone_number': patient.whatsapp_number,
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
    
    def name_get(self):
        return [(msg.id, msg.display_name) for msg in self]