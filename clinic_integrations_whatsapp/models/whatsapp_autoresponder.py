# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class WhatsAppAutoResponder(models.Model):
    """
    WhatsApp Auto-Responder Configuration

    Configurable automatic responses based on keywords and business hours

    Fase 5.3: Auto-Responder System
    """
    _name = 'clinic.whatsapp.autoresponder'
    _description = 'WhatsApp Auto-Responder'
    _order = 'priority desc, id'
    _rec_name = 'name'

    name = fields.Char(
        string='Name',
        required=True,
        help='Descriptive name for this auto-responder rule'
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        help='Enable/disable this auto-responder'
    )

    trigger_keywords = fields.Char(
        string='Trigger Keywords',
        required=True,
        help='Comma-separated keywords (e.g., "hola,hi,hello,buenos días")'
    )

    match_type = fields.Selection([
        ('exact', 'Exact Match'),
        ('contains', 'Contains Keyword'),
        ('starts_with', 'Starts With'),
        ('regex', 'Regular Expression'),
    ], string='Match Type',
       default='contains',
       required=True,
       help='How to match keywords in incoming messages')

    case_sensitive = fields.Boolean(
        string='Case Sensitive',
        default=False,
        help='Match keywords with case sensitivity'
    )

    response_template = fields.Text(
        string='Response Message',
        required=True,
        help='Auto-response message to send. Use {{patient_name}} for personalization.'
    )

    priority = fields.Integer(
        string='Priority',
        default=10,
        help='Higher priority rules are checked first (higher number = higher priority)'
    )

    # Business Hours Configuration
    active_hours_only = fields.Boolean(
        string='Business Hours Only',
        default=False,
        help='Only respond during business hours'
    )

    working_hours_start = fields.Float(
        string='Business Hours Start',
        default=8.0,
        help='Start of business hours (24h format, e.g. 8.5 = 8:30 AM)'
    )

    working_hours_end = fields.Float(
        string='Business Hours End',
        default=18.0,
        help='End of business hours (24h format, e.g. 18.0 = 6:00 PM)'
    )

    working_days = fields.Selection([
        ('weekdays', 'Monday - Friday'),
        ('weekdays_sat', 'Monday - Saturday'),
        ('all', 'Every Day'),
        ('custom', 'Custom Days'),
    ], string='Working Days',
       default='weekdays',
       help='Days when this auto-responder is active')

    custom_working_days = fields.Char(
        string='Custom Days',
        help='Comma-separated days (0=Monday, 6=Sunday). Example: 0,1,2,3,4'
    )

    # Response Behavior
    send_once_per_conversation = fields.Boolean(
        string='Send Once Per Conversation',
        default=True,
        help='Only send this auto-response once per conversation thread'
    )

    cooldown_minutes = fields.Integer(
        string='Cooldown Period (minutes)',
        default=60,
        help='Minimum time between sending this auto-response to same customer'
    )

    stop_on_match = fields.Boolean(
        string='Stop on Match',
        default=True,
        help='Stop checking other auto-responders if this one matches'
    )

    # Conditions
    only_for_new_threads = fields.Boolean(
        string='Only for New Conversations',
        default=False,
        help='Only respond to first message in a new conversation'
    )

    only_outside_hours = fields.Boolean(
        string='Only Outside Business Hours',
        default=False,
        help='Only respond when outside business hours (for after-hours messages)'
    )

    # Statistics
    total_triggered = fields.Integer(
        string='Times Triggered',
        default=0,
        readonly=True,
        help='Total number of times this auto-responder was triggered'
    )

    last_triggered_at = fields.Datetime(
        string='Last Triggered',
        readonly=True,
        help='Last time this auto-responder was triggered'
    )

    # Meta
    notes = fields.Text(
        string='Notes',
        help='Internal notes about this auto-responder'
    )

    # SQL Constraints
    _sql_constraints = [
        ('priority_positive', 'CHECK(priority >= 0)',
         'Priority must be non-negative'),
        ('cooldown_positive', 'CHECK(cooldown_minutes >= 0)',
         'Cooldown period must be non-negative'),
    ]

    @api.constrains('working_hours_start', 'working_hours_end')
    def _check_working_hours(self):
        """Validate working hours"""
        for responder in self:
            if responder.active_hours_only or responder.only_outside_hours:
                if responder.working_hours_start < 0 or responder.working_hours_start >= 24:
                    raise ValidationError(_("Working hours start must be between 0 and 24"))
                if responder.working_hours_end <= responder.working_hours_start:
                    raise ValidationError(_("Working hours end must be after start"))
                if responder.working_hours_end > 24:
                    raise ValidationError(_("Working hours end cannot exceed 24"))

    @api.constrains('trigger_keywords')
    def _check_trigger_keywords(self):
        """Validate trigger keywords"""
        for responder in self:
            if not responder.trigger_keywords or not responder.trigger_keywords.strip():
                raise ValidationError(_("Trigger keywords cannot be empty"))

    def matches_message(self, message_body):
        """
        Check if message matches this auto-responder's keywords

        Args:
            message_body (str): Incoming message text

        Returns:
            bool: True if message matches
        """
        self.ensure_one()

        if not message_body:
            return False

        # Prepare message for comparison
        msg = message_body if self.case_sensitive else message_body.lower()

        # Get keywords
        keywords = [k.strip() for k in self.trigger_keywords.split(',') if k.strip()]
        if not self.case_sensitive:
            keywords = [k.lower() for k in keywords]

        # Check match type
        if self.match_type == 'exact':
            # Exact match (whole message equals keyword)
            return msg in keywords

        elif self.match_type == 'contains':
            # Contains any keyword
            return any(keyword in msg for keyword in keywords)

        elif self.match_type == 'starts_with':
            # Starts with any keyword
            return any(msg.startswith(keyword) for keyword in keywords)

        elif self.match_type == 'regex':
            # Regex match (use trigger_keywords as regex pattern)
            try:
                pattern = re.compile(self.trigger_keywords, re.IGNORECASE if not self.case_sensitive else 0)
                return bool(pattern.search(msg))
            except re.error as e:
                _logger.error(f"Invalid regex pattern in auto-responder {self.id}: {e}")
                return False

        return False

    def is_within_business_hours(self):
        """
        Check if current time is within business hours

        Returns:
            bool: True if within business hours
        """
        self.ensure_one()

        now = datetime.now()
        current_hour = now.hour + now.minute / 60.0  # Convert to decimal (e.g., 14:30 = 14.5)
        current_weekday = now.weekday()  # 0 = Monday, 6 = Sunday

        # Check time range
        if not (self.working_hours_start <= current_hour < self.working_hours_end):
            return False

        # Check working days
        if self.working_days == 'weekdays':
            return current_weekday < 5  # Monday-Friday

        elif self.working_days == 'weekdays_sat':
            return current_weekday < 6  # Monday-Saturday

        elif self.working_days == 'all':
            return True  # Every day

        elif self.working_days == 'custom':
            if not self.custom_working_days:
                return True
            custom_days = [int(d.strip()) for d in self.custom_working_days.split(',') if d.strip().isdigit()]
            return current_weekday in custom_days

        return True

    def should_respond(self, thread, message_body):
        """
        Check all conditions to determine if should send auto-response

        Args:
            thread (recordset): WhatsApp thread
            message_body (str): Incoming message text

        Returns:
            bool: True if should send auto-response
        """
        self.ensure_one()

        # Check if active
        if not self.active:
            return False

        # Check keyword match
        if not self.matches_message(message_body):
            return False

        # Check business hours conditions
        is_business_hours = self.is_within_business_hours()

        if self.active_hours_only and not is_business_hours:
            return False

        if self.only_outside_hours and is_business_hours:
            return False

        # Check if only for new threads
        if self.only_for_new_threads:
            if thread.inbound_count > 1:  # Already had messages
                return False

        # Check cooldown period
        if self.cooldown_minutes > 0:
            if not self._check_cooldown(thread):
                return False

        # Check send once per conversation
        if self.send_once_per_conversation:
            if self._already_sent_to_thread(thread):
                return False

        return True

    def _check_cooldown(self, thread):
        """
        Check if cooldown period has passed

        Args:
            thread (recordset): WhatsApp thread

        Returns:
            bool: True if cooldown passed
        """
        self.ensure_one()

        if not self.last_triggered_at:
            return True

        # Check if this responder was recently sent to this thread
        recent_messages = self.env['clinic.whatsapp.message'].search([
            ('patient_id', '=', thread.patient_id.id),
            ('direction', '=', 'outbound'),
            ('message_body', 'ilike', self.response_template[:50]),  # Match first 50 chars
            ('create_date', '>', fields.Datetime.now() - timedelta(minutes=self.cooldown_minutes)),
        ], limit=1)

        return not bool(recent_messages)

    def _already_sent_to_thread(self, thread):
        """
        Check if this auto-response was already sent to this thread

        Args:
            thread (recordset): WhatsApp thread

        Returns:
            bool: True if already sent
        """
        self.ensure_one()

        # Search for messages with similar content
        existing_messages = self.env['clinic.whatsapp.message'].search([
            ('patient_id', '=', thread.patient_id.id),
            ('direction', '=', 'outbound'),
            ('message_body', 'ilike', self.response_template[:50]),
        ], limit=1)

        return bool(existing_messages)

    def send_response(self, thread):
        """
        Send auto-response to customer

        Args:
            thread (recordset): WhatsApp thread

        Returns:
            recordset: Created message or empty recordset
        """
        self.ensure_one()

        try:
            # Personalize message
            message_text = self.response_template

            if '{{patient_name}}' in message_text:
                patient_name = thread.patient_id.name if thread.patient_id else 'Customer'
                message_text = message_text.replace('{{patient_name}}', patient_name)

            # Create outbound message
            WhatsAppMessage = self.env['clinic.whatsapp.message'].sudo()

            message = WhatsAppMessage.create({
                'patient_id': thread.patient_id.id,
                'phone_number': thread.phone_number,
                'direction': 'outbound',
                'message_type': 'text',
                'message_body': message_text,
                'category': 'auto_response',
                'state': 'queued',
            })

            # Send message
            message.action_send()

            # Update statistics
            self.write({
                'total_triggered': self.total_triggered + 1,
                'last_triggered_at': fields.Datetime.now(),
            })

            _logger.info(
                f"✅ Auto-responder '{self.name}' sent to {thread.patient_id.name} "
                f"(thread {thread.id})"
            )

            return message

        except Exception as e:
            _logger.error(f"❌ Error sending auto-response: {e}", exc_info=True)
            return self.env['clinic.whatsapp.message']

    @api.model
    def process_incoming_message(self, thread, message_body):
        """
        Process incoming message against all active auto-responders

        Called from whatsapp_message._check_automated_response_v2()

        Args:
            thread (recordset): WhatsApp thread
            message_body (str): Incoming message text

        Returns:
            bool: True if any auto-response was sent
        """
        # Get all active auto-responders ordered by priority
        responders = self.search([
            ('active', '=', True)
        ], order='priority desc, id')

        response_sent = False

        for responder in responders:
            if responder.should_respond(thread, message_body):
                responder.send_response(thread)
                response_sent = True

                # Stop if configured to stop on match
                if responder.stop_on_match:
                    break

        return response_sent

    def action_test_response(self):
        """
        Test this auto-responder (for UI button)

        Returns:
            dict: Notification action
        """
        self.ensure_one()

        # Show preview
        preview = self.response_template

        if '{{patient_name}}' in preview:
            preview = preview.replace('{{patient_name}}', 'John Doe')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Auto-Responder Test'),
                'message': preview,
                'type': 'info',
                'sticky': True,
            }
        }

    def action_view_statistics(self):
        """View detailed statistics for this auto-responder"""
        self.ensure_one()

        return {
            'name': _('Auto-Responder Statistics: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.whatsapp.autoresponder',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
