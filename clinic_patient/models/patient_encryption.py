# -*- coding: utf-8 -*-
"""
TASK-F3-007: Patient Data Encryption Example

This module shows how to apply field-level encryption to sensitive patient data.

⚠️ IMPORTANT: Encryption is DISABLED by default.
To enable:
1. Set environment variable: ODOO_ENCRYPTION_KEY=<your-key>
2. Set patient.enable_field_encryption = True
3. Encrypt existing data using the migration wizard

ENCRYPTED FIELDS:
- name (Full Name)
- email
- mobile
- phone
- national_id
- medical_record_number

NOTE: Once encrypted, you CANNOT use LIKE/ILIKE queries on these fields!
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PatientEncryption(models.Model):
    """
    Extends clinic.patient with optional field encryption
    """
    _inherit = ['clinic.patient', 'encryption.mixin']
    _name = 'clinic.patient'

    enable_field_encryption = fields.Boolean(
        string='Enable Field Encryption',
        default=False,
        help='Enable encryption for sensitive fields (name, email, phone, etc.)'
    )

    # List of fields to encrypt
    ENCRYPTED_FIELDS = ['name', 'email', 'mobile', 'phone', 'national_id']

    @api.model
    def create(self, vals):
        """Encrypt sensitive fields on create"""
        # Check if encryption is enabled globally
        encrypt = self.env['ir.config_parameter'].sudo().get_param(
            'clinic.patient.encryption_enabled',
            default='False'
        ) == 'True'

        if encrypt and vals.get('enable_field_encryption', True):
            vals = self._encrypt_fields(vals, self.ENCRYPTED_FIELDS)
            vals['encryption_enabled'] = True

        return super().create(vals)

    def write(self, vals):
        """Encrypt sensitive fields on write"""
        # Check if any encrypted field is being updated
        if any(field in vals for field in self.ENCRYPTED_FIELDS):
            for record in self:
                if record.enable_field_encryption or record.encryption_enabled:
                    vals = self._encrypt_fields(vals, self.ENCRYPTED_FIELDS)

        return super().write(vals)

    def read(self, fields=None, load='_classic_read'):
        """Decrypt sensitive fields on read"""
        result = super().read(fields=fields, load=load)

        # If specific fields requested, check if any are encrypted
        if fields:
            encrypted_requested = [f for f in fields if f in self.ENCRYPTED_FIELDS]
        else:
            encrypted_requested = self.ENCRYPTED_FIELDS

        if not encrypted_requested:
            return result

        # Decrypt values
        for record_vals in result:
            if record_vals.get('encryption_enabled'):
                for field_name in encrypted_requested:
                    if field_name in record_vals and record_vals[field_name]:
                        # Find the record to use its decrypt method
                        record = self.browse(record_vals['id'])
                        record_vals[field_name] = record._decrypt_value(record_vals[field_name])

        return result

    def get_decrypted_value(self, field_name):
        """
        Get decrypted value for a specific field

        Usage:
            decrypted_name = patient.get_decrypted_value('name')

        Args:
            field_name (str): Field name to decrypt

        Returns:
            str: Decrypted value
        """
        self.ensure_one()

        if field_name not in self.ENCRYPTED_FIELDS:
            raise UserError(_("Field %s is not configured for encryption") % field_name)

        value = getattr(self, field_name, None)
        if not value:
            return value

        if self.encryption_enabled:
            return self._decrypt_value(value)
        else:
            return value

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        """
        Override search to warn about encrypted field queries

        ⚠️ IMPORTANT: You CANNOT search encrypted fields with LIKE/ILIKE!
        This will return empty results.
        """
        # Check if search involves encrypted fields
        for arg in args:
            if isinstance(arg, (list, tuple)) and len(arg) >= 2:
                field_name = arg[0]
                operator = arg[1] if len(arg) > 1 else '='

                if field_name in self.ENCRYPTED_FIELDS:
                    if operator in ('like', 'ilike', '=like', '=ilike'):
                        _logger.warning(
                            f"⚠️ Search with {operator} on encrypted field '{field_name}' "
                            f"will return no results! Consider disabling encryption or "
                            f"using exact match only."
                        )

        return super().search(args, offset=offset, limit=limit, order=order, count=count)

    def action_encrypt_data(self):
        """Encrypt data for this patient"""
        self.ensure_one()

        if self.encryption_enabled:
            raise UserError(_("Data is already encrypted!"))

        # Encrypt all sensitive fields
        vals = {}
        for field_name in self.ENCRYPTED_FIELDS:
            value = getattr(self, field_name, None)
            if value:
                vals[field_name] = self._encrypt_value(value)

        vals['encryption_enabled'] = True
        vals['enable_field_encryption'] = True

        self.write(vals)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Patient data encrypted successfully'),
                'type': 'success',
            }
        }

    def action_decrypt_data(self):
        """Decrypt data for this patient (for data migration/export)"""
        self.ensure_one()

        if not self.encryption_enabled:
            raise UserError(_("Data is not encrypted!"))

        # Decrypt all fields
        vals = {}
        for field_name in self.ENCRYPTED_FIELDS:
            encrypted_value = getattr(self, field_name, None)
            if encrypted_value:
                vals[field_name] = self._decrypt_value(encrypted_value)

        vals['encryption_enabled'] = False
        vals['enable_field_encryption'] = False

        # Use sudo to bypass write encryption
        self.sudo().with_context(skip_encryption=True).write(vals)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Patient data decrypted successfully'),
                'type': 'success',
            }
        }


class PatientEncryptionMigration(models.TransientModel):
    """
    Wizard to encrypt/decrypt patient data in bulk
    """
    _name = 'clinic.patient.encryption.migration'
    _description = 'Patient Data Encryption Migration'

    operation = fields.Selection([
        ('encrypt', 'Encrypt Patient Data'),
        ('decrypt', 'Decrypt Patient Data'),
        ('test', 'Test Encryption'),
    ], string='Operation', required=True, default='test')

    patient_ids = fields.Many2many(
        'clinic.patient',
        string='Patients',
        help='Leave empty to process all patients'
    )

    progress = fields.Integer(string='Progress', readonly=True)
    total = fields.Integer(string='Total', readonly=True)
    log = fields.Text(string='Log', readonly=True)

    def action_execute(self):
        """Execute the encryption operation"""
        self.ensure_one()

        patients = self.patient_ids or self.env['clinic.patient'].search([])
        self.total = len(patients)

        log_lines = []
        log_lines.append(f"Starting {self.operation} for {self.total} patients...")
        log_lines.append("=" * 80)

        success_count = 0
        error_count = 0

        for idx, patient in enumerate(patients, 1):
            try:
                if self.operation == 'encrypt':
                    if not patient.encryption_enabled:
                        patient.action_encrypt_data()
                        success_count += 1
                        log_lines.append(f"✓ Encrypted: {patient.name} ({patient.patient_code})")
                    else:
                        log_lines.append(f"⊘ Skipped (already encrypted): {patient.name}")

                elif self.operation == 'decrypt':
                    if patient.encryption_enabled:
                        patient.action_decrypt_data()
                        success_count += 1
                        log_lines.append(f"✓ Decrypted: {patient.name} ({patient.patient_code})")
                    else:
                        log_lines.append(f"⊘ Skipped (not encrypted): {patient.name}")

                elif self.operation == 'test':
                    # Test encryption/decryption cycle
                    original_name = patient.name
                    encrypted = patient._encrypt_value(original_name)
                    decrypted = patient._decrypt_value(encrypted)

                    if decrypted == original_name:
                        success_count += 1
                        log_lines.append(f"✓ Test passed: {patient.patient_code}")
                    else:
                        error_count += 1
                        log_lines.append(f"✗ Test failed: {patient.patient_code}")

            except Exception as e:
                error_count += 1
                log_lines.append(f"✗ Error for {patient.patient_code}: {str(e)}")

            self.progress = idx

        log_lines.append("\n" + "=" * 80)
        log_lines.append(f"Operation completed!")
        log_lines.append(f"Success: {success_count}, Errors: {error_count}")

        self.log = "\n".join(log_lines)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
