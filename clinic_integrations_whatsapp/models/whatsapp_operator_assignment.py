# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class WhatsAppOperatorAssignment(models.Model):
    """
    WhatsApp Operator Assignment Configuration

    Manages operator availability and capacity for WhatsApp conversations

    Fase 5.1: Operator Assignment & Load Balancing
    """
    _name = 'clinic.whatsapp.operator.assignment'
    _description = 'WhatsApp Operator Assignment'
    _rec_name = 'operator_id'
    _order = 'current_chats_count asc, operator_id'

    operator_id = fields.Many2one(
        'res.users',
        string='Operator',
        required=True,
        index=True,
        domain=[('share', '=', False)],  # Only internal users
        help='User assigned as WhatsApp operator'
    )

    max_concurrent_chats = fields.Integer(
        string='Max Concurrent Chats',
        default=10,
        help='Maximum number of simultaneous conversations this operator can handle'
    )

    available = fields.Boolean(
        string='Available',
        default=True,
        help='Is operator currently available to receive new chats?'
    )

    current_chats_count = fields.Integer(
        string='Active Chats',
        compute='_compute_current_chats_count',
        store=False,
        help='Number of currently active conversations'
    )

    capacity_percentage = fields.Float(
        string='Capacity %',
        compute='_compute_capacity_percentage',
        help='Percentage of capacity in use'
    )

    is_at_capacity = fields.Boolean(
        string='At Capacity',
        compute='_compute_is_at_capacity',
        help='True if operator has reached max concurrent chats'
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        help='Optional department for routing logic'
    )

    language_ids = fields.Many2many(
        'res.lang',
        string='Languages',
        help='Languages this operator can handle'
    )

    working_hours_start = fields.Float(
        string='Working Hours Start',
        default=8.0,
        help='Start of working hours (24h format, e.g. 8.5 = 8:30 AM)'
    )

    working_hours_end = fields.Float(
        string='Working Hours End',
        default=18.0,
        help='End of working hours (24h format, e.g. 18.0 = 6:00 PM)'
    )

    working_days = fields.Selection([
        ('weekdays', 'Monday - Friday'),
        ('all', 'All Days'),
        ('custom', 'Custom'),
    ], string='Working Days',
       default='weekdays',
       help='Days operator is available')

    custom_working_days = fields.Char(
        string='Custom Days',
        help='Comma-separated days (0=Monday, 6=Sunday). Example: 0,1,2,3,4,5'
    )

    # Statistics
    total_chats_handled = fields.Integer(
        string='Total Chats Handled',
        default=0,
        readonly=True,
        help='Lifetime count of conversations handled'
    )

    avg_response_time_minutes = fields.Float(
        string='Avg Response Time (min)',
        compute='_compute_avg_response_time',
        help='Average time to first response'
    )

    avg_resolution_time_hours = fields.Float(
        string='Avg Resolution Time (hrs)',
        compute='_compute_avg_resolution_time',
        help='Average time to resolve conversations'
    )

    escalation_rate = fields.Float(
        string='Escalation Rate %',
        compute='_compute_escalation_rate',
        help='Percentage of chats escalated'
    )

    # Activity tracking
    last_activity_at = fields.Datetime(
        string='Last Activity',
        help='Last time operator was active in WhatsApp'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    # SQL Constraints
    _sql_constraints = [
        ('operator_unique', 'UNIQUE(operator_id)',
         'Only one assignment record per operator!'),
        ('max_chats_positive', 'CHECK(max_concurrent_chats > 0)',
         'Max concurrent chats must be greater than 0'),
    ]

    @api.depends('operator_id')
    def _compute_current_chats_count(self):
        """Count active chats assigned to this operator"""
        for assignment in self:
            if assignment.operator_id:
                count = self.env['clinic.whatsapp.thread'].search_count([
                    ('assigned_operator_id', '=', assignment.operator_id.id),
                    ('escalation_status', 'in', ['pending', 'warning']),
                    ('active', '=', True),
                ])
                assignment.current_chats_count = count
            else:
                assignment.current_chats_count = 0

    @api.depends('current_chats_count', 'max_concurrent_chats')
    def _compute_capacity_percentage(self):
        """Calculate capacity utilization percentage"""
        for assignment in self:
            if assignment.max_concurrent_chats > 0:
                assignment.capacity_percentage = (
                    assignment.current_chats_count / assignment.max_concurrent_chats
                ) * 100
            else:
                assignment.capacity_percentage = 0.0

    @api.depends('current_chats_count', 'max_concurrent_chats', 'available')
    def _compute_is_at_capacity(self):
        """Check if operator is at maximum capacity"""
        for assignment in self:
            assignment.is_at_capacity = (
                assignment.current_chats_count >= assignment.max_concurrent_chats or
                not assignment.available
            )

    def _compute_avg_response_time(self):
        """Calculate average response time for this operator"""
        for assignment in self:
            if not assignment.operator_id:
                assignment.avg_response_time_minutes = 0.0
                continue

            # Get all threads assigned to this operator with responses
            threads = self.env['clinic.whatsapp.thread'].search([
                ('assigned_operator_id', '=', assignment.operator_id.id),
                ('last_inbound_at', '!=', False),
                ('last_operator_reply_at', '!=', False),
            ], limit=100)  # Last 100 conversations

            if not threads:
                assignment.avg_response_time_minutes = 0.0
                continue

            total_seconds = 0
            count = 0

            for thread in threads:
                if thread.last_operator_reply_at and thread.last_inbound_at:
                    delta = thread.last_operator_reply_at - thread.last_inbound_at
                    # Only count if operator replied AFTER customer message
                    if delta.total_seconds() > 0:
                        total_seconds += delta.total_seconds()
                        count += 1

            if count > 0:
                avg_seconds = total_seconds / count
                assignment.avg_response_time_minutes = avg_seconds / 60
            else:
                assignment.avg_response_time_minutes = 0.0

    def _compute_avg_resolution_time(self):
        """Calculate average time to resolve conversations"""
        for assignment in self:
            if not assignment.operator_id:
                assignment.avg_resolution_time_hours = 0.0
                continue

            # Get resolved threads
            threads = self.env['clinic.whatsapp.thread'].search([
                ('assigned_operator_id', '=', assignment.operator_id.id),
                ('escalation_status', '=', 'resolved'),
                ('first_message_at', '!=', False),
                ('last_operator_reply_at', '!=', False),
            ], limit=100)

            if not threads:
                assignment.avg_resolution_time_hours = 0.0
                continue

            total_seconds = 0
            for thread in threads:
                delta = thread.last_operator_reply_at - thread.first_message_at
                total_seconds += delta.total_seconds()

            avg_seconds = total_seconds / len(threads)
            assignment.avg_resolution_time_hours = avg_seconds / 3600

    def _compute_escalation_rate(self):
        """Calculate percentage of conversations escalated"""
        for assignment in self:
            if not assignment.operator_id:
                assignment.escalation_rate = 0.0
                continue

            total_threads = self.env['clinic.whatsapp.thread'].search_count([
                ('assigned_operator_id', '=', assignment.operator_id.id),
            ])

            if total_threads == 0:
                assignment.escalation_rate = 0.0
                continue

            escalated_threads = self.env['clinic.whatsapp.thread'].search_count([
                ('assigned_operator_id', '=', assignment.operator_id.id),
                ('escalation_status', '=', 'escalated'),
            ])

            assignment.escalation_rate = (escalated_threads / total_threads) * 100

    @api.constrains('max_concurrent_chats')
    def _check_max_chats(self):
        """Validate max_concurrent_chats is reasonable"""
        for assignment in self:
            if assignment.max_concurrent_chats < 1:
                raise ValidationError(_("Max concurrent chats must be at least 1"))
            if assignment.max_concurrent_chats > 50:
                raise ValidationError(
                    _("Max concurrent chats seems too high (>50). "
                      "Please verify this is correct.")
                )

    @api.constrains('working_hours_start', 'working_hours_end')
    def _check_working_hours(self):
        """Validate working hours are logical"""
        for assignment in self:
            if assignment.working_hours_start < 0 or assignment.working_hours_start >= 24:
                raise ValidationError(_("Working hours start must be between 0 and 24"))
            if assignment.working_hours_end <= assignment.working_hours_start:
                raise ValidationError(_("Working hours end must be after start"))
            if assignment.working_hours_end > 24:
                raise ValidationError(_("Working hours end cannot exceed 24"))

    def action_toggle_availability(self):
        """Toggle operator availability"""
        self.ensure_one()
        self.available = not self.available

        status = 'available' if self.available else 'unavailable'
        _logger.info(f"Operator {self.operator_id.name} marked as {status}")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Availability Updated'),
                'message': _('You are now %s for WhatsApp conversations') % status,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_active_chats(self):
        """Open list of active chats for this operator"""
        self.ensure_one()

        return {
            'name': _('Active WhatsApp Chats'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.whatsapp.thread',
            'view_mode': 'tree,form',
            'domain': [
                ('assigned_operator_id', '=', self.operator_id.id),
                ('escalation_status', 'in', ['pending', 'warning']),
                ('active', '=', True),
            ],
            'context': {
                'search_default_group_by_escalation': 1,
            }
        }

    def action_view_statistics(self):
        """Show detailed statistics for this operator"""
        self.ensure_one()

        return {
            'name': _('Operator Statistics: %s') % self.operator_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.whatsapp.operator.assignment',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def get_next_available_operator(self, language_code=None, department_id=None):
        """
        Get next available operator for assignment

        Uses round-robin based on current load

        Args:
            language_code (str): Optional language requirement
            department_id (int): Optional department requirement

        Returns:
            res.users: Operator user or False
        """
        domain = [
            ('available', '=', True),
            ('active', '=', True),
            ('is_at_capacity', '=', False),
        ]

        if department_id:
            domain.append(('department_id', '=', department_id))

        # TODO: Add language filtering when needed
        # if language_code:
        #     domain.append(('language_ids.code', '=', language_code))

        # Get available operators sorted by load (ascending)
        assignments = self.search(domain, order='current_chats_count asc', limit=1)

        if assignments:
            _logger.info(
                f"Assigned operator {assignments[0].operator_id.name} "
                f"({assignments[0].current_chats_count}/{assignments[0].max_concurrent_chats} chats)"
            )
            return assignments[0].operator_id

        # No available operators
        _logger.warning("No available WhatsApp operators found")
        return False

    @api.model
    def update_operator_activity(self, operator_id):
        """
        Update last activity timestamp for operator

        Called when operator sends a message or performs action

        Args:
            operator_id (int): Operator user ID
        """
        assignment = self.search([('operator_id', '=', operator_id)], limit=1)

        if assignment:
            assignment.write({'last_activity_at': fields.Datetime.now()})

    @api.model
    def increment_chat_counter(self, operator_id):
        """
        Increment total chats handled counter

        Args:
            operator_id (int): Operator user ID
        """
        assignment = self.search([('operator_id', '=', operator_id)], limit=1)

        if assignment:
            assignment.write({
                'total_chats_handled': assignment.total_chats_handled + 1
            })
