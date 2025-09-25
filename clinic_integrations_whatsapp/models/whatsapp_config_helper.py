# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class WhatsAppConfigHelper(models.TransientModel):
    """Helper model for secure WhatsApp API configuration using ir.config_parameter"""
    _name = 'clinic.whatsapp.config.helper'
    _description = 'WhatsApp Configuration Helper'

    @api.model
    def get_api_config(self):
        """
        Get WhatsApp API configuration from secure ir.config_parameter storage

        Returns dict with:
        - api_url: WhatsApp API base URL
        - api_token: API access token
        - phone_number: WhatsApp Business phone number ID
        - max_retries: Maximum retry attempts for failed messages
        - retry_delay: Delay in minutes between retries
        """
        IrConfig = self.env['ir.config_parameter'].sudo()

        config = {
            'api_url': IrConfig.get_param('clinic.whatsapp.api_url', 'https://graph.facebook.com/v18.0'),
            'api_token': IrConfig.get_param('clinic.whatsapp.api_token', False),
            'phone_number': IrConfig.get_param('clinic.whatsapp.phone_number_id', False),
            'max_retries': int(IrConfig.get_param('clinic.whatsapp.max_retries', '3')),
            'retry_delay': int(IrConfig.get_param('clinic.whatsapp.retry_delay', '5')),
            'webhook_verify_token': IrConfig.get_param('clinic.whatsapp.webhook_verify_token', False),
        }

        # Check if we have the minimum required configuration
        if not config['api_token'] or not config['phone_number']:
            # Try to migrate from old config if it exists
            self._migrate_from_old_config()

            # Re-fetch after migration
            config['api_token'] = IrConfig.get_param('clinic.whatsapp.api_token', False)
            config['phone_number'] = IrConfig.get_param('clinic.whatsapp.phone_number_id', False)

        return config

    @api.model
    def set_api_config(self, **kwargs):
        """
        Set WhatsApp API configuration in secure storage

        Args:
            api_url: WhatsApp API base URL
            api_token: API access token
            phone_number: WhatsApp Business phone number ID
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries
            webhook_verify_token: Webhook verification token
        """
        IrConfig = self.env['ir.config_parameter'].sudo()

        # Map of parameter names
        param_map = {
            'api_url': 'clinic.whatsapp.api_url',
            'api_token': 'clinic.whatsapp.api_token',
            'phone_number': 'clinic.whatsapp.phone_number_id',
            'max_retries': 'clinic.whatsapp.max_retries',
            'retry_delay': 'clinic.whatsapp.retry_delay',
            'webhook_verify_token': 'clinic.whatsapp.webhook_verify_token',
        }

        for key, value in kwargs.items():
            if key in param_map and value is not None:
                IrConfig.set_param(param_map[key], value)

        _logger.info("WhatsApp configuration updated successfully")

    @api.model
    def get_config_value(self, key, default=None):
        """Get a specific configuration value"""
        IrConfig = self.env['ir.config_parameter'].sudo()

        param_name = f'clinic.whatsapp.{key}'
        return IrConfig.get_param(param_name, default)

    @api.model
    def test_connection(self):
        """Test WhatsApp API connection"""
        config = self.get_api_config()

        if not config.get('api_token'):
            raise UserError(_("WhatsApp API token not configured"))

        if not config.get('phone_number'):
            raise UserError(_("WhatsApp phone number ID not configured"))

        try:
            import requests

            # Test API endpoint
            headers = {
                'Authorization': f'Bearer {config["api_token"]}',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                f"{config['api_url']}/{config['phone_number']}",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'message': _('Connection successful!'),
                    'details': {
                        'phone_number': result.get('display_phone_number'),
                        'verified_name': result.get('verified_name'),
                        'status': result.get('account_review_status'),
                    }
                }
            else:
                return {
                    'success': False,
                    'message': _('Connection failed'),
                    'error': f"Status code: {response.status_code}",
                    'details': response.text
                }

        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'message': _('Connection error'),
                'error': str(e)
            }
        except Exception as e:
            return {
                'success': False,
                'message': _('Unexpected error'),
                'error': str(e)
            }

    @api.model
    def _migrate_from_old_config(self):
        """Migrate from old WhatsAppConfig model if it exists"""
        try:
            # Check if old config model exists
            old_config = self.env['clinic.whatsapp.config'].search(
                [('migrated_to_config_params', '=', False)],
                limit=1
            )

            if old_config:
                old_config.migrate_to_config_params()
                _logger.info("Auto-migrated WhatsApp configuration from old model")
        except KeyError:
            # Model doesn't exist, nothing to migrate
            pass
        except Exception as e:
            _logger.warning(f"Could not migrate old WhatsApp config: {str(e)}")

    @api.model
    def validate_phone_number(self, phone):
        """
        Validate and format phone number for WhatsApp

        Args:
            phone: Phone number to validate

        Returns:
            Formatted phone number or False if invalid
        """
        if not phone:
            return False

        # Remove all non-digit characters
        import re
        phone_digits = re.sub(r'\D', '', phone)

        # Must be at least 10 digits
        if len(phone_digits) < 10:
            return False

        # Add country code if not present (default to US +1)
        if not phone_digits.startswith('1') and len(phone_digits) == 10:
            phone_digits = '1' + phone_digits

        return phone_digits

    @api.model
    def get_templates(self):
        """Get available WhatsApp message templates from API"""
        config = self.get_api_config()

        if not config.get('api_token') or not config.get('phone_number'):
            return []

        try:
            import requests

            headers = {
                'Authorization': f'Bearer {config['api_token']}',
            }

            # Get WhatsApp Business Account ID first
            phone_response = requests.get(
                f"{config['api_url']}/{config['phone_number']}",
                headers=headers,
                timeout=10
            )

            if phone_response.status_code != 200:
                _logger.error(f"Failed to get phone info: {phone_response.text}")
                return []

            phone_data = phone_response.json()
            waba_id = phone_data.get('wa_id')

            if not waba_id:
                _logger.error("Could not determine WhatsApp Business Account ID")
                return []

            # Get message templates
            templates_response = requests.get(
                f"{config['api_url']}/{waba_id}/message_templates",
                headers=headers,
                timeout=10
            )

            if templates_response.status_code == 200:
                templates_data = templates_response.json()
                return templates_data.get('data', [])
            else:
                _logger.error(f"Failed to get templates: {templates_response.text}")
                return []

        except Exception as e:
            _logger.error(f"Error fetching templates: {str(e)}")
            return []

    @api.model
    def sync_templates(self):
        """Sync WhatsApp templates with local database"""
        templates = self.get_templates()

        if not templates:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Templates Found'),
                    'message': _('No templates were found or there was an error fetching them.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Update or create templates
        Template = self.env['clinic.whatsapp.template']
        updated = 0
        created = 0

        for template_data in templates:
            existing = Template.search([
                ('template_name', '=', template_data.get('name'))
            ], limit=1)

            template_vals = {
                'template_name': template_data.get('name'),
                'category': template_data.get('category', 'marketing'),
                'language_code': template_data.get('language', 'en'),
                'status': template_data.get('status', 'pending'),
                'body_text': template_data.get('body', ''),
                'header_text': template_data.get('header', ''),
                'footer_text': template_data.get('footer', ''),
            }

            if existing:
                existing.write(template_vals)
                updated += 1
            else:
                Template.create(template_vals)
                created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Templates Synced'),
                'message': _('Created %d new templates, updated %d existing templates.') % (created, updated),
                'type': 'success',
                'sticky': False,
            }
        }