# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class WhatsAppThread(models.Model):
    """
    WhatsApp Conversation Thread

    🎯 PURPOSE: Track 24-hour window per conversation for Meta's messaging rules

    Meta Rules:
    - Customer-initiated: Within 24h of last inbound message → can send FREE TEXT
    - Business-initiated: Outside 24h window → MUST use approved TEMPLATE

    Reference: https://developers.facebook.com/docs/whatsapp/pricing#opened-and-closed-conversations
    """
    _name = 'clinic.whatsapp.thread'
    _description = 'WhatsApp Conversation Thread'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'last_inbound_at desc'
    _rec_name = 'display_name'

    # Identification
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        index=True,
        ondelete='cascade'
    )

    phone_number = fields.Char(
        string='Phone Number',
        required=True,
        index=True,
        help="Customer's WhatsApp number (E.164 format)"
    )

    phone_number_id = fields.Char(
        string='Meta Phone Number ID',
        help="WhatsApp Business Phone Number ID (for multi-account support)"
    )

    # Conversation timestamps
    last_inbound_at = fields.Datetime(
        string='Last Customer Message',
        help='When customer last sent us a message (resets 24h window)',
        index=True
    )

    last_outbound_at = fields.Datetime(
        string='Last Business Message',
        help='When we last sent a message to customer'
    )

    first_message_at = fields.Datetime(
        string='Conversation Started',
        default=fields.Datetime.now,
        readonly=True
    )

    # 24-hour window tracking
    is_within_24h_window = fields.Boolean(
        string='Within 24h Window',
        compute='_compute_is_within_24h_window',
        store=True,
        help='True if customer sent message within last 24 hours (can send free text)'
    )

    window_expires_at = fields.Datetime(
        string='Window Expires At',
        compute='_compute_is_within_24h_window',
        store=False,
        help='When the 24h window will close'
    )

    # Fase 3.1: UI-friendly fields
    window_status_text = fields.Char(
        string='Window Status',
        compute='_compute_window_ui_fields',
        store=True,
        help='Human-readable window status for UI'
    )

    window_time_remaining = fields.Char(
        string='Time Remaining',
        compute='_compute_window_ui_fields',
        store=True,
        help='Formatted time remaining (e.g., "5h 30m")'
    )

    window_urgency_level = fields.Selection([
        ('none', 'No Window'),  # No customer message yet
        ('expired', 'Expired'),  # Outside 24h
        ('normal', 'Normal'),  # > 6h remaining
        ('warning', 'Warning'),  # 3-6h remaining
        ('urgent', 'Urgent'),  # < 3h remaining
    ], string='Urgency Level',
       compute='_compute_window_ui_fields',
       store=True,
       help='Urgency indicator for UI color coding')

    can_send_text = fields.Boolean(
        string='Can Send Free Text',
        compute='_compute_window_ui_fields',
        store=True,
        help='Quick check for send button enablement'
    )

    requires_template = fields.Boolean(
        string='Requires Template',
        compute='_compute_window_ui_fields',
        store=True,
        help='True if must use approved template'
    )

    # Statistics
    inbound_count = fields.Integer(
        string='Inbound Messages',
        default=0,
        help='Total messages received from customer'
    )

    outbound_count = fields.Integer(
        string='Outbound Messages',
        default=0,
        help='Total messages sent to customer'
    )

    last_message_body = fields.Text(
        string='Last Message',
        help='Preview of last message in conversation'
    )

    last_message_direction = fields.Selection([
        ('inbound', 'Inbound'),
        ('outbound', 'Outbound'),
    ], string='Last Message Direction')

    # Fase 5.1: Operator Assignment & Escalation
    assigned_operator_id = fields.Many2one(
        'res.users',
        string='Assigned Operator',
        tracking=True,
        index=True,
        domain=[('share', '=', False)],  # Only internal users
        help='WhatsApp operator assigned to handle this conversation'
    )

    discuss_channel_id = fields.Many2one(
        'discuss.channel',
        string='Discuss Channel',
        ondelete='set null',
        help='Linked Discuss channel for real-time chat'
    )

    escalation_status = fields.Selection([
        ('none', 'No Escalation'),
        ('pending', 'Pending Response'),
        ('warning', 'Response Overdue'),
        ('escalated', 'Escalated to Supervisor'),
        ('resolved', 'Resolved'),
    ], string='Escalation Status',
       default='none',
       tracking=True,
       help='Current escalation level based on response time')

    last_operator_reply_at = fields.Datetime(
        string='Last Operator Reply',
        help='When operator last replied to customer',
        index=True
    )

    escalation_deadline = fields.Datetime(
        string='Escalation Deadline',
        compute='_compute_escalation_deadline',
        store=True,
        help='When thread will be escalated if no operator response'
    )

    pending_customer_reply = fields.Boolean(
        string='Pending Customer Reply',
        compute='_compute_pending_reply',
        store=True,
        help='True if last message was from operator (waiting for customer)'
    )

    escalation_hours_threshold = fields.Integer(
        string='Escalation Threshold (Hours)',
        default=24,
        help='Hours to wait before escalating thread'
    )

    # Status
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Inactive threads are archived conversations'
    )

    # SQL constraints
    _sql_constraints = [
        ('patient_phone_unique', 'UNIQUE(patient_id, phone_number)',
         'Only one conversation thread per patient phone number'),
    ]

    @api.depends('patient_id', 'phone_number')
    def _compute_display_name(self):
        for thread in self:
            if thread.patient_id:
                thread.display_name = f"{thread.patient_id.name} ({thread.phone_number})"
            else:
                thread.display_name = thread.phone_number or 'New Thread'

    @api.depends('last_inbound_at')
    def _compute_is_within_24h_window(self):
        """
        Calculate if conversation is within 24h window

        Critical for message type validation:
        - within_24h = True → can send free text
        - within_24h = False → must use template
        """
        now = fields.Datetime.now()

        for thread in self:
            if thread.last_inbound_at:
                delta = now - thread.last_inbound_at
                thread.is_within_24h_window = delta.total_seconds() < 86400

                if thread.is_within_24h_window:
                    # Calculate expiration time
                    thread.window_expires_at = thread.last_inbound_at + timedelta(hours=24)
                else:
                    thread.window_expires_at = False
            else:
                # No customer message yet → business-initiated only (templates)
                thread.is_within_24h_window = False
                thread.window_expires_at = False

    @api.depends('last_inbound_at', 'is_within_24h_window', 'window_expires_at')
    def _compute_window_ui_fields(self):
        """
        Compute UI-friendly fields for 24h window display

        Fase 3.1: Enhanced UI indicators
        """
        now = fields.Datetime.now()

        for thread in self:
            # Default values
            thread.can_send_text = False
            thread.requires_template = True
            thread.window_status_text = ''
            thread.window_time_remaining = ''
            thread.window_urgency_level = 'none'

            if not thread.last_inbound_at:
                # No customer message yet
                thread.window_status_text = "⚠️ No customer message - templates only"
                thread.window_urgency_level = 'none'
                thread.requires_template = True
                thread.can_send_text = False

            elif thread.is_within_24h_window and thread.window_expires_at:
                # Window is open - calculate remaining time
                remaining = thread.window_expires_at - now
                total_seconds = remaining.total_seconds()

                # Format time remaining
                hours = int(total_seconds / 3600)
                minutes = int((total_seconds % 3600) / 60)

                if hours > 0:
                    thread.window_time_remaining = f"{hours}h {minutes}m"
                else:
                    thread.window_time_remaining = f"{minutes}m"

                # Determine urgency level
                if total_seconds < 10800:  # < 3 hours
                    thread.window_urgency_level = 'urgent'
                    thread.window_status_text = f"🔥 Window closing soon ({thread.window_time_remaining})"
                elif total_seconds < 21600:  # < 6 hours
                    thread.window_urgency_level = 'warning'
                    thread.window_status_text = f"⚠️ Window expires in {thread.window_time_remaining}"
                else:  # >= 6 hours
                    thread.window_urgency_level = 'normal'
                    thread.window_status_text = f"✅ Free text OK ({thread.window_time_remaining} left)"

                thread.can_send_text = True
                thread.requires_template = False

            else:
                # Window closed - calculate how long ago
                if thread.last_inbound_at:
                    elapsed = now - thread.last_inbound_at
                    days = int(elapsed.total_seconds() / 86400)
                    hours = int((elapsed.total_seconds() % 86400) / 3600)

                    if days > 0:
                        thread.window_status_text = f"❌ Window closed {days}d {hours}h ago - templates only"
                    else:
                        thread.window_status_text = f"❌ Window closed {hours}h ago - templates only"

                thread.window_urgency_level = 'expired'
                thread.requires_template = True
                thread.can_send_text = False

    @api.model
    def get_or_create_thread(self, patient_id, phone_number, phone_number_id=None):
        """
        Get existing thread or create new one

        Args:
            patient_id (int): Patient record ID
            phone_number (str): Customer phone number
            phone_number_id (str): Optional Meta phone number ID

        Returns:
            recordset: WhatsApp thread
        """
        thread = self.search([
            ('patient_id', '=', patient_id),
            ('phone_number', '=', phone_number),
        ], limit=1)

        if not thread:
            _logger.info(f"Creating new WhatsApp thread for patient {patient_id}")
            thread = self.create({
                'patient_id': patient_id,
                'phone_number': phone_number,
                'phone_number_id': phone_number_id,
            })

        return thread

    def update_inbound_message(self, message_body=None):
        """
        Update thread when customer sends message

        🔄 CRITICAL: This resets the 24h window!

        Args:
            message_body (str): Optional preview of message content
        """
        self.ensure_one()

        now = fields.Datetime.now()

        update_vals = {
            'last_inbound_at': now,
            'inbound_count': self.inbound_count + 1,
            'last_message_direction': 'inbound',
        }

        if message_body:
            # Store preview (first 200 chars)
            update_vals['last_message_body'] = message_body[:200]

        self.write(update_vals)

        _logger.info(
            f"✅ Thread {self.id} updated: 24h window reset "
            f"(expires at {now + timedelta(hours=24)})"
        )

    def update_outbound_message(self, message_body=None):
        """
        Update thread when business sends message

        Note: Does NOT reset 24h window

        Args:
            message_body (str): Optional preview of message content
        """
        self.ensure_one()

        now = fields.Datetime.now()

        update_vals = {
            'last_outbound_at': now,
            'outbound_count': self.outbound_count + 1,
            'last_message_direction': 'outbound',
        }

        if message_body:
            update_vals['last_message_body'] = message_body[:200]

        self.write(update_vals)

    def can_send_free_text(self):
        """
        Check if free text messages are allowed

        Returns:
            dict: {
                'allowed': bool,
                'reason': str,
                'expires_at': datetime or False
            }
        """
        self.ensure_one()

        if self.is_within_24h_window:
            return {
                'allowed': True,
                'reason': 'Customer-initiated conversation (within 24h window)',
                'expires_at': self.window_expires_at,
            }
        else:
            return {
                'allowed': False,
                'reason': 'Outside 24h window - must use approved template',
                'expires_at': False,
            }

    def action_view_messages(self):
        """Open all messages for this thread"""
        self.ensure_one()

        return {
            'name': f'Messages - {self.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.whatsapp.message',
            'view_mode': 'tree,form',
            'domain': [
                ('patient_id', '=', self.patient_id.id),
                ('phone_number', '=', self.phone_number),
            ],
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_phone_number': self.phone_number,
            }
        }

    @api.model
    def cleanup_inactive_threads(self, days=180):
        """
        Archive threads with no activity for N days

        Should be called by scheduled action monthly

        Args:
            days (int): Inactivity threshold

        Returns:
            int: Number of archived threads
        """
        cutoff_date = fields.Datetime.now() - timedelta(days=days)

        inactive_threads = self.search([
            ('active', '=', True),
            '|',
            ('last_inbound_at', '<', cutoff_date),
            ('last_outbound_at', '<', cutoff_date),
        ])

        count = len(inactive_threads)
        inactive_threads.write({'active': False})

        _logger.info(f"🧹 Archived {count} inactive WhatsApp threads (older than {days} days)")
        return count

    def get_window_status_display(self):
        """
        Get human-readable window status

        Returns:
            str: Status message for UI
        """
        self.ensure_one()

        if not self.last_inbound_at:
            return "⚠️ No customer message yet - templates only"

        if self.is_within_24h_window:
            remaining = self.window_expires_at - fields.Datetime.now()
            hours = int(remaining.total_seconds() / 3600)
            minutes = int((remaining.total_seconds() % 3600) / 60)
            return f"✅ Free text allowed (expires in {hours}h {minutes}m)"
        else:
            elapsed = fields.Datetime.now() - self.last_inbound_at
            days = int(elapsed.total_seconds() / 86400)
            return f"❌ Window closed {days} day(s) ago - templates only"

    def action_send_message_from_dashboard(self):
        """
        Quick action to send WhatsApp message from dashboard

        Fase 3.5: Opens message wizard with thread context

        Returns:
            dict: Window action to open message wizard
        """
        self.ensure_one()

        return {
            'name': f'Send WhatsApp to {self.patient_id.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.whatsapp.message.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_phone_number': self.phone_number,
                'default_message_type': 'text' if self.can_send_text else 'template',
            }
        }

    # ===== Fase 5.1: Operator Assignment & Escalation Methods =====

    @api.depends('last_inbound_at', 'last_operator_reply_at', 'escalation_hours_threshold')
    def _compute_escalation_deadline(self):
        """
        Calculate when thread will be escalated if no operator response

        Deadline = last_inbound_at + escalation_hours_threshold
        Only set if:
        - Customer sent message (last_inbound_at exists)
        - No operator reply OR operator reply before last customer message
        """
        for thread in self:
            if thread.last_inbound_at and thread.escalation_status in ('pending', 'warning'):
                # Only set deadline if operator hasn't replied yet
                # or replied before the last customer message
                if not thread.last_operator_reply_at or \
                   thread.last_operator_reply_at < thread.last_inbound_at:
                    hours = thread.escalation_hours_threshold or 24
                    thread.escalation_deadline = thread.last_inbound_at + timedelta(hours=hours)
                else:
                    # Operator already replied after customer's last message
                    thread.escalation_deadline = False
            else:
                thread.escalation_deadline = False

    @api.depends('last_inbound_at', 'last_operator_reply_at', 'last_outbound_at')
    def _compute_pending_reply(self):
        """
        Determine if waiting for customer or operator reply

        Logic:
        - If last_outbound_at > last_inbound_at → pending customer reply
        - Otherwise → pending operator reply (or no messages yet)
        """
        for thread in self:
            if thread.last_outbound_at and thread.last_inbound_at:
                # Pending customer reply if we sent message after their last message
                thread.pending_customer_reply = thread.last_outbound_at > thread.last_inbound_at
            else:
                # No conversation yet or only customer messages
                thread.pending_customer_reply = False

    def assign_to_operator(self, operator_id=None):
        """
        Assign thread to an operator

        Args:
            operator_id (int): User ID to assign, or None to auto-assign

        Returns:
            res.users: Assigned operator
        """
        self.ensure_one()

        if operator_id:
            operator = self.env['res.users'].browse(operator_id)
        else:
            operator = self._assign_available_operator()

        if operator:
            self.write({
                'assigned_operator_id': operator.id,
                'escalation_status': 'pending',
            })
            _logger.info(f"Thread {self.id} assigned to operator {operator.name}")

        return operator

    def _assign_available_operator(self):
        """
        Find and assign an available operator using round-robin logic

        Priority:
        1. Operators marked as available
        2. Operators with fewest active chats
        3. Operators in WhatsApp Operator group

        Returns:
            res.users: Assigned operator or False
        """
        # Find users in WhatsApp Operator group
        operator_group = self.env.ref(
            'clinic_integrations_whatsapp.group_whatsapp_operator',
            raise_if_not_found=False
        )

        if not operator_group:
            _logger.warning("WhatsApp Operator group not found - cannot auto-assign")
            return False

        # Get all operators in the group
        operators = operator_group.users.filtered(lambda u: not u.share and u.active)

        if not operators:
            _logger.warning("No active operators found in WhatsApp Operator group")
            return False

        # Check if we have operator assignment model (Phase 5.2)
        if hasattr(self.env, 'clinic.whatsapp.operator.assignment'):
            # Use assignment model to find available operator
            Assignment = self.env['clinic.whatsapp.operator.assignment']
            available_assignments = Assignment.search([
                ('operator_id', 'in', operators.ids),
                ('available', '=', True),
            ], order='current_chats_count asc', limit=1)

            if available_assignments:
                return available_assignments[0].operator_id

        # Fallback: Simple round-robin by counting active threads
        operator_thread_counts = {}
        for operator in operators:
            count = self.search_count([
                ('assigned_operator_id', '=', operator.id),
                ('escalation_status', 'in', ['pending', 'warning']),
                ('active', '=', True),
            ])
            operator_thread_counts[operator.id] = count

        # Return operator with fewest threads
        if operator_thread_counts:
            min_operator_id = min(operator_thread_counts, key=operator_thread_counts.get)
            return self.env['res.users'].browse(min_operator_id)

        # Last resort: return first operator
        return operators[0]

    def update_operator_reply(self):
        """
        Update thread when operator sends a reply

        Called by whatsapp_message model when outbound message is sent
        """
        self.ensure_one()

        now = fields.Datetime.now()

        # Update timestamps
        self.write({
            'last_operator_reply_at': now,
            'escalation_status': 'resolved',  # Operator responded
        })

        _logger.info(f"Thread {self.id} - operator replied, escalation resolved")

    def action_escalate_thread(self):
        """
        Manually escalate thread to supervisor

        Can be called by operator or automatically by cron
        """
        self.ensure_one()

        supervisor_group = self.env.ref(
            'clinic_integrations_whatsapp.group_whatsapp_supervisor',
            raise_if_not_found=False
        )

        if not supervisor_group or not supervisor_group.users:
            _logger.warning("No supervisors found to escalate thread")
            return False

        # Get supervisor with fewest escalated threads
        supervisors = supervisor_group.users.filtered(lambda u: not u.share and u.active)
        supervisor_counts = {}
        for sup in supervisors:
            count = self.search_count([
                ('assigned_operator_id', '=', sup.id),
                ('escalation_status', '=', 'escalated'),
            ])
            supervisor_counts[sup.id] = count

        supervisor_id = min(supervisor_counts, key=supervisor_counts.get) if supervisor_counts else supervisors[0].id
        supervisor = self.env['res.users'].browse(supervisor_id)

        # Escalate
        self.write({
            'escalation_status': 'escalated',
            'assigned_operator_id': supervisor.id,
        })

        # Create activity for supervisor
        self.activity_schedule(
            'mail.mail_activity_data_warning',
            user_id=supervisor.id,
            summary=f'Escalated WhatsApp conversation: {self.patient_id.name}',
            note=f'Customer waiting for response since {self.last_inbound_at}\n'
                 f'Last message: {self.last_message_body[:100]}...'
        )

        # Log in chatter
        self.message_post(
            body=f"⚠️ <strong>Thread escalated to {supervisor.name}</strong><br/>"
                 f"Reason: No operator response for {self.escalation_hours_threshold} hours",
            message_type='notification',
        )

        _logger.warning(
            f"Thread {self.id} escalated to supervisor {supervisor.name} "
            f"(no response for {self.escalation_hours_threshold}h)"
        )

        return True

    @api.model
    def monitor_escalations(self):
        """
        Cron job: Monitor threads and escalate if needed

        Run frequency: Every hour
        Escalation rules:
        - pending + deadline passed → warning
        - warning + 24h more → escalated
        """
        now = fields.Datetime.now()

        # Find threads pending with deadline passed
        pending_threads = self.search([
            ('escalation_status', '=', 'pending'),
            ('escalation_deadline', '!=', False),
            ('escalation_deadline', '<', now),
        ])

        for thread in pending_threads:
            thread.write({'escalation_status': 'warning'})
            _logger.info(f"Thread {thread.id} moved to WARNING status")

            # Notify assigned operator
            if thread.assigned_operator_id:
                thread.activity_schedule(
                    'mail.mail_activity_data_warning',
                    user_id=thread.assigned_operator_id.id,
                    summary=f'⏰ WhatsApp response overdue: {thread.patient_id.name}',
                    note=f'Customer waiting since: {thread.last_inbound_at}'
                )

        # Find threads in warning for >24h → escalate
        warning_deadline = now - timedelta(hours=24)
        warning_threads = self.search([
            ('escalation_status', '=', 'warning'),
            ('last_inbound_at', '<', warning_deadline),
            ('last_operator_reply_at', '=', False),  # Still no reply
        ])

        escalated_count = 0
        for thread in warning_threads:
            if thread.action_escalate_thread():
                escalated_count += 1

        _logger.info(
            f"Escalation monitor: {len(pending_threads)} moved to warning, "
            f"{escalated_count} escalated to supervisor"
        )

        return {
            'warnings': len(pending_threads),
            'escalated': escalated_count,
        }

    def action_open_discuss_channel(self):
        """
        Open linked Discuss channel

        Returns:
            dict: Action to open channel in Discuss
        """
        self.ensure_one()

        if not self.discuss_channel_id:
            raise UserError(_("No Discuss channel linked to this conversation."))

        return {
            'name': _('WhatsApp Chat'),
            'type': 'ir.actions.act_window',
            'res_model': 'discuss.channel',
            'res_id': self.discuss_channel_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
