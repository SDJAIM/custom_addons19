# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class WhatsAppConfig(models.Model):
    """Deprecated: Use ir.config_parameter for secure configuration storage"""
    _name = 'clinic.whatsapp.config'
    _description = 'WhatsApp Configuration (Deprecated)'
    _order = 'create_date desc'

    name = fields.Char(
        string='Configuration Name',
        default='Default',
        help='This model is deprecated. Use Settings > WhatsApp Configuration instead.'
    )
    api_url = fields.Char(
        string='API URL',
        default='https://graph.facebook.com/v18.0',
        help='Deprecated: Configure via Settings > WhatsApp Configuration'
    )
    api_token = fields.Char(
        string='API Token',
        help='DEPRECATED: This field is no longer secure. Use Settings > WhatsApp Configuration.'
    )
    phone_number = fields.Char(
        string='WhatsApp Business Number',
        help='Deprecated: Configure via Settings > WhatsApp Configuration'
    )

    # Migration flag
    migrated_to_config_params = fields.Boolean(
        string='Migrated to Config Parameters',
        default=False,
        readonly=True
    )

    @api.model
    def get_config(self):
        """Get active WhatsApp configuration - now using ir.config_parameter"""
        # Log deprecation warning
        _logger.warning("WhatsAppConfig.get_config() is deprecated. Use WhatsAppConfigHelper.get_api_config() instead.")

        # Return configuration from ir.config_parameter
        helper = self.env['clinic.whatsapp.config.helper']
        return helper.get_api_config()

    @api.model
    def get_secure_config(self):
        """Get configuration using secure ir.config_parameter storage"""
        helper = self.env['clinic.whatsapp.config.helper']
        config = helper.get_api_config()

        if not config.get('api_token'):
            raise UserError(_(
                "WhatsApp API is not configured. Please go to Settings > WhatsApp Configuration to set up the integration."
            ))

        return config

    def migrate_to_config_params(self):
        """Migrate old configuration to ir.config_parameter"""
        self.ensure_one()

        if self.migrated_to_config_params:
            _logger.info(f"Configuration '{self.name}' already migrated.")
            return

        IrConfig = self.env['ir.config_parameter'].sudo()

        # Migrate configuration values
        if self.api_url:
            IrConfig.set_param('clinic.whatsapp.api_url', self.api_url)
        if self.api_token:
            IrConfig.set_param('clinic.whatsapp.api_token', self.api_token)
        if self.phone_number:
            IrConfig.set_param('clinic.whatsapp.phone_number', self.phone_number)

        # Mark as migrated
        self.migrated_to_config_params = True

        _logger.info(f"Configuration '{self.name}' migrated to ir.config_parameter successfully.")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Migration Complete'),
                'message': _('Configuration has been migrated to secure storage. You can now delete this record.'),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def migrate_all_configs(self):
        """Migrate all existing configurations to ir.config_parameter"""
        configs = self.search([('migrated_to_config_params', '=', False)])

        if not configs:
            _logger.info("No configurations to migrate.")
            return

        # Use the most recent configuration
        latest_config = configs[0]
        latest_config.migrate_to_config_params()

        # Mark others as migrated to avoid conflicts
        other_configs = configs[1:]
        if other_configs:
            other_configs.write({'migrated_to_config_params': True})
            _logger.info(f"Marked {len(other_configs)} other configurations as migrated.")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Migration Complete'),
                'message': _('All configurations have been migrated to secure storage.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def unlink(self):
        """Override unlink to suggest migration before deletion"""
        for record in self:
            if not record.migrated_to_config_params and (record.api_token or record.phone_number):
                raise UserError(_(
                    "This configuration contains data that should be migrated to secure storage first. "
                    "Use the 'Migrate to Config Parameters' button, then delete this record."
                ))

        return super(WhatsAppConfig, self).unlink()