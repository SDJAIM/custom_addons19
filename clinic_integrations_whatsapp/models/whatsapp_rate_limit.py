# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class WhatsAppRateLimit(models.Model):
    _name = 'clinic.whatsapp.rate_limit'
    _description = 'WhatsApp Rate Limiting'
    _rec_name = 'patient_id'

    # Identification
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        index=True,
        ondelete='cascade'
    )

    phone_number = fields.Char(
        string='Phone Number',
        index=True
    )

    identifier_type = fields.Selection([
        ('patient', 'Patient'),
        ('phone', 'Phone Number'),
        ('global', 'Global'),
    ], string='Identifier Type', required=True, default='patient')

    # Rate Limit Tracking
    messages_sent_today = fields.Integer(
        string='Messages Sent Today',
        default=0
    )

    messages_sent_hour = fields.Integer(
        string='Messages Sent This Hour',
        default=0
    )

    messages_sent_minute = fields.Integer(
        string='Messages Sent This Minute',
        default=0
    )

    last_message_date = fields.Datetime(
        string='Last Message Date'
    )

    last_reset_date = fields.Date(
        string='Last Reset Date',
        default=fields.Date.today
    )

    last_hour_reset = fields.Datetime(
        string='Last Hour Reset'
    )

    last_minute_reset = fields.Datetime(
        string='Last Minute Reset'
    )

    # Rate Limit Configuration
    daily_limit = fields.Integer(
        string='Daily Limit',
        default=100,
        help='Maximum messages per day'
    )

    hourly_limit = fields.Integer(
        string='Hourly Limit',
        default=20,
        help='Maximum messages per hour'
    )

    minute_limit = fields.Integer(
        string='Minute Limit',
        default=5,
        help='Maximum messages per minute'
    )

    # Blocking
    is_blocked = fields.Boolean(
        string='Is Blocked',
        default=False,
        help='Temporarily blocked due to rate limit violations'
    )

    blocked_until = fields.Datetime(
        string='Blocked Until'
    )

    block_count = fields.Integer(
        string='Block Count',
        default=0,
        help='Number of times this identifier has been blocked'
    )

    # Company support
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        index=True
    )

    @api.model
    def check_rate_limit(self, patient_id=None, phone_number=None, raise_error=True):
        """
        Check if sending a message would exceed rate limits.

        Args:
            patient_id: ID of the patient
            phone_number: Phone number to check
            raise_error: If True, raise an error when limit exceeded

        Returns:
            dict: {
                'allowed': bool,
                'reason': str,
                'wait_time': int (seconds to wait),
                'limits': dict of current limits
            }
        """
        now = fields.Datetime.now()
        today = fields.Date.today()

        # Find or create rate limit record
        domain = [('company_id', '=', self.env.company.id)]
        if patient_id:
            domain.extend([
                ('identifier_type', '=', 'patient'),
                ('patient_id', '=', patient_id)
            ])
        elif phone_number:
            domain.extend([
                ('identifier_type', '=', 'phone'),
                ('phone_number', '=', phone_number)
            ])
        else:
            domain.extend([
                ('identifier_type', '=', 'global')
            ])

        rate_limit = self.search(domain, limit=1)

        if not rate_limit:
            # Create new rate limit record
            vals = {
                'company_id': self.env.company.id,
                'identifier_type': 'patient' if patient_id else 'phone' if phone_number else 'global'
            }
            if patient_id:
                vals['patient_id'] = patient_id
            if phone_number:
                vals['phone_number'] = phone_number

            # Get limits from configuration
            config_helper = self.env['clinic.whatsapp.config.helper']
            vals['daily_limit'] = int(config_helper.get_config_value('daily_message_limit', '100'))
            vals['hourly_limit'] = int(config_helper.get_config_value('hourly_message_limit', '20'))
            vals['minute_limit'] = int(config_helper.get_config_value('minute_message_limit', '5'))

            rate_limit = self.create(vals)

        # Check if blocked
        if rate_limit.is_blocked and rate_limit.blocked_until:
            if now < rate_limit.blocked_until:
                wait_time = int((rate_limit.blocked_until - now).total_seconds())
                if raise_error:
                    raise ValidationError(
                        _("Rate limit exceeded. Please wait %d seconds before sending another message.") % wait_time
                    )
                return {
                    'allowed': False,
                    'reason': 'blocked',
                    'wait_time': wait_time,
                    'limits': self._get_current_limits(rate_limit)
                }
            else:
                # Unblock
                rate_limit.is_blocked = False
                rate_limit.blocked_until = False

        # Reset counters if needed
        rate_limit._reset_counters_if_needed(now, today)

        # Check minute limit
        if rate_limit.messages_sent_minute >= rate_limit.minute_limit:
            wait_time = 60
            if raise_error:
                raise ValidationError(
                    _("Minute rate limit reached (%d/%d). Please wait %d seconds.") %
                    (rate_limit.messages_sent_minute, rate_limit.minute_limit, wait_time)
                )
            return {
                'allowed': False,
                'reason': 'minute_limit',
                'wait_time': wait_time,
                'limits': self._get_current_limits(rate_limit)
            }

        # Check hourly limit
        if rate_limit.messages_sent_hour >= rate_limit.hourly_limit:
            if rate_limit.last_hour_reset:
                wait_time = int((rate_limit.last_hour_reset + timedelta(hours=1) - now).total_seconds())
            else:
                wait_time = 3600
            if raise_error:
                raise ValidationError(
                    _("Hourly rate limit reached (%d/%d). Please wait %d minutes.") %
                    (rate_limit.messages_sent_hour, rate_limit.hourly_limit, wait_time // 60)
                )
            return {
                'allowed': False,
                'reason': 'hourly_limit',
                'wait_time': wait_time,
                'limits': self._get_current_limits(rate_limit)
            }

        # Check daily limit
        if rate_limit.messages_sent_today >= rate_limit.daily_limit:
            tomorrow = datetime.combine(today + timedelta(days=1), datetime.min.time())
            wait_time = int((tomorrow - now).total_seconds())
            if raise_error:
                raise ValidationError(
                    _("Daily rate limit reached (%d/%d). Please try again tomorrow.") %
                    (rate_limit.messages_sent_today, rate_limit.daily_limit)
                )
            return {
                'allowed': False,
                'reason': 'daily_limit',
                'wait_time': wait_time,
                'limits': self._get_current_limits(rate_limit)
            }

        return {
            'allowed': True,
            'reason': 'ok',
            'wait_time': 0,
            'limits': self._get_current_limits(rate_limit)
        }

    def _reset_counters_if_needed(self, now, today):
        """Reset counters based on time periods"""
        self.ensure_one()

        # Reset daily counter
        if self.last_reset_date != today:
            self.messages_sent_today = 0
            self.last_reset_date = today

        # Reset hourly counter
        if not self.last_hour_reset or (now - self.last_hour_reset).total_seconds() >= 3600:
            self.messages_sent_hour = 0
            self.last_hour_reset = now

        # Reset minute counter
        if not self.last_minute_reset or (now - self.last_minute_reset).total_seconds() >= 60:
            self.messages_sent_minute = 0
            self.last_minute_reset = now

    def _get_current_limits(self, rate_limit):
        """Get current limit status"""
        return {
            'daily': {
                'used': rate_limit.messages_sent_today,
                'limit': rate_limit.daily_limit,
                'remaining': rate_limit.daily_limit - rate_limit.messages_sent_today
            },
            'hourly': {
                'used': rate_limit.messages_sent_hour,
                'limit': rate_limit.hourly_limit,
                'remaining': rate_limit.hourly_limit - rate_limit.messages_sent_hour
            },
            'minute': {
                'used': rate_limit.messages_sent_minute,
                'limit': rate_limit.minute_limit,
                'remaining': rate_limit.minute_limit - rate_limit.messages_sent_minute
            }
        }

    @api.model
    def increment_counter(self, patient_id=None, phone_number=None):
        """Increment message counter after successful send"""
        domain = [('company_id', '=', self.env.company.id)]
        if patient_id:
            domain.extend([
                ('identifier_type', '=', 'patient'),
                ('patient_id', '=', patient_id)
            ])
        elif phone_number:
            domain.extend([
                ('identifier_type', '=', 'phone'),
                ('phone_number', '=', phone_number)
            ])
        else:
            domain.extend([
                ('identifier_type', '=', 'global')
            ])

        rate_limit = self.search(domain, limit=1)
        if rate_limit:
            rate_limit.write({
                'messages_sent_today': rate_limit.messages_sent_today + 1,
                'messages_sent_hour': rate_limit.messages_sent_hour + 1,
                'messages_sent_minute': rate_limit.messages_sent_minute + 1,
                'last_message_date': fields.Datetime.now()
            })

    @api.model
    def cleanup_old_records(self, days=30):
        """Clean up old rate limit records"""
        cutoff_date = fields.Date.today() - timedelta(days=days)
        old_records = self.search([
            ('last_message_date', '<', cutoff_date),
            ('is_blocked', '=', False)
        ])
        count = len(old_records)
        old_records.unlink()
        _logger.info(f"Cleaned up {count} old rate limit records")
        return count