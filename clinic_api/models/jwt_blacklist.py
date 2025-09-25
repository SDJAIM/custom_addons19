# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from datetime import datetime

class JWTBlacklist(models.Model):
    _name = 'clinic.api.jwt_blacklist'
    _description = 'JWT Blacklist for Replay Attack Prevention'
    _rec_name = 'jti'

    jti = fields.Char(
        string='JWT ID',
        required=True,
        index=True,
        help='Unique JWT identifier to prevent replay attacks'
    )

    api_key_id = fields.Many2one(
        'clinic.api.key',
        string='API Key',
        required=True,
        ondelete='cascade',
        index=True
    )

    expiry = fields.Datetime(
        string='Expiry',
        required=True,
        index=True,
        help='When this JWT expires and can be removed'
    )

    created_at = fields.Datetime(
        string='Created At',
        default=fields.Datetime.now,
        readonly=True
    )

    _sql_constraints = [
        ('jti_unique', 'UNIQUE(jti)', 'JWT ID must be unique!'),
    ]

    @api.model
    def cleanup_expired(self):
        """Remove expired blacklist entries - called by cron job"""
        expired = self.search([
            ('expiry', '<', fields.Datetime.now())
        ])
        count = len(expired)
        expired.unlink()
        return {
            'cleaned': count,
            'message': f'Cleaned {count} expired JWT blacklist entries'
        }