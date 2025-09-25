# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class WhatsAppSettings(models.TransientModel):
    _name = 'clinic.whatsapp.settings'
    _description = 'WhatsApp Configuration Settings'
    _inherit = 'res.config.settings'

    # WhatsApp API Configuration
    whatsapp_api_url = fields.Char(
        string='WhatsApp API URL',
        help='Base URL for WhatsApp Business API',
        config_parameter='clinic.whatsapp.api_url'
    )

    whatsapp_api_token = fields.Char(
        string='WhatsApp API Token',
        help='API access token for WhatsApp Business API (stored securely)',
        config_parameter='clinic.whatsapp.api_token'
    )

    whatsapp_phone_number = fields.Char(
        string='WhatsApp Business Phone Number',
        help='Phone number ID from WhatsApp Business Manager',
        config_parameter='clinic.whatsapp.phone_number'
    )

    whatsapp_webhook_verify_token = fields.Char(
        string='Webhook Verify Token',
        help='Token for webhook verification',
        config_parameter='clinic.whatsapp.webhook_verify_token'
    )

    whatsapp_app_secret = fields.Char(
        string='App Secret',
        help='App secret for webhook signature verification',
        config_parameter='clinic.whatsapp.app_secret'
    )

    # Message Configuration
    whatsapp_default_country_code = fields.Char(
        string='Default Country Code',
        default='+1',
        help='Default country code for phone numbers without country code',
        config_parameter='clinic.whatsapp.default_country_code'
    )

    whatsapp_max_retries = fields.Integer(
        string='Max Retry Attempts',
        default=3,
        help='Maximum number of retry attempts for failed messages',
        config_parameter='clinic.whatsapp.max_retries'
    )

    whatsapp_retry_delay = fields.Integer(
        string='Retry Delay (minutes)',
        default=5,
        help='Delay in minutes between retry attempts',
        config_parameter='clinic.whatsapp.retry_delay'
    )

    # Feature Toggles
    whatsapp_enable_reminders = fields.Boolean(
        string='Enable Appointment Reminders',
        default=True,
        help='Enable automatic appointment reminder messages',
        config_parameter='clinic.whatsapp.enable_reminders'
    )

    whatsapp_enable_confirmations = fields.Boolean(
        string='Enable Appointment Confirmations',
        default=True,
        help='Enable appointment confirmation messages',
        config_parameter='clinic.whatsapp.enable_confirmations'
    )

    whatsapp_enable_prescription_reminders = fields.Boolean(
        string='Enable Prescription Reminders',
        default=True,
        help='Enable prescription reminder messages',
        config_parameter='clinic.whatsapp.enable_prescription_reminders'
    )

    whatsapp_enable_auto_responses = fields.Boolean(
        string='Enable Auto Responses',
        default=True,
        help='Enable automatic responses to patient messages',
        config_parameter='clinic.whatsapp.enable_auto_responses'
    )

    # Security Settings
    whatsapp_require_opt_in = fields.Boolean(
        string='Require Patient Opt-In',
        default=True,
        help='Require explicit patient consent before sending messages',
        config_parameter='clinic.whatsapp.require_opt_in'
    )

    whatsapp_webhook_enabled = fields.Boolean(
        string='Enable Webhook',
        default=True,
        help='Enable webhook for receiving message status updates',
        config_parameter='clinic.whatsapp.webhook_enabled'
    )

    @api.model
    def get_values(self):
        """Get configuration values from ir.config_parameter"""
        res = super(WhatsAppSettings, self).get_values()

        # Get configuration parameters
        IrConfig = self.env['ir.config_parameter'].sudo()

        res.update({
            'whatsapp_api_url': IrConfig.get_param('clinic.whatsapp.api_url', 'https://graph.facebook.com/v18.0'),
            'whatsapp_api_token': IrConfig.get_param('clinic.whatsapp.api_token', ''),
            'whatsapp_phone_number': IrConfig.get_param('clinic.whatsapp.phone_number', ''),
            'whatsapp_webhook_verify_token': IrConfig.get_param('clinic.whatsapp.webhook_verify_token', ''),
            'whatsapp_app_secret': IrConfig.get_param('clinic.whatsapp.app_secret', ''),
            'whatsapp_default_country_code': IrConfig.get_param('clinic.whatsapp.default_country_code', '+1'),
            'whatsapp_max_retries': int(IrConfig.get_param('clinic.whatsapp.max_retries', '3')),
            'whatsapp_retry_delay': int(IrConfig.get_param('clinic.whatsapp.retry_delay', '5')),
            'whatsapp_enable_reminders': IrConfig.get_param('clinic.whatsapp.enable_reminders', 'True') == 'True',
            'whatsapp_enable_confirmations': IrConfig.get_param('clinic.whatsapp.enable_confirmations', 'True') == 'True',
            'whatsapp_enable_prescription_reminders': IrConfig.get_param('clinic.whatsapp.enable_prescription_reminders', 'True') == 'True',
            'whatsapp_enable_auto_responses': IrConfig.get_param('clinic.whatsapp.enable_auto_responses', 'True') == 'True',
            'whatsapp_require_opt_in': IrConfig.get_param('clinic.whatsapp.require_opt_in', 'True') == 'True',
            'whatsapp_webhook_enabled': IrConfig.get_param('clinic.whatsapp.webhook_enabled', 'True') == 'True',
        })

        return res

    def set_values(self):
        """Set configuration values to ir.config_parameter"""
        super(WhatsAppSettings, self).set_values()

        IrConfig = self.env['ir.config_parameter'].sudo()

        # Set configuration parameters
        IrConfig.set_param('clinic.whatsapp.api_url', self.whatsapp_api_url or '')
        IrConfig.set_param('clinic.whatsapp.api_token', self.whatsapp_api_token or '')
        IrConfig.set_param('clinic.whatsapp.phone_number', self.whatsapp_phone_number or '')
        IrConfig.set_param('clinic.whatsapp.webhook_verify_token', self.whatsapp_webhook_verify_token or '')
        IrConfig.set_param('clinic.whatsapp.app_secret', self.whatsapp_app_secret or '')
        IrConfig.set_param('clinic.whatsapp.default_country_code', self.whatsapp_default_country_code or '+1')
        IrConfig.set_param('clinic.whatsapp.max_retries', str(self.whatsapp_max_retries))
        IrConfig.set_param('clinic.whatsapp.retry_delay', str(self.whatsapp_retry_delay))
        IrConfig.set_param('clinic.whatsapp.enable_reminders', str(self.whatsapp_enable_reminders))
        IrConfig.set_param('clinic.whatsapp.enable_confirmations', str(self.whatsapp_enable_confirmations))
        IrConfig.set_param('clinic.whatsapp.enable_prescription_reminders', str(self.whatsapp_enable_prescription_reminders))
        IrConfig.set_param('clinic.whatsapp.enable_auto_responses', str(self.whatsapp_enable_auto_responses))
        IrConfig.set_param('clinic.whatsapp.require_opt_in', str(self.whatsapp_require_opt_in))
        IrConfig.set_param('clinic.whatsapp.webhook_enabled', str(self.whatsapp_webhook_enabled))

        _logger.info("WhatsApp configuration parameters updated successfully")

    @api.constrains('whatsapp_api_token')
    def _check_api_token(self):
        """Validate API token format"""
        for record in self:
            if record.whatsapp_api_token and len(record.whatsapp_api_token) < 10:
                raise ValidationError(_("WhatsApp API token appears to be too short. Please verify the token."))

    @api.constrains('whatsapp_phone_number')
    def _check_phone_number(self):
        """Validate phone number format"""
        for record in self:
            if record.whatsapp_phone_number and not record.whatsapp_phone_number.isdigit():
                raise ValidationError(_("WhatsApp phone number should contain only digits."))

    @api.constrains('whatsapp_max_retries')
    def _check_max_retries(self):
        """Validate max retries value"""
        for record in self:
            if record.whatsapp_max_retries < 0 or record.whatsapp_max_retries > 10:
                raise ValidationError(_("Max retries should be between 0 and 10."))

    @api.constrains('whatsapp_retry_delay')
    def _check_retry_delay(self):
        """Validate retry delay value"""
        for record in self:
            if record.whatsapp_retry_delay < 1 or record.whatsapp_retry_delay > 60:
                raise ValidationError(_("Retry delay should be between 1 and 60 minutes."))

    def action_test_connection(self):
        """Test WhatsApp API connection"""
        self.ensure_one()

        if not self.whatsapp_api_token:
            raise ValidationError(_("Please configure the API token first."))

        try:
            import requests
            headers = {
                'Authorization': f'Bearer {self.whatsapp_api_token}',
                'Content-Type': 'application/json'
            }

            # Test API connection by getting phone number info
            response = requests.get(
                f"{self.whatsapp_api_url}/{self.whatsapp_phone_number}",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('WhatsApp API connection test successful!'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise ValidationError(_("API connection failed: %s") % response.text)

        except requests.RequestException as e:
            raise ValidationError(_("Connection error: %s") % str(e))
        except Exception as e:
            raise ValidationError(_("Test failed: %s") % str(e))


class WhatsAppConfigHelper(models.Model):
    """Helper model for accessing WhatsApp configuration"""
    _name = 'clinic.whatsapp.config.helper'
    _description = 'WhatsApp Configuration Helper'

    @api.model
    def get_config_value(self, param_name, default_value=''):
        """
        Get a configuration parameter value

        Args:
            param_name (str): Parameter name (without clinic.whatsapp prefix)
            default_value: Default value if parameter not found

        Returns:
            str: Configuration value
        """
        IrConfig = self.env['ir.config_parameter'].sudo()
        return IrConfig.get_param(f'clinic.whatsapp.{param_name}', default_value)

    @api.model
    def get_api_config(self):
        """
        Get API configuration for WhatsApp integration

        Returns:
            dict: API configuration dictionary
        """
        IrConfig = self.env['ir.config_parameter'].sudo()

        return {
            'api_url': IrConfig.get_param('clinic.whatsapp.api_url', 'https://graph.facebook.com/v18.0'),
            'api_token': IrConfig.get_param('clinic.whatsapp.api_token', ''),
            'phone_number': IrConfig.get_param('clinic.whatsapp.phone_number', ''),
            'webhook_verify_token': IrConfig.get_param('clinic.whatsapp.webhook_verify_token', ''),
            'app_secret': IrConfig.get_param('clinic.whatsapp.app_secret', ''),
            'default_country_code': IrConfig.get_param('clinic.whatsapp.default_country_code', '+1'),
            'max_retries': int(IrConfig.get_param('clinic.whatsapp.max_retries', '3')),
            'retry_delay': int(IrConfig.get_param('clinic.whatsapp.retry_delay', '5')),
        }

    @api.model
    def get_feature_config(self):
        """
        Get feature toggle configuration

        Returns:
            dict: Feature configuration dictionary
        """
        IrConfig = self.env['ir.config_parameter'].sudo()

        return {
            'enable_reminders': IrConfig.get_param('clinic.whatsapp.enable_reminders', 'True') == 'True',
            'enable_confirmations': IrConfig.get_param('clinic.whatsapp.enable_confirmations', 'True') == 'True',
            'enable_prescription_reminders': IrConfig.get_param('clinic.whatsapp.enable_prescription_reminders', 'True') == 'True',
            'enable_auto_responses': IrConfig.get_param('clinic.whatsapp.enable_auto_responses', 'True') == 'True',
            'require_opt_in': IrConfig.get_param('clinic.whatsapp.require_opt_in', 'True') == 'True',
            'webhook_enabled': IrConfig.get_param('clinic.whatsapp.webhook_enabled', 'True') == 'True',
        }

    @api.model
    def is_configured(self):
        """
        Check if WhatsApp is properly configured

        Returns:
            bool: True if basic configuration is complete
        """
        config = self.get_api_config()
        return bool(config['api_token'] and config['phone_number'])