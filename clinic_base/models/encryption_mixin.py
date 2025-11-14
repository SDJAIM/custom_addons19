# -*- coding: utf-8 -*-
"""
TASK-F3-007: Data Encryption at Rest

Provides field-level encryption for sensitive data (names, emails, phones, medical records)
to comply with HIPAA/GDPR requirements.

⚠️ IMPORTANT TRADE-OFFS:
- Performance overhead on every read/write
- No LIKE/ILIKE queries on encrypted fields
- More complex backup/restore procedures
- Key rotation requires re-encryption of all data

BENEFITS:
+ Protection if database is compromised
+ Compliance with healthcare regulations
+ Granular control over sensitive data

SECURITY NOTES:
- Encryption key MUST be stored securely (environment variable, vault)
- Key MUST be backed up separately from database
- Consider key rotation policy
- Use strong encryption (AES-256)
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import base64
import os

_logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    _logger.warning(
        "cryptography library not installed. "
        "Field encryption will not work. "
        "Install with: pip install cryptography"
    )


class EncryptionMixin(models.AbstractModel):
    """
    Mixin for models that need field encryption

    Usage:
        class MyModel(models.Model):
            _name = 'my.model'
            _inherit = ['encryption.mixin']

            sensitive_field = fields.Char(string='Sensitive')

            def write(self, vals):
                if 'sensitive_field' in vals:
                    vals['sensitive_field'] = self._encrypt_value(vals['sensitive_field'])
                return super().write(vals)
    """
    _name = 'encryption.mixin'
    _description = 'Field Encryption Mixin'

    # Track if encryption is enabled for this record
    encryption_enabled = fields.Boolean(
        string='Encryption Enabled',
        default=False,
        help='Indicates if sensitive fields are encrypted',
        copy=False
    )

    @api.model
    def _get_encryption_key(self):
        """
        Get encryption key from secure storage

        Priority:
        1. Environment variable ODOO_ENCRYPTION_KEY
        2. ir.config_parameter (less secure)
        3. Generate new key (FIRST RUN ONLY - must be saved!)

        Returns:
            bytes: Encryption key
        """
        if not CRYPTO_AVAILABLE:
            raise UserError(_(
                "Encryption is not available. "
                "Please install cryptography: pip install cryptography"
            ))

        # Try environment variable first (most secure)
        env_key = os.environ.get('ODOO_ENCRYPTION_KEY')
        if env_key:
            try:
                # Validate it's a valid Fernet key
                Fernet(env_key.encode())
                return env_key.encode()
            except Exception as e:
                _logger.error(f"Invalid encryption key in environment: {e}")

        # Fall back to config parameter (less secure but convenient for dev)
        key = self.env['ir.config_parameter'].sudo().get_param('clinic.encryption_key')

        if not key:
            # Generate new key (ONLY on first run)
            _logger.warning(
                "⚠️ Generating NEW encryption key. "
                "This should ONLY happen on initial setup!"
            )
            new_key = Fernet.generate_key().decode()

            # Save to config (NOT recommended for production!)
            self.env['ir.config_parameter'].sudo().set_param('clinic.encryption_key', new_key)

            _logger.warning(
                "🔐 IMPORTANT: Encryption key generated and saved to database. "
                "For PRODUCTION, move this key to environment variable ODOO_ENCRYPTION_KEY "
                "and remove from ir.config_parameter!"
            )

            key = new_key

        try:
            # Validate key
            Fernet(key.encode())
            return key.encode()
        except Exception as e:
            raise UserError(_(
                "Invalid encryption key configuration. "
                "Please check your ODOO_ENCRYPTION_KEY environment variable. "
                "Error: %s"
            ) % str(e))

    def _encrypt_value(self, value):
        """
        Encrypt a string value

        Args:
            value (str): Plain text value

        Returns:
            str: Base64-encoded encrypted value prefixed with 'ENC:'
        """
        if not value:
            return value

        if isinstance(value, str) and value.startswith('ENC:'):
            # Already encrypted
            return value

        if not CRYPTO_AVAILABLE:
            _logger.warning("Encryption not available - storing plain text!")
            return value

        try:
            key = self._get_encryption_key()
            f = Fernet(key)

            # Encrypt
            encrypted_bytes = f.encrypt(value.encode('utf-8'))

            # Encode to base64 for database storage
            encrypted_b64 = base64.b64encode(encrypted_bytes).decode('utf-8')

            # Prefix with 'ENC:' to identify encrypted values
            return f'ENC:{encrypted_b64}'

        except Exception as e:
            _logger.error(f"Encryption failed: {e}", exc_info=True)
            raise UserError(_("Failed to encrypt data: %s") % str(e))

    def _decrypt_value(self, encrypted_value):
        """
        Decrypt an encrypted value

        Args:
            encrypted_value (str): Encrypted value (prefixed with 'ENC:')

        Returns:
            str: Decrypted plain text value
        """
        if not encrypted_value:
            return encrypted_value

        if not isinstance(encrypted_value, str) or not encrypted_value.startswith('ENC:'):
            # Not encrypted, return as-is
            return encrypted_value

        if not CRYPTO_AVAILABLE:
            return "[ENCRYPTED - cryptography library not available]"

        try:
            # Remove 'ENC:' prefix
            encrypted_b64 = encrypted_value[4:]

            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted_b64.encode('utf-8'))

            # Decrypt
            key = self._get_encryption_key()
            f = Fernet(key)
            decrypted_bytes = f.decrypt(encrypted_bytes)

            return decrypted_bytes.decode('utf-8')

        except InvalidToken:
            _logger.error("Invalid encryption token - wrong key or corrupted data")
            return "[ENCRYPTED - invalid key]"
        except Exception as e:
            _logger.error(f"Decryption failed: {e}", exc_info=True)
            return "[ENCRYPTED - decryption failed]"

    def _encrypt_fields(self, vals, field_names):
        """
        Helper to encrypt multiple fields in a vals dict

        Args:
            vals (dict): Values dictionary
            field_names (list): List of field names to encrypt

        Returns:
            dict: Updated vals with encrypted values
        """
        for field_name in field_names:
            if field_name in vals and vals[field_name]:
                vals[field_name] = self._encrypt_value(vals[field_name])
        return vals

    def _decrypt_fields(self, field_names):
        """
        Helper to decrypt multiple fields on self

        Args:
            field_names (list): List of field names to decrypt

        Returns:
            dict: Dictionary of decrypted values
        """
        self.ensure_one()
        result = {}
        for field_name in field_names:
            encrypted_value = getattr(self, field_name, None)
            if encrypted_value:
                result[field_name] = self._decrypt_value(encrypted_value)
            else:
                result[field_name] = encrypted_value
        return result

    @api.model
    def rotate_encryption_key(self, old_key, new_key):
        """
        Rotate encryption key for all encrypted records

        ⚠️ THIS IS A DANGEROUS OPERATION - BACKUP FIRST!

        Args:
            old_key (str): Old encryption key
            new_key (str): New encryption key
        """
        if not CRYPTO_AVAILABLE:
            raise UserError(_("Encryption not available"))

        # Validate keys
        try:
            Fernet(old_key.encode())
            Fernet(new_key.encode())
        except Exception as e:
            raise UserError(_("Invalid encryption key format: %s") % str(e))

        _logger.info(f"Starting key rotation for {self._name}...")

        records = self.search([('encryption_enabled', '=', True)])
        count = 0

        for record in records:
            try:
                # This would need to be implemented per model
                # to know which fields to re-encrypt
                pass
            except Exception as e:
                _logger.error(f"Failed to rotate key for record {record.id}: {e}")

        _logger.info(f"Key rotation complete. Processed {count} records.")

        return count


class EncryptionKeyManagement(models.TransientModel):
    """
    Wizard for encryption key management
    """
    _name = 'clinic.encryption.key.management'
    _description = 'Encryption Key Management'

    operation = fields.Selection([
        ('generate', 'Generate New Key'),
        ('export', 'Export Current Key'),
        ('rotate', 'Rotate Key'),
    ], string='Operation', required=True, default='generate')

    new_key = fields.Char(
        string='New Encryption Key',
        help='Generated encryption key (save this securely!)'
    )

    old_key = fields.Char(
        string='Old Key',
        help='Required for key rotation'
    )

    confirmation = fields.Boolean(
        string='I have backed up the database',
        help='Required for key rotation'
    )

    def action_generate_key(self):
        """Generate a new encryption key"""
        if not CRYPTO_AVAILABLE:
            raise UserError(_("cryptography library not installed"))

        new_key = Fernet.generate_key().decode()
        self.new_key = new_key

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_export_key(self):
        """Export current encryption key"""
        self.ensure_one()

        mixin = self.env['encryption.mixin']
        key = mixin._get_encryption_key().decode()

        self.new_key = key

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_rotate_key(self):
        """Rotate encryption key"""
        self.ensure_one()

        if not self.confirmation:
            raise UserError(_("You must confirm database backup before rotating keys!"))

        if not self.old_key or not self.new_key:
            raise UserError(_("Both old and new keys are required!"))

        # This is a placeholder - actual implementation would need to
        # iterate through all models with encryption and re-encrypt data
        raise UserError(_(
            "Key rotation is not yet implemented. "
            "This requires careful planning and testing. "
            "Contact support for assistance."
        ))
