# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta
import logging
import requests

_logger = logging.getLogger(__name__)


class GoogleMeetConfig(models.Model):
    """
    TASK-F3-002: Google Meet Configuration per Staff Member

    Stores OAuth2 tokens for each staff member to enable Google Calendar
    API integration for creating Google Meet links automatically.
    """
    _name = 'clinic.google.meet.config'
    _description = 'Google Meet Configuration'
    _rec_name = 'staff_id'

    # ========================
    # Fields
    # ========================
    staff_id = fields.Many2one(
        'clinic.staff',
        string='Staff Member',
        required=True,
        ondelete='cascade',
        index=True,
        help='Staff member whose Google account is connected'
    )

    user_id = fields.Many2one(
        'res.users',
        string='User',
        related='staff_id.user_id',
        readonly=True,
        store=True
    )

    google_calendar_id = fields.Char(
        string='Calendar ID',
        default='primary',
        required=True,
        help='Google Calendar ID (usually "primary" for main calendar)'
    )

    # OAuth2 Tokens (encrypted in production)
    access_token = fields.Char(
        string='Access Token',
        copy=False,
        groups='base.group_system',
        help='OAuth2 access token for Google API'
    )

    refresh_token = fields.Char(
        string='Refresh Token',
        copy=False,
        groups='base.group_system',
        help='OAuth2 refresh token for obtaining new access tokens'
    )

    token_expiry = fields.Datetime(
        string='Token Expires At',
        help='When the access token expires'
    )

    # Status
    is_connected = fields.Boolean(
        string='Connected',
        compute='_compute_is_connected',
        store=True,
        help='Is Google account currently connected?'
    )

    last_sync_date = fields.Datetime(
        string='Last Sync',
        readonly=True,
        help='Last time the connection was tested'
    )

    google_email = fields.Char(
        string='Google Email',
        help='Connected Google account email'
    )

    # ========================
    # Computed Fields
    # ========================
    @api.depends('access_token', 'refresh_token')
    def _compute_is_connected(self):
        """Check if Google account is connected"""
        for config in self:
            config.is_connected = bool(config.access_token and config.refresh_token)

    # ========================
    # Constraints
    # ========================
    _sql_constraints = [
        ('staff_unique', 'UNIQUE(staff_id)',
         'Each staff member can only have one Google Meet configuration!'),
    ]

    # ========================
    # API Methods
    # ========================
    def _get_google_credentials(self):
        """
        Get valid OAuth2 credentials for Google API

        Returns:
            dict: Credentials dictionary with token, refresh_token, etc.
        """
        self.ensure_one()

        if not self.access_token or not self.refresh_token:
            raise UserError(_(
                'Google account not connected for %s.\n\n'
                'Please connect your Google account first.'
            ) % self.staff_id.name)

        # Check if token is expired and refresh if needed
        if self.token_expiry and self.token_expiry < fields.Datetime.now():
            _logger.info(f"Access token expired for {self.staff_id.name}, refreshing...")
            self._refresh_access_token()

        return {
            'token': self.access_token,
            'refresh_token': self.refresh_token,
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': self.env['ir.config_parameter'].sudo().get_param('google_meet.client_id'),
            'client_secret': self.env['ir.config_parameter'].sudo().get_param('google_meet.client_secret'),
            'scopes': ['https://www.googleapis.com/auth/calendar.events'],
        }

    def _refresh_access_token(self):
        """
        Refresh expired OAuth2 access token using refresh token
        """
        self.ensure_one()

        if not self.refresh_token:
            raise UserError(_('No refresh token available. Please reconnect your Google account.'))

        client_id = self.env['ir.config_parameter'].sudo().get_param('google_meet.client_id')
        client_secret = self.env['ir.config_parameter'].sudo().get_param('google_meet.client_secret')

        if not client_id or not client_secret:
            raise UserError(_(
                'Google Meet API credentials not configured.\n\n'
                'Please configure:\n'
                '- google_meet.client_id\n'
                '- google_meet.client_secret\n\n'
                'in System Parameters.'
            ))

        try:
            response = requests.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'refresh_token': self.refresh_token,
                    'grant_type': 'refresh_token',
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.write({
                    'access_token': data['access_token'],
                    'token_expiry': fields.Datetime.now() + timedelta(seconds=data.get('expires_in', 3600)),
                    'last_sync_date': fields.Datetime.now(),
                })
                _logger.info(f"Successfully refreshed access token for {self.staff_id.name}")
            else:
                error_msg = response.json().get('error_description', response.text)
                _logger.error(f"Failed to refresh Google token: {error_msg}")
                raise UserError(_(
                    'Failed to refresh Google access token.\n\n'
                    'Error: %s\n\n'
                    'You may need to reconnect your Google account.'
                ) % error_msg)

        except requests.exceptions.RequestException as e:
            _logger.error(f"Network error refreshing token: {str(e)}")
            raise UserError(_(
                'Network error while refreshing Google token.\n\n'
                'Error: %s'
            ) % str(e))

    def action_test_connection(self):
        """Test Google Calendar API connection"""
        self.ensure_one()

        try:
            creds = self._get_google_credentials()
            headers = {'Authorization': f"Bearer {creds['token']}"}

            # Simple API call to test connection
            response = requests.get(
                f"https://www.googleapis.com/calendar/v3/calendars/{self.google_calendar_id}",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                calendar_data = response.json()
                self.write({
                    'last_sync_date': fields.Datetime.now(),
                    'google_email': calendar_data.get('id'),
                })

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _('Successfully connected to Google Calendar:\n%s') % calendar_data.get('summary', 'Calendar'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_('Connection test failed: %s') % response.text)

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': _('Error: %s') % str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_disconnect(self):
        """Disconnect Google account"""
        self.ensure_one()

        # Revoke token at Google
        if self.access_token:
            try:
                requests.post(
                    f"https://oauth2.googleapis.com/revoke?token={self.access_token}",
                    timeout=5
                )
            except:
                pass  # Don't fail if revocation fails

        self.write({
            'access_token': False,
            'refresh_token': False,
            'token_expiry': False,
            'google_email': False,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Disconnected'),
                'message': _('Google account has been disconnected'),
                'type': 'info',
            }
        }
