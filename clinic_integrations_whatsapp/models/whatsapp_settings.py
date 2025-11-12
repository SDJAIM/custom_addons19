# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class WhatsAppSettings(models.TransientModel):
    _name = 'clinic.whatsapp.settings'
    _description = 'WhatsApp Configuration Settings'
    _inherit = 'res.config.settings'

    # Cloud API Credentials (Meta WhatsApp Business)
    whatsapp_app_id = fields.Char(
        string='App ID',
        help='WhatsApp App ID from Meta Business Manager',
        config_parameter='clinic.whatsapp.app_id'
    )

    whatsapp_app_secret = fields.Char(
        string='App Secret',
        help='App secret for webhook signature verification (HMAC-SHA256)',
        config_parameter='clinic.whatsapp.app_secret'
    )

    whatsapp_business_account_id = fields.Char(
        string='Business Account ID',
        help='WhatsApp Business Account ID (WABA ID) from Meta',
        config_parameter='clinic.whatsapp.business_account_id'
    )

    whatsapp_phone_number_id = fields.Char(
        string='Phone Number ID',
        help='Phone Number ID from WhatsApp Business Manager (not the phone number itself)',
        config_parameter='clinic.whatsapp.phone_number_id'
    )

    whatsapp_access_token = fields.Char(
        string='Access Token',
        help='Permanent or System User Access Token from Meta (stored securely)',
        config_parameter='clinic.whatsapp.access_token'
    )

    whatsapp_api_version = fields.Selection([
        ('v17.0', 'v17.0'),
        ('v18.0', 'v18.0'),
        ('v19.0', 'v19.0'),
        ('v20.0', 'v20.0'),
    ], string='API Version', default='v18.0',
       help='Meta Graph API version',
       config_parameter='clinic.whatsapp.api_version')

    # Webhook Configuration
    whatsapp_webhook_verify_token = fields.Char(
        string='Webhook Verify Token',
        help='Random string for webhook verification (your choice)',
        config_parameter='clinic.whatsapp.webhook_verify_token'
    )

    whatsapp_webhook_url = fields.Char(
        string='Webhook URL',
        compute='_compute_webhook_url',
        help='Copy this URL to Meta App Dashboard > WhatsApp > Configuration > Webhook'
    )

    # Legacy fields (for backward compatibility)
    whatsapp_api_url = fields.Char(
        string='API URL (computed)',
        compute='_compute_api_url',
        help='Computed from API version'
    )

    whatsapp_api_token = fields.Char(
        string='API Token (deprecated)',
        help='Use Access Token instead',
        config_parameter='clinic.whatsapp.api_token'
    )

    whatsapp_phone_number = fields.Char(
        string='Phone Number (deprecated)',
        help='Use Phone Number ID instead',
        config_parameter='clinic.whatsapp.phone_number'
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

    # Connection status
    is_configured = fields.Boolean(
        string='Is Configured',
        compute='_compute_is_configured',
        help='True if all required credentials are set'
    )

    @api.depends('whatsapp_access_token', 'whatsapp_phone_number_id')
    def _compute_is_configured(self):
        """Check if basic configuration is complete"""
        for record in self:
            record.is_configured = bool(
                record.whatsapp_access_token and
                record.whatsapp_phone_number_id
            )

    @api.depends('whatsapp_api_version')
    def _compute_api_url(self):
        """Compute API URL from version"""
        for record in self:
            version = record.whatsapp_api_version or 'v18.0'
            record.whatsapp_api_url = f'https://graph.facebook.com/{version}'

    def _compute_webhook_url(self):
        """Compute webhook URL from base URL"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for record in self:
            record.whatsapp_webhook_url = f"{base_url}/whatsapp/webhook" if base_url else ''

    @api.model
    def get_values(self):
        """Get configuration values from ir.config_parameter"""
        res = super(WhatsAppSettings, self).get_values()

        # Get configuration parameters
        IrConfig = self.env['ir.config_parameter'].sudo()

        res.update({
            # Cloud API credentials
            'whatsapp_app_id': IrConfig.get_param('clinic.whatsapp.app_id', ''),
            'whatsapp_app_secret': IrConfig.get_param('clinic.whatsapp.app_secret', ''),
            'whatsapp_business_account_id': IrConfig.get_param('clinic.whatsapp.business_account_id', ''),
            'whatsapp_phone_number_id': IrConfig.get_param('clinic.whatsapp.phone_number_id', ''),
            'whatsapp_access_token': IrConfig.get_param('clinic.whatsapp.access_token', ''),
            'whatsapp_api_version': IrConfig.get_param('clinic.whatsapp.api_version', 'v18.0'),
            # Webhook
            'whatsapp_webhook_verify_token': IrConfig.get_param('clinic.whatsapp.webhook_verify_token', ''),
            # Legacy (backward compatibility)
            'whatsapp_api_token': IrConfig.get_param('clinic.whatsapp.api_token', ''),
            'whatsapp_phone_number': IrConfig.get_param('clinic.whatsapp.phone_number', ''),
            # Message config
            'whatsapp_default_country_code': IrConfig.get_param('clinic.whatsapp.default_country_code', '+1'),
            'whatsapp_max_retries': int(IrConfig.get_param('clinic.whatsapp.max_retries', '3')),
            'whatsapp_retry_delay': int(IrConfig.get_param('clinic.whatsapp.retry_delay', '5')),
            # Features
            'whatsapp_enable_reminders': IrConfig.get_param('clinic.whatsapp.enable_reminders', 'True') == 'True',
            'whatsapp_enable_confirmations': IrConfig.get_param('clinic.whatsapp.enable_confirmations', 'True') == 'True',
            'whatsapp_enable_prescription_reminders': IrConfig.get_param('clinic.whatsapp.enable_prescription_reminders', 'True') == 'True',
            'whatsapp_enable_auto_responses': IrConfig.get_param('clinic.whatsapp.enable_auto_responses', 'True') == 'True',
            # Security
            'whatsapp_require_opt_in': IrConfig.get_param('clinic.whatsapp.require_opt_in', 'True') == 'True',
            'whatsapp_webhook_enabled': IrConfig.get_param('clinic.whatsapp.webhook_enabled', 'True') == 'True',
        })

        return res

    def set_values(self):
        """Set configuration values to ir.config_parameter"""
        super(WhatsAppSettings, self).set_values()

        IrConfig = self.env['ir.config_parameter'].sudo()

        # Set Cloud API credentials
        IrConfig.set_param('clinic.whatsapp.app_id', self.whatsapp_app_id or '')
        IrConfig.set_param('clinic.whatsapp.app_secret', self.whatsapp_app_secret or '')
        IrConfig.set_param('clinic.whatsapp.business_account_id', self.whatsapp_business_account_id or '')
        IrConfig.set_param('clinic.whatsapp.phone_number_id', self.whatsapp_phone_number_id or '')
        IrConfig.set_param('clinic.whatsapp.access_token', self.whatsapp_access_token or '')
        IrConfig.set_param('clinic.whatsapp.api_version', self.whatsapp_api_version or 'v18.0')

        # Set webhook configuration
        IrConfig.set_param('clinic.whatsapp.webhook_verify_token', self.whatsapp_webhook_verify_token or '')

        # Set legacy parameters (backward compatibility)
        IrConfig.set_param('clinic.whatsapp.api_token', self.whatsapp_api_token or '')
        IrConfig.set_param('clinic.whatsapp.phone_number', self.whatsapp_phone_number or '')

        # Set message configuration
        IrConfig.set_param('clinic.whatsapp.default_country_code', self.whatsapp_default_country_code or '+1')
        IrConfig.set_param('clinic.whatsapp.max_retries', str(self.whatsapp_max_retries))
        IrConfig.set_param('clinic.whatsapp.retry_delay', str(self.whatsapp_retry_delay))

        # Set feature toggles
        IrConfig.set_param('clinic.whatsapp.enable_reminders', str(self.whatsapp_enable_reminders))
        IrConfig.set_param('clinic.whatsapp.enable_confirmations', str(self.whatsapp_enable_confirmations))
        IrConfig.set_param('clinic.whatsapp.enable_prescription_reminders', str(self.whatsapp_enable_prescription_reminders))
        IrConfig.set_param('clinic.whatsapp.enable_auto_responses', str(self.whatsapp_enable_auto_responses))

        # Set security settings
        IrConfig.set_param('clinic.whatsapp.require_opt_in', str(self.whatsapp_require_opt_in))
        IrConfig.set_param('clinic.whatsapp.webhook_enabled', str(self.whatsapp_webhook_enabled))

        _logger.info("✅ WhatsApp configuration parameters updated successfully")

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
        """
        Test WhatsApp Cloud API connection

        Tests:
        1. Access Token validity
        2. Phone Number ID accessibility
        3. Display phone number info
        4. Webhook configuration (optional)
        """
        self.ensure_one()

        # Validate required fields
        if not self.whatsapp_access_token:
            raise ValidationError(_("Please configure the Access Token first."))

        if not self.whatsapp_phone_number_id:
            raise ValidationError(_("Please configure the Phone Number ID first."))

        try:
            import requests

            # Compute API URL
            api_url = f'https://graph.facebook.com/{self.whatsapp_api_version or "v18.0"}'

            headers = {
                'Authorization': f'Bearer {self.whatsapp_access_token}',
                'Content-Type': 'application/json'
            }

            # Test 1: Get phone number info
            _logger.info(f"Testing WhatsApp API connection to {api_url}/{self.whatsapp_phone_number_id}")

            response = requests.get(
                f"{api_url}/{self.whatsapp_phone_number_id}",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                phone_info = response.json()
                display_phone = phone_info.get('display_phone_number', 'Unknown')
                verified_name = phone_info.get('verified_name', 'Not verified')
                quality = phone_info.get('quality_rating', 'Unknown')

                _logger.info(f"✅ Phone Number ID valid: {display_phone} ({verified_name})")

                # Test 2: Verify Business Account ID access (optional)
                waba_status = "Not configured"
                if self.whatsapp_business_account_id:
                    try:
                        waba_response = requests.get(
                            f"{api_url}/{self.whatsapp_business_account_id}",
                            headers=headers,
                            params={'fields': 'id,name'},
                            timeout=10
                        )
                        if waba_response.status_code == 200:
                            waba_info = waba_response.json()
                            waba_status = f"✅ Accessible: {waba_info.get('name', 'Unknown')}"
                        else:
                            waba_status = f"⚠️ Error: {waba_response.status_code}"
                    except Exception as e:
                        waba_status = f"⚠️ Cannot verify: {str(e)}"

                # Build success message
                message = (
                    f"<strong>✅ Connection Successful!</strong><br/><br/>"
                    f"<strong>Phone Number:</strong> {display_phone}<br/>"
                    f"<strong>Verified Name:</strong> {verified_name}<br/>"
                    f"<strong>Quality Rating:</strong> {quality}<br/>"
                    f"<strong>Business Account:</strong> {waba_status}<br/>"
                    f"<strong>API Version:</strong> {self.whatsapp_api_version or 'v18.0'}<br/><br/>"
                    f"<em>Your WhatsApp Cloud API is properly configured.</em>"
                )

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': '✅ Connection Test Successful',
                        'message': message,
                        'type': 'success',
                        'sticky': True,
                    }
                }

            elif response.status_code == 401:
                raise ValidationError(
                    _("❌ Authentication failed!\n\n"
                      "The Access Token is invalid or expired.\n\n"
                      "Please verify:\n"
                      "• Token is copied correctly\n"
                      "• Token has not expired\n"
                      "• Token has 'whatsapp_business_messaging' permission")
                )

            elif response.status_code == 404:
                raise ValidationError(
                    _("❌ Phone Number ID not found!\n\n"
                      "Please verify:\n"
                      "• Phone Number ID is correct\n"
                      "• Phone number is registered in Meta Business Manager\n"
                      "• Access Token has permission to this phone number")
                )

            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('error', {}).get('message', response.text)

                raise ValidationError(
                    _("❌ API Error (%s):\n\n%s") % (response.status_code, error_msg)
                )

        except requests.RequestException as e:
            _logger.error(f"❌ Connection test failed: {e}")
            raise ValidationError(
                _("❌ Connection Error!\n\n"
                  "Could not reach WhatsApp API:\n%s\n\n"
                  "Please check:\n"
                  "• Internet connection\n"
                  "• Firewall settings\n"
                  "• API URL is correct") % str(e)
            )

        except ValidationError:
            raise

        except Exception as e:
            _logger.error(f"❌ Unexpected error in connection test: {e}", exc_info=True)
            raise ValidationError(_("❌ Unexpected error: %s") % str(e))

    def action_generate_verify_token(self):
        """Generate a random webhook verify token"""
        self.ensure_one()

        import secrets
        token = secrets.token_urlsafe(32)
        self.whatsapp_webhook_verify_token = token

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ Token Generated',
                'message': 'Random webhook verify token has been generated. Save your settings!',
                'type': 'success',
                'sticky': False,
            }
        }


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

        api_version = IrConfig.get_param('clinic.whatsapp.api_version', 'v18.0')
        api_url = f'https://graph.facebook.com/{api_version}'

        return {
            # New Cloud API fields
            'app_id': IrConfig.get_param('clinic.whatsapp.app_id', ''),
            'app_secret': IrConfig.get_param('clinic.whatsapp.app_secret', ''),
            'business_account_id': IrConfig.get_param('clinic.whatsapp.business_account_id', ''),
            'phone_number_id': IrConfig.get_param('clinic.whatsapp.phone_number_id', ''),
            'access_token': IrConfig.get_param('clinic.whatsapp.access_token', ''),
            'api_version': api_version,
            'api_url': api_url,
            # Webhook
            'webhook_verify_token': IrConfig.get_param('clinic.whatsapp.webhook_verify_token', ''),
            # Legacy (backward compatibility)
            'api_token': IrConfig.get_param('clinic.whatsapp.api_token', ''),
            'phone_number': IrConfig.get_param('clinic.whatsapp.phone_number', ''),
            # Other config
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

        # Check new Cloud API fields first
        if config['access_token'] and config['phone_number_id']:
            return True

        # Fallback to legacy fields (backward compatibility)
        if config['api_token'] and config['phone_number']:
            _logger.warning(
                "Using legacy API configuration. "
                "Please migrate to Cloud API (Access Token + Phone Number ID)"
            )
            return True

        return False