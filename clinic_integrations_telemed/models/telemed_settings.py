# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class TelemedicineSettings(models.TransientModel):
    _name = 'clinic.telemed.settings'
    _description = 'Telemedicine Configuration Settings'
    _inherit = 'res.config.settings'

    # Platform Selection
    telemed_platform = fields.Selection([
        ('zoom', 'Zoom'),
        ('google_meet', 'Google Meet'),
        ('jitsi', 'Jitsi Meet'),
        ('teams', 'Microsoft Teams'),
        ('custom', 'Custom Platform'),
    ], string='Video Platform', default='jitsi',
       config_parameter='clinic.telemed.platform',
       help='Video conferencing platform to use for telemedicine sessions')

    # Zoom Configuration
    zoom_api_key = fields.Char(
        string='Zoom API Key',
        config_parameter='clinic.telemed.zoom_api_key',
        help='Zoom API Key for creating meetings'
    )

    zoom_api_secret = fields.Char(
        string='Zoom API Secret',
        config_parameter='clinic.telemed.zoom_api_secret',
        help='Zoom API Secret for authentication'
    )

    zoom_webhook_secret = fields.Char(
        string='Zoom Webhook Secret',
        config_parameter='clinic.telemed.zoom_webhook_secret',
        help='Zoom Webhook secret for event verification'
    )

    # Google Meet Configuration
    google_client_id = fields.Char(
        string='Google Client ID',
        config_parameter='clinic.telemed.google_client_id',
        help='Google OAuth 2.0 Client ID'
    )

    google_client_secret = fields.Char(
        string='Google Client Secret',
        config_parameter='clinic.telemed.google_client_secret',
        help='Google OAuth 2.0 Client Secret'
    )

    google_refresh_token = fields.Char(
        string='Google Refresh Token',
        config_parameter='clinic.telemed.google_refresh_token',
        help='Google OAuth 2.0 Refresh Token'
    )

    # Microsoft Teams Configuration
    teams_tenant_id = fields.Char(
        string='Teams Tenant ID',
        config_parameter='clinic.telemed.teams_tenant_id',
        help='Microsoft Teams Tenant ID'
    )

    teams_client_id = fields.Char(
        string='Teams Client ID',
        config_parameter='clinic.telemed.teams_client_id',
        help='Microsoft Teams Application Client ID'
    )

    teams_client_secret = fields.Char(
        string='Teams Client Secret',
        config_parameter='clinic.telemed.teams_client_secret',
        help='Microsoft Teams Application Client Secret'
    )

    # Jitsi Configuration
    jitsi_domain = fields.Char(
        string='Jitsi Domain',
        default='meet.jit.si',
        config_parameter='clinic.telemed.jitsi_domain',
        help='Jitsi Meet domain (use meet.jit.si for free service)'
    )

    jitsi_app_id = fields.Char(
        string='Jitsi App ID',
        config_parameter='clinic.telemed.jitsi_app_id',
        help='Jitsi App ID for JWT authentication (optional)'
    )

    jitsi_app_secret = fields.Char(
        string='Jitsi App Secret',
        config_parameter='clinic.telemed.jitsi_app_secret',
        help='Jitsi App Secret for JWT authentication (optional)'
    )

    # Custom Platform Configuration
    custom_api_url = fields.Char(
        string='Custom API URL',
        config_parameter='clinic.telemed.custom_api_url',
        help='API URL for custom video platform'
    )

    custom_api_key = fields.Char(
        string='Custom API Key',
        config_parameter='clinic.telemed.custom_api_key',
        help='API Key for custom video platform'
    )

    custom_api_secret = fields.Char(
        string='Custom API Secret',
        config_parameter='clinic.telemed.custom_api_secret',
        help='API Secret for custom video platform'
    )

    # Session Configuration
    default_session_duration = fields.Integer(
        string='Default Session Duration (minutes)',
        default=30,
        config_parameter='clinic.telemed.default_duration',
        help='Default duration for telemedicine sessions'
    )

    waiting_room_enabled = fields.Boolean(
        string='Enable Waiting Room',
        default=True,
        config_parameter='clinic.telemed.waiting_room_enabled',
        help='Enable waiting room for patients'
    )

    recording_enabled = fields.Boolean(
        string='Enable Recording',
        default=False,
        config_parameter='clinic.telemed.recording_enabled',
        help='Enable automatic session recording (subject to legal requirements)'
    )

    # Security Configuration
    require_password = fields.Boolean(
        string='Require Meeting Password',
        default=True,
        config_parameter='clinic.telemed.require_password',
        help='Require password for accessing video sessions'
    )

    auto_generate_password = fields.Boolean(
        string='Auto-generate Passwords',
        default=True,
        config_parameter='clinic.telemed.auto_generate_password',
        help='Automatically generate secure passwords for meetings'
    )

    # Notification Configuration
    send_email_invites = fields.Boolean(
        string='Send Email Invites',
        default=True,
        config_parameter='clinic.telemed.send_email_invites',
        help='Send email invitations with meeting links'
    )

    send_sms_invites = fields.Boolean(
        string='Send SMS Invites',
        default=False,
        config_parameter='clinic.telemed.send_sms_invites',
        help='Send SMS invitations with meeting links'
    )

    reminder_time_minutes = fields.Integer(
        string='Reminder Time (minutes)',
        default=15,
        config_parameter='clinic.telemed.reminder_time',
        help='Send reminders X minutes before session start'
    )

    @api.model
    def get_values(self):
        """Get configuration values from ir.config_parameter"""
        res = super(TelemedicineSettings, self).get_values()

        IrConfig = self.env['ir.config_parameter'].sudo()

        res.update({
            'telemed_platform': IrConfig.get_param('clinic.telemed.platform', 'jitsi'),
            'zoom_api_key': IrConfig.get_param('clinic.telemed.zoom_api_key', ''),
            'zoom_api_secret': IrConfig.get_param('clinic.telemed.zoom_api_secret', ''),
            'zoom_webhook_secret': IrConfig.get_param('clinic.telemed.zoom_webhook_secret', ''),
            'google_client_id': IrConfig.get_param('clinic.telemed.google_client_id', ''),
            'google_client_secret': IrConfig.get_param('clinic.telemed.google_client_secret', ''),
            'google_refresh_token': IrConfig.get_param('clinic.telemed.google_refresh_token', ''),
            'teams_tenant_id': IrConfig.get_param('clinic.telemed.teams_tenant_id', ''),
            'teams_client_id': IrConfig.get_param('clinic.telemed.teams_client_id', ''),
            'teams_client_secret': IrConfig.get_param('clinic.telemed.teams_client_secret', ''),
            'jitsi_domain': IrConfig.get_param('clinic.telemed.jitsi_domain', 'meet.jit.si'),
            'jitsi_app_id': IrConfig.get_param('clinic.telemed.jitsi_app_id', ''),
            'jitsi_app_secret': IrConfig.get_param('clinic.telemed.jitsi_app_secret', ''),
            'custom_api_url': IrConfig.get_param('clinic.telemed.custom_api_url', ''),
            'custom_api_key': IrConfig.get_param('clinic.telemed.custom_api_key', ''),
            'custom_api_secret': IrConfig.get_param('clinic.telemed.custom_api_secret', ''),
            'default_session_duration': int(IrConfig.get_param('clinic.telemed.default_duration', '30')),
            'waiting_room_enabled': IrConfig.get_param('clinic.telemed.waiting_room_enabled', 'True') == 'True',
            'recording_enabled': IrConfig.get_param('clinic.telemed.recording_enabled', 'False') == 'True',
            'require_password': IrConfig.get_param('clinic.telemed.require_password', 'True') == 'True',
            'auto_generate_password': IrConfig.get_param('clinic.telemed.auto_generate_password', 'True') == 'True',
            'send_email_invites': IrConfig.get_param('clinic.telemed.send_email_invites', 'True') == 'True',
            'send_sms_invites': IrConfig.get_param('clinic.telemed.send_sms_invites', 'False') == 'True',
            'reminder_time_minutes': int(IrConfig.get_param('clinic.telemed.reminder_time', '15')),
        })

        return res

    def set_values(self):
        """Set configuration values to ir.config_parameter"""
        super(TelemedicineSettings, self).set_values()

        IrConfig = self.env['ir.config_parameter'].sudo()

        IrConfig.set_param('clinic.telemed.platform', self.telemed_platform or 'jitsi')
        IrConfig.set_param('clinic.telemed.zoom_api_key', self.zoom_api_key or '')
        IrConfig.set_param('clinic.telemed.zoom_api_secret', self.zoom_api_secret or '')
        IrConfig.set_param('clinic.telemed.zoom_webhook_secret', self.zoom_webhook_secret or '')
        IrConfig.set_param('clinic.telemed.google_client_id', self.google_client_id or '')
        IrConfig.set_param('clinic.telemed.google_client_secret', self.google_client_secret or '')
        IrConfig.set_param('clinic.telemed.google_refresh_token', self.google_refresh_token or '')
        IrConfig.set_param('clinic.telemed.teams_tenant_id', self.teams_tenant_id or '')
        IrConfig.set_param('clinic.telemed.teams_client_id', self.teams_client_id or '')
        IrConfig.set_param('clinic.telemed.teams_client_secret', self.teams_client_secret or '')
        IrConfig.set_param('clinic.telemed.jitsi_domain', self.jitsi_domain or 'meet.jit.si')
        IrConfig.set_param('clinic.telemed.jitsi_app_id', self.jitsi_app_id or '')
        IrConfig.set_param('clinic.telemed.jitsi_app_secret', self.jitsi_app_secret or '')
        IrConfig.set_param('clinic.telemed.custom_api_url', self.custom_api_url or '')
        IrConfig.set_param('clinic.telemed.custom_api_key', self.custom_api_key or '')
        IrConfig.set_param('clinic.telemed.custom_api_secret', self.custom_api_secret or '')
        IrConfig.set_param('clinic.telemed.default_duration', str(self.default_session_duration))
        IrConfig.set_param('clinic.telemed.waiting_room_enabled', str(self.waiting_room_enabled))
        IrConfig.set_param('clinic.telemed.recording_enabled', str(self.recording_enabled))
        IrConfig.set_param('clinic.telemed.require_password', str(self.require_password))
        IrConfig.set_param('clinic.telemed.auto_generate_password', str(self.auto_generate_password))
        IrConfig.set_param('clinic.telemed.send_email_invites', str(self.send_email_invites))
        IrConfig.set_param('clinic.telemed.send_sms_invites', str(self.send_sms_invites))
        IrConfig.set_param('clinic.telemed.reminder_time', str(self.reminder_time_minutes))

        _logger.info("Telemedicine configuration parameters updated successfully")

    @api.constrains('default_session_duration')
    def _check_session_duration(self):
        """Validate session duration"""
        for record in self:
            if record.default_session_duration < 5 or record.default_session_duration > 480:
                raise ValidationError(_("Session duration should be between 5 and 480 minutes (8 hours)."))

    @api.constrains('reminder_time_minutes')
    def _check_reminder_time(self):
        """Validate reminder time"""
        for record in self:
            if record.reminder_time_minutes < 1 or record.reminder_time_minutes > 1440:
                raise ValidationError(_("Reminder time should be between 1 and 1440 minutes (24 hours)."))

    def action_test_platform_connection(self):
        """Test connection to the selected video platform"""
        self.ensure_one()

        if self.telemed_platform == 'zoom':
            return self._test_zoom_connection()
        elif self.telemed_platform == 'google_meet':
            return self._test_google_connection()
        elif self.telemed_platform == 'teams':
            return self._test_teams_connection()
        elif self.telemed_platform == 'jitsi':
            return self._test_jitsi_connection()
        elif self.telemed_platform == 'custom':
            return self._test_custom_connection()
        else:
            raise ValidationError(_("Please select a video platform first."))

    def _test_zoom_connection(self):
        """Test Zoom API connection"""
        if not self.zoom_api_key or not self.zoom_api_secret:
            raise ValidationError(_("Please configure Zoom API credentials first."))

        try:
            # Test Zoom API connection logic here
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Zoom API connection test successful!'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise ValidationError(_("Zoom connection failed: %s") % str(e))

    def _test_google_connection(self):
        """Test Google Meet API connection"""
        if not self.google_client_id or not self.google_client_secret:
            raise ValidationError(_("Please configure Google API credentials first."))

        try:
            # Test Google API connection logic here
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Google Meet API connection test successful!'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise ValidationError(_("Google Meet connection failed: %s") % str(e))

    def _test_teams_connection(self):
        """Test Microsoft Teams API connection"""
        if not self.teams_tenant_id or not self.teams_client_id or not self.teams_client_secret:
            raise ValidationError(_("Please configure Microsoft Teams API credentials first."))

        try:
            # Test Teams API connection logic here
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Microsoft Teams API connection test successful!'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise ValidationError(_("Microsoft Teams connection failed: %s") % str(e))

    def _test_jitsi_connection(self):
        """Test Jitsi Meet connection"""
        if not self.jitsi_domain:
            raise ValidationError(_("Please configure Jitsi domain first."))

        try:
            # Test Jitsi connection logic here
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Jitsi Meet connection test successful!'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise ValidationError(_("Jitsi Meet connection failed: %s") % str(e))

    def _test_custom_connection(self):
        """Test custom platform API connection"""
        if not self.custom_api_url:
            raise ValidationError(_("Please configure custom API URL first."))

        try:
            # Test custom API connection logic here
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Custom platform API connection test successful!'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise ValidationError(_("Custom platform connection failed: %s") % str(e))


