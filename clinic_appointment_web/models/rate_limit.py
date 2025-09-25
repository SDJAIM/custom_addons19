# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta


class ClinicRateLimit(models.Model):
    """Model to store rate limit attempts for security"""
    _name = 'clinic.rate_limit'
    _description = 'Rate Limit Tracking'
    _rec_name = 'client_id'
    _order = 'timestamp desc'

    client_id = fields.Char(
        string='Client ID',
        required=True,
        index=True,
        help='Hashed client identifier'
    )

    resource = fields.Char(
        string='Resource',
        required=True,
        index=True,
        help='Resource being rate limited'
    )

    timestamp = fields.Datetime(
        string='Timestamp',
        required=True,
        index=True,
        default=fields.Datetime.now
    )

    ip_address = fields.Char(
        string='IP Address',
        help='Client IP for security monitoring'
    )

    user_agent = fields.Text(
        string='User Agent',
        help='Browser user agent string'
    )

    blocked = fields.Boolean(
        string='Blocked',
        default=False,
        help='Client was blocked due to rate limiting'
    )

    # Auto-cleanup old records
    @api.model
    def _gc_rate_limits(self):
        """Garbage collect old rate limit records - called by cron"""
        # Keep records for 24 hours for security analysis
        cutoff = datetime.now() - timedelta(hours=24)
        old_records = self.search([('timestamp', '<', cutoff)])

        # Log before deletion for audit
        if old_records:
            _logger.info(f"Cleaning {len(old_records)} old rate limit records")

        old_records.unlink()
        return True

    @api.model
    def check_and_update_rate_limit(self, client_id, resource, max_attempts=5, window_minutes=60):
        """
        Check if rate limit is exceeded and update records

        :return: dict with 'allowed', 'remaining', 'reset_time'
        """
        cutoff_time = fields.Datetime.now() - timedelta(minutes=window_minutes)

        # Count recent attempts
        recent_attempts = self.search_count([
            ('client_id', '=', client_id),
            ('resource', '=', resource),
            ('timestamp', '>', cutoff_time),
            ('blocked', '=', False)
        ])

        # Check if already blocked
        blocked_record = self.search([
            ('client_id', '=', client_id),
            ('resource', '=', resource),
            ('blocked', '=', True),
            ('timestamp', '>', cutoff_time)
        ], limit=1)

        if blocked_record:
            reset_time = blocked_record.timestamp + timedelta(minutes=window_minutes)
            return {
                'allowed': False,
                'remaining': 0,
                'reset_time': reset_time,
                'reason': 'blocked'
            }

        # Check if limit would be exceeded
        if recent_attempts >= max_attempts:
            # Create blocked record
            self.create({
                'client_id': client_id,
                'resource': resource,
                'timestamp': fields.Datetime.now(),
                'blocked': True
            })
            reset_time = fields.Datetime.now() + timedelta(minutes=window_minutes)
            return {
                'allowed': False,
                'remaining': 0,
                'reset_time': reset_time,
                'reason': 'limit_exceeded'
            }

        # Allow and record attempt
        self.create({
            'client_id': client_id,
            'resource': resource,
            'timestamp': fields.Datetime.now(),
            'blocked': False
        })

        remaining = max_attempts - recent_attempts - 1
        return {
            'allowed': True,
            'remaining': remaining,
            'reset_time': None,
            'reason': 'ok'
        }

    @api.model
    def get_suspicious_clients(self, hours=24, threshold=100):
        """Get clients with suspicious activity patterns"""
        cutoff = fields.Datetime.now() - timedelta(hours=hours)

        query = """
            SELECT client_id, COUNT(*) as attempts, COUNT(DISTINCT resource) as resources
            FROM clinic_rate_limit
            WHERE timestamp > %s
            GROUP BY client_id
            HAVING COUNT(*) > %s
            ORDER BY attempts DESC
        """

        self.env.cr.execute(query, (cutoff, threshold))
        return self.env.cr.fetchall()