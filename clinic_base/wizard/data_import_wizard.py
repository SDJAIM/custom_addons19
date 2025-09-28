# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import csv
import io
import logging

_logger = logging.getLogger(__name__)


class ClinicDataImportWizard(models.TransientModel):
    _name = 'clinic.data.import.wizard'
    _description = 'Data Import Wizard'

    name = fields.Char(
        string='Import Name',
        required=True,
        default='Data Import'
    )

    model_name = fields.Selection([
        ('clinic.patient', 'Patients'),
        ('clinic.staff', 'Staff'),
        ('clinic.appointment', 'Appointments'),
        ('clinic.treatment', 'Treatments'),
        ('product.product', 'Products'),
        ('res.partner', 'Contacts'),
    ], string='Import Type', required=True)

    file_data = fields.Binary(
        string='CSV File',
        required=True,
        help='Select CSV file to import'
    )

    file_name = fields.Char(string='File Name')

    delimiter = fields.Selection([
        (',', 'Comma (,)'),
        (';', 'Semicolon (;)'),
        ('|', 'Pipe (|)'),
        ('\t', 'Tab'),
    ], string='Delimiter', default=',', required=True)

    encoding = fields.Selection([
        ('utf-8', 'UTF-8'),
        ('latin1', 'Latin-1'),
        ('cp1252', 'Windows-1252'),
    ], string='Encoding', default='utf-8', required=True)

    skip_first_line = fields.Boolean(
        string='Skip Header Line',
        default=True,
        help='Skip the first line if it contains column headers'
    )

    update_existing = fields.Boolean(
        string='Update Existing Records',
        default=False,
        help='Update existing records if found (based on reference field)'
    )

    test_mode = fields.Boolean(
        string='Test Mode',
        default=True,
        help='Run in test mode without creating records'
    )

    import_log = fields.Text(
        string='Import Log',
        readonly=True
    )

    @api.onchange('file_data')
    def _onchange_file_data(self):
        if self.file_data:
            # Try to detect delimiter
            try:
                file_content = base64.b64decode(self.file_data).decode('utf-8')
                first_line = file_content.split('\n')[0] if file_content else ''

                if ',' in first_line:
                    self.delimiter = ','
                elif ';' in first_line:
                    self.delimiter = ';'
                elif '\t' in first_line:
                    self.delimiter = '\t'
                elif '|' in first_line:
                    self.delimiter = '|'
            except:
                pass

    def action_import(self):
        """Execute the data import"""
        self.ensure_one()

        if not self.file_data:
            raise UserError(_('Please select a file to import'))

        # Decode file
        try:
            file_content = base64.b64decode(self.file_data).decode(self.encoding)
        except Exception as e:
            raise UserError(_('Error decoding file: %s') % str(e))

        # Parse CSV
        csv_reader = csv.DictReader(
            io.StringIO(file_content),
            delimiter=self.delimiter
        )

        # Process records
        log_lines = []
        created_count = 0
        updated_count = 0
        error_count = 0

        for row_num, row in enumerate(csv_reader, start=2 if self.skip_first_line else 1):
            try:
                if self.model_name == 'clinic.patient':
                    self._import_patient_record(row, self.test_mode)
                elif self.model_name == 'res.partner':
                    self._import_partner_record(row, self.test_mode)
                else:
                    raise UserError(_('Import not implemented for model: %s') % self.model_name)

                created_count += 1
                log_lines.append(f"Row {row_num}: Success")

            except Exception as e:
                error_count += 1
                log_lines.append(f"Row {row_num}: Error - {str(e)}")
                _logger.error(f"Import error at row {row_num}: {e}")

        # Update log
        summary = f"\nSummary:\n"
        summary += f"- Created: {created_count} records\n"
        summary += f"- Updated: {updated_count} records\n"
        summary += f"- Errors: {error_count} records\n"

        if self.test_mode:
            summary += "\n⚠️ Test mode - no records were actually created"
            self.env.cr.rollback()

        self.import_log = "\n".join(log_lines) + summary

        # Log audit
        if not self.test_mode:
            self.env['clinic.audit.log'].create_log(
                action='import',
                model_name=self.model_name,
                description=f'Imported {created_count} records from CSV'
            )

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _import_patient_record(self, row, test_mode=False):
        """Import a patient record from CSV row"""
        # Map CSV columns to model fields
        values = {
            'name': row.get('name', ''),
            'email': row.get('email', ''),
            'phone': row.get('phone', ''),
            'mobile': row.get('mobile', ''),
            # Add more field mappings as needed
        }

        # Validate required fields
        if not values.get('name'):
            raise ValueError('Patient name is required')

        # Create or update record
        if not test_mode:
            # Check if exists (by email or other unique field)
            if self.update_existing and values.get('email'):
                existing = self.env['clinic.patient'].search([
                    ('email', '=', values['email'])
                ], limit=1)
                if existing:
                    existing.write(values)
                    return existing

            # Create new record
            return self.env['clinic.patient'].create(values)

    def _import_partner_record(self, row, test_mode=False):
        """Import a partner record from CSV row"""
        values = {
            'name': row.get('name', ''),
            'email': row.get('email', ''),
            'phone': row.get('phone', ''),
            'is_company': row.get('is_company', '').lower() in ['true', '1', 'yes'],
        }

        if not values.get('name'):
            raise ValueError('Partner name is required')

        if not test_mode:
            return self.env['res.partner'].create(values)