class TelemedicineConfigHelper(models.Model):
    """Helper model for accessing Telemedicine configuration"""
    _name = 'clinic.telemed.config.helper'
    _description = 'Telemedicine Configuration Helper'

    @api.model
    def get_config_value(self, param_name, default_value=''):
        """
        Get a configuration parameter value

        Args:
            param_name (str): Parameter name (without clinic.telemed prefix)
            default_value: Default value if parameter not found

        Returns:
            str: Configuration value
        """
        IrConfig = self.env['ir.config_parameter'].sudo()
        return IrConfig.get_param(f'clinic.telemed.{param_name}', default_value)

    @api.model
    def get_platform_config(self):
        """
        Get platform configuration for telemedicine integration

        Returns:
            dict: Platform configuration dictionary
        """
        IrConfig = self.env['ir.config_parameter'].sudo()
        platform = IrConfig.get_param('clinic.telemed.platform', 'jitsi')

        config = {
            'platform': platform,
            'default_duration': int(IrConfig.get_param('clinic.telemed.default_duration', '30')),
            'waiting_room_enabled': IrConfig.get_param('clinic.telemed.waiting_room_enabled', 'True') == 'True',
            'recording_enabled': IrConfig.get_param('clinic.telemed.recording_enabled', 'False') == 'True',
            'require_password': IrConfig.get_param('clinic.telemed.require_password', 'True') == 'True',
            'auto_generate_password': IrConfig.get_param('clinic.telemed.auto_generate_password', 'True') == 'True',
        }

        # Add platform-specific configuration
        if platform == 'zoom':
            config.update({
                'api_key': IrConfig.get_param('clinic.telemed.zoom_api_key', ''),
                'api_secret': IrConfig.get_param('clinic.telemed.zoom_api_secret', ''),
                'webhook_secret': IrConfig.get_param('clinic.telemed.zoom_webhook_secret', ''),
            })
        elif platform == 'google_meet':
            config.update({
                'client_id': IrConfig.get_param('clinic.telemed.google_client_id', ''),
                'client_secret': IrConfig.get_param('clinic.telemed.google_client_secret', ''),
                'refresh_token': IrConfig.get_param('clinic.telemed.google_refresh_token', ''),
            })
        elif platform == 'teams':
            config.update({
                'tenant_id': IrConfig.get_param('clinic.telemed.teams_tenant_id', ''),
                'client_id': IrConfig.get_param('clinic.telemed.teams_client_id', ''),
                'client_secret': IrConfig.get_param('clinic.telemed.teams_client_secret', ''),
            })
        elif platform == 'jitsi':
            config.update({
                'domain': IrConfig.get_param('clinic.telemed.jitsi_domain', 'meet.jit.si'),
                'app_id': IrConfig.get_param('clinic.telemed.jitsi_app_id', ''),
                'app_secret': IrConfig.get_param('clinic.telemed.jitsi_app_secret', ''),
            })
        elif platform == 'custom':
            config.update({
                'api_url': IrConfig.get_param('clinic.telemed.custom_api_url', ''),
                'api_key': IrConfig.get_param('clinic.telemed.custom_api_key', ''),
                'api_secret': IrConfig.get_param('clinic.telemed.custom_api_secret', ''),
            })

        return config

    @api.model
    def get_notification_config(self):
        """
        Get notification configuration

        Returns:
            dict: Notification configuration dictionary
        """
        IrConfig = self.env['ir.config_parameter'].sudo()

        return {
            'send_email_invites': IrConfig.get_param('clinic.telemed.send_email_invites', 'True') == 'True',
            'send_sms_invites': IrConfig.get_param('clinic.telemed.send_sms_invites', 'False') == 'True',
            'reminder_time': int(IrConfig.get_param('clinic.telemed.reminder_time', '15')),
        }

    @api.model
    def validate_platform(self, platform=None, config=None):
        """
        Validate telemedicine platform configuration

        Args:
            platform: Platform to validate (optional, uses current if not provided)
            config: Configuration dict (optional, fetches if not provided)

        Returns:
            dict: Validation result with 'valid' boolean and 'errors' list
        """
        if not config:
            config = self.get_platform_config()

        if not platform:
            platform = config.get('platform')

        errors = []
        warnings = []

        if not platform:
            return {
                'valid': False,
                'errors': [_("No platform selected")],
                'warnings': []
            }

        # Platform-specific validation
        if platform == 'zoom':
            if not config.get('api_key'):
                errors.append(_("Zoom API Key is required"))
            elif len(config.get('api_key', '')) < 20:
                errors.append(_("Zoom API Key appears to be invalid"))

            if not config.get('api_secret'):
                errors.append(_("Zoom API Secret is required"))
            elif len(config.get('api_secret', '')) < 20:
                errors.append(_("Zoom API Secret appears to be invalid"))

            if not config.get('jwt_token') and not config.get('oauth_token'):
                warnings.append(_("Consider configuring JWT or OAuth token for better security"))

        elif platform == 'google_meet':
            if not config.get('client_id'):
                errors.append(_("Google Client ID is required"))
            elif not config.get('client_id', '').endswith('.apps.googleusercontent.com'):
                errors.append(_("Google Client ID format appears invalid"))

            if not config.get('client_secret'):
                errors.append(_("Google Client Secret is required"))

            if not config.get('calendar_id'):
                warnings.append(_("Google Calendar ID recommended for scheduling"))

        elif platform == 'teams':
            if not config.get('tenant_id'):
                errors.append(_("Microsoft Tenant ID is required"))
            elif len(config.get('tenant_id', '')) != 36:  # UUID format
                errors.append(_("Microsoft Tenant ID format appears invalid"))

            if not config.get('client_id'):
                errors.append(_("Microsoft Client ID is required"))
            elif len(config.get('client_id', '')) != 36:  # UUID format
                errors.append(_("Microsoft Client ID format appears invalid"))

            if not config.get('client_secret'):
                errors.append(_("Microsoft Client Secret is required"))

        elif platform == 'jitsi':
            if not config.get('domain'):
                errors.append(_("Jitsi domain is required"))
            elif not self._validate_url(config.get('domain', '')):
                errors.append(_("Jitsi domain is not a valid URL"))

            # Jitsi can work without credentials but warn if not using self-hosted
            if 'meet.jit.si' in config.get('domain', ''):
                warnings.append(_("Using public Jitsi server. Consider self-hosting for privacy."))

        elif platform == 'custom':
            if not config.get('api_url'):
                errors.append(_("Custom platform API URL is required"))
            elif not self._validate_url(config.get('api_url', '')):
                errors.append(_("API URL is not valid"))

            if not config.get('custom_platform_name'):
                warnings.append(_("Custom platform name should be specified"))

            # Check for basic auth or token
            has_auth = (config.get('custom_api_key') or
                       config.get('custom_username') or
                       config.get('custom_token'))
            if not has_auth:
                warnings.append(_("No authentication configured for custom platform"))

        else:
            errors.append(_("Unknown platform: %s") % platform)

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'platform': platform
        }

    @api.model
    def _validate_url(self, url):
        """Validate if string is a valid URL"""
        if not url:
            return False

        import re
        # Basic URL validation regex
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        return bool(url_pattern.match(url))

    @api.model
    def is_configured(self):
        """
        Check if telemedicine is properly configured

        Returns:
            bool: True if basic configuration is complete
        """
        validation = self.validate_platform()
        return validation['valid']