# -*- coding: utf-8 -*-

from odoo import http, fields, _
from odoo.http import request
from datetime import timedelta
import logging
import requests

_logger = logging.getLogger(__name__)


class GoogleOAuthController(http.Controller):
    """
    TASK-F3-002: Handle Google OAuth2 authentication flow
    """

    @http.route('/google/auth/start', type='http', auth='user', website=True)
    def google_auth_start(self, **kwargs):
        """
        Initiate Google OAuth2 flow - redirect to Google consent screen
        """
        client_id = request.env['ir.config_parameter'].sudo().get_param('google_meet.client_id')

        if not client_id:
            return request.render('clinic_integrations_telemed.google_auth_error', {
                'error': _('Google Meet is not configured. Please contact your administrator.'),
                'error_detail': _('Missing google_meet.client_id in System Parameters.')
            })

        # Build redirect URI
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        redirect_uri = f"{base_url}/google/auth/callback"

        # Build authorization URL
        auth_params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'https://www.googleapis.com/auth/calendar.events',
            'access_type': 'offline',
            'prompt': 'consent',  # Force consent to get refresh token
            'state': str(request.session.sid),  # CSRF protection
        }

        auth_url = 'https://accounts.google.com/o/oauth2/v2/auth?' + '&'.join(
            f"{k}={v}" for k, v in auth_params.items()
        )

        _logger.info(f"Redirecting user {request.env.user.name} to Google OAuth")
        return request.redirect(auth_url)

    @http.route('/google/auth/callback', type='http', auth='user', website=True, csrf=False)
    def google_auth_callback(self, code=None, error=None, state=None, **kwargs):
        """
        Handle OAuth callback - exchange authorization code for tokens
        """
        if error:
            _logger.error(f"Google OAuth error: {error}")
            return request.render('clinic_integrations_telemed.google_auth_error', {
                'error': _('Google authorization failed'),
                'error_detail': error
            })

        if not code:
            return request.render('clinic_integrations_telemed.google_auth_error', {
                'error': _('No authorization code received'),
                'error_detail': _('The authorization process was interrupted.')
            })

        # Verify state for CSRF protection
        # Note: In production, implement proper state verification

        # Get configuration
        client_id = request.env['ir.config_parameter'].sudo().get_param('google_meet.client_id')
        client_secret = request.env['ir.config_parameter'].sudo().get_param('google_meet.client_secret')

        if not client_id or not client_secret:
            return request.render('clinic_integrations_telemed.google_auth_error', {
                'error': _('Google Meet is not properly configured'),
                'error_detail': _('Missing API credentials in System Parameters.')
            })

        # Build redirect URI
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        redirect_uri = f"{base_url}/google/auth/callback"

        # Exchange code for tokens
        try:
            response = requests.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'code': code,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': redirect_uri,
                    'grant_type': 'authorization_code',
                },
                timeout=10
            )

            if response.status_code != 200:
                error_data = response.json()
                _logger.error(f"Token exchange failed: {error_data}")
                return request.render('clinic_integrations_telemed.google_auth_error', {
                    'error': _('Failed to exchange authorization code'),
                    'error_detail': error_data.get('error_description', response.text)
                })

            tokens = response.json()

            # Get current staff member
            staff = request.env['clinic.staff'].sudo().search([
                ('user_id', '=', request.env.uid)
            ], limit=1)

            if not staff:
                return request.render('clinic_integrations_telemed.google_auth_error', {
                    'error': _('No staff record found'),
                    'error_detail': _('Your user account is not linked to a staff member. Please contact your administrator.')
                })

            # Get user's email for display
            user_info_response = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f"Bearer {tokens['access_token']}"},
                timeout=10
            )
            google_email = None
            if user_info_response.status_code == 200:
                google_email = user_info_response.json().get('email')

            # Save or update Google Meet config
            google_config = request.env['clinic.google.meet.config'].sudo().search([
                ('staff_id', '=', staff.id)
            ], limit=1)

            config_vals = {
                'access_token': tokens['access_token'],
                'refresh_token': tokens.get('refresh_token'),
                'token_expiry': fields.Datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600)),
                'last_sync_date': fields.Datetime.now(),
                'google_email': google_email,
            }

            if google_config:
                google_config.write(config_vals)
                _logger.info(f"Updated Google Meet config for {staff.name}")
            else:
                config_vals['staff_id'] = staff.id
                google_config = request.env['clinic.google.meet.config'].sudo().create(config_vals)
                _logger.info(f"Created Google Meet config for {staff.name}")

            return request.render('clinic_integrations_telemed.google_auth_success', {
                'staff': staff,
                'google_email': google_email,
            })

        except requests.exceptions.RequestException as e:
            _logger.error(f"Network error during OAuth: {str(e)}")
            return request.render('clinic_integrations_telemed.google_auth_error', {
                'error': _('Network error'),
                'error_detail': str(e)
            })
        except Exception as e:
            _logger.error(f"Unexpected error during OAuth: {str(e)}", exc_info=True)
            return request.render('clinic_integrations_telemed.google_auth_error', {
                'error': _('Unexpected error'),
                'error_detail': str(e)
            })
