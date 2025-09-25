# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval
import base64
import csv
import io
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class DataMigrationWizard(models.TransientModel):
    _name = 'clinic.data.migration.wizard'
    _description = 'Data Migration Wizard'

    name = fields.Char(
        string='Migration Name',
        required=True,
        default=lambda self: f"Migration {fields.Datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )

    migration_type = fields.Selection([
        ('import', 'Import Data'),
        ('export', 'Export Data'),
        ('sync', 'Synchronize'),
        ('transform', 'Transform Data')
    ], string='Migration Type', required=True, default='import')

    model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        domain=[('model', 'like', 'clinic.%')]
    )

    model_name = fields.Char(
        related='model_id.model',
        string='Model Name',
        readonly=True
    )

    # Import/Export Settings
    file_type = fields.Selection([
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
        ('xml', 'XML')
    ], string='File Type', default='csv')

    import_file = fields.Binary(
        string='Import File',
        attachment=True
    )

    import_filename = fields.Char(
        string='Filename'
    )

    export_file = fields.Binary(
        string='Export File',
        readonly=True,
        attachment=True
    )

    export_filename = fields.Char(
        string='Export Filename',
        readonly=True
    )

    # Field Mapping
    field_mapping = fields.Text(
        string='Field Mapping',
        help='JSON mapping of source fields to target fields'
    )

    auto_map_fields = fields.Boolean(
        string='Auto-Map Fields',
        default=True,
        help='Automatically map fields with matching names'
    )

    # Options
    skip_errors = fields.Boolean(
        string='Skip Errors',
        default=True,
        help='Continue import even if some records fail'
    )

    update_existing = fields.Boolean(
        string='Update Existing',
        help='Update existing records instead of creating new ones'
    )

    key_field = fields.Many2one(
        'ir.model.fields',
        string='Key Field',
        help='Field to use for matching existing records',
        domain="[('model_id', '=', model_id)]"
    )

    batch_size = fields.Integer(
        string='Batch Size',
        default=100,
        help='Number of records to process at once'
    )

    # Transformation Rules
    transformation_rules = fields.Text(
        string='Transformation Rules',
        help='Python code to transform data before import'
    )

    # Progress
    state = fields.Selection([
        ('draft', 'Draft'),
        ('mapping', 'Field Mapping'),
        ('preview', 'Preview'),
        ('processing', 'Processing'),
        ('done', 'Done')
    ], string='State', default='draft')

    total_records = fields.Integer(
        string='Total Records',
        readonly=True
    )

    processed_records = fields.Integer(
        string='Processed Records',
        readonly=True
    )

    success_count = fields.Integer(
        string='Successful',
        readonly=True
    )

    error_count = fields.Integer(
        string='Errors',
        readonly=True
    )

    # Results
    preview_data = fields.Text(
        string='Preview Data',
        readonly=True
    )

    error_log = fields.Text(
        string='Error Log',
        readonly=True
    )

    result_summary = fields.Html(
        string='Result Summary',
        readonly=True
    )

    # Mapping Configuration
    mapping_lines = fields.One2many(
        'clinic.data.migration.mapping',
        'wizard_id',
        string='Field Mappings'
    )

    @api.onchange('model_id')
    def _onchange_model_id(self):
        """Update available fields when model changes"""
        if self.model_id and self.auto_map_fields:
            self._generate_field_mapping()

    @api.onchange('import_file')
    def _onchange_import_file(self):
        """Parse import file and detect fields"""
        if self.import_file and self.file_type:
            self._parse_import_file()

    def _generate_field_mapping(self):
        """Generate automatic field mapping"""
        if not self.model_id:
            return

        # Get model fields
        fields_obj = self.env['ir.model.fields']
        model_fields = fields_obj.search([
            ('model_id', '=', self.model_id.id),
            ('store', '=', True),
            ('compute', '=', False)
        ])

        # Create mapping lines
        mapping_lines = []
        for field in model_fields:
            if field.name not in ['id', 'create_uid', 'create_date', 'write_uid', 'write_date']:
                mapping_lines.append((0, 0, {
                    'target_field_id': field.id,
                    'target_field_name': field.name,
                    'target_field_type': field.ttype,
                    'source_column': field.name,  # Default to same name
                    'is_required': field.required,
                }))

        self.mapping_lines = mapping_lines

    def _parse_import_file(self):
        """Parse import file to detect structure"""
        if not self.import_file:
            return

        file_content = base64.b64decode(self.import_file)

        try:
            if self.file_type == 'csv':
                self._parse_csv(file_content)
            elif self.file_type == 'json':
                self._parse_json(file_content)
            elif self.file_type == 'excel':
                self._parse_excel(file_content)
        except Exception as e:
            raise UserError(_("Error parsing file: %s") % str(e))

    def _parse_csv(self, content):
        """Parse CSV file"""
        csv_file = io.StringIO(content.decode('utf-8'))
        reader = csv.DictReader(csv_file)

        # Get headers
        headers = reader.fieldnames
        self.total_records = sum(1 for _ in reader)

        # Update mapping with detected columns
        for line in self.mapping_lines:
            if line.source_column in headers:
                line.is_mapped = True

        # Preview first 5 records
        csv_file.seek(0)
        reader = csv.DictReader(csv_file)
        preview_records = []
        for i, row in enumerate(reader):
            if i >= 5:
                break
            preview_records.append(row)

        self.preview_data = json.dumps(preview_records, indent=2)

    def _parse_json(self, content):
        """Parse JSON file"""
        data = json.loads(content.decode('utf-8'))

        if isinstance(data, list):
            self.total_records = len(data)
            # Preview first 5 records
            self.preview_data = json.dumps(data[:5], indent=2)
        else:
            self.total_records = 1
            self.preview_data = json.dumps(data, indent=2)

    def action_preview(self):
        """Preview import data with mapping"""
        self.ensure_one()
        self.state = 'preview'

        # Generate preview of how data will be imported
        preview_html = self._generate_preview_html()
        self.result_summary = preview_html

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.data.migration.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_import(self):
        """Execute the import process"""
        self.ensure_one()

        if self.migration_type == 'import':
            self._execute_import()
        elif self.migration_type == 'export':
            self._execute_export()
        elif self.migration_type == 'transform':
            self._execute_transform()

        self.state = 'done'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.data.migration.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def _execute_import(self):
        """Execute data import"""
        if not self.import_file:
            raise UserError(_("Please upload a file to import"))

        file_content = base64.b64decode(self.import_file)
        Model = self.env[self.model_name]

        # Parse file
        if self.file_type == 'csv':
            records = self._parse_csv_for_import(file_content)
        elif self.file_type == 'json':
            records = json.loads(file_content.decode('utf-8'))
        else:
            raise UserError(_("Unsupported file type for import"))

        # Process records
        self.total_records = len(records)
        errors = []

        for i in range(0, len(records), self.batch_size):
            batch = records[i:i + self.batch_size]

            for record_data in batch:
                try:
                    # Map fields
                    mapped_data = self._map_fields(record_data)

                    # Apply transformations
                    if self.transformation_rules:
                        mapped_data = self._apply_transformations(mapped_data)

                    # Check if update existing
                    if self.update_existing and self.key_field:
                        key_value = mapped_data.get(self.key_field.name)
                        existing = Model.search([
                            (self.key_field.name, '=', key_value)
                        ], limit=1)

                        if existing:
                            existing.write(mapped_data)
                        else:
                            Model.create(mapped_data)
                    else:
                        Model.create(mapped_data)

                    self.success_count += 1

                except Exception as e:
                    self.error_count += 1
                    errors.append(f"Row {self.processed_records + 1}: {str(e)}")

                    if not self.skip_errors:
                        raise

                self.processed_records += 1

            # Commit batch
            self.env.cr.commit()

        # Update results
        if errors:
            self.error_log = '\n'.join(errors[:100])  # Limit to 100 errors

        self.result_summary = f"""
        <h3>Import Results</h3>
        <ul>
            <li>Total Records: {self.total_records}</li>
            <li>Successfully Imported: {self.success_count}</li>
            <li>Errors: {self.error_count}</li>
        </ul>
        """

    def _execute_export(self):
        """Execute data export"""
        Model = self.env[self.model_name]

        # Get records to export
        domain = []
        if self.env.context.get('active_ids'):
            domain = [('id', 'in', self.env.context['active_ids'])]

        records = Model.search(domain)
        self.total_records = len(records)

        # Prepare data
        export_data = []
        for record in records:
            record_data = {}
            for line in self.mapping_lines.filtered('is_mapped'):
                field_name = line.target_field_name
                value = getattr(record, field_name)

                # Handle relational fields
                if line.target_field_type == 'many2one':
                    value = value.id if value else None
                elif line.target_field_type in ['one2many', 'many2many']:
                    value = value.ids if value else []

                record_data[line.source_column or field_name] = value

            export_data.append(record_data)

        # Generate export file
        if self.file_type == 'csv':
            output = self._generate_csv(export_data)
            self.export_filename = f"{self.model_name}_{fields.Date.today()}.csv"
        elif self.file_type == 'json':
            output = json.dumps(export_data, indent=2, default=str).encode('utf-8')
            self.export_filename = f"{self.model_name}_{fields.Date.today()}.json"
        else:
            raise UserError(_("Unsupported file type for export"))

        self.export_file = base64.b64encode(output)
        self.success_count = len(export_data)

        self.result_summary = f"""
        <h3>Export Results</h3>
        <ul>
            <li>Total Records Exported: {self.success_count}</li>
            <li>File: {self.export_filename}</li>
        </ul>
        """

    def _execute_transform(self):
        """Execute data transformation"""
        Model = self.env[self.model_name]

        # Get records to transform - use safe_eval to prevent code injection
        domain_str = self.env.context.get('domain', '[]')
        try:
            domain = safe_eval(domain_str, {'datetime': datetime})
        except (ValueError, SyntaxError) as e:
            raise UserError(_("Invalid domain filter: %s") % str(e))
        records = Model.search(domain)
        self.total_records = len(records)

        errors = []

        for record in records:
            try:
                # Apply transformation rules
                if self.transformation_rules:
                    # Create safe execution context
                    local_dict = {
                        'record': record,
                        'env': self.env,
                        'datetime': datetime,
                        'fields': fields,
                    }

                    # Execute transformation
                    exec(self.transformation_rules, local_dict)

                self.success_count += 1

            except Exception as e:
                self.error_count += 1
                errors.append(f"Record {record.id}: {str(e)}")

                if not self.skip_errors:
                    raise

            self.processed_records += 1

        if errors:
            self.error_log = '\n'.join(errors[:100])

        self.result_summary = f"""
        <h3>Transformation Results</h3>
        <ul>
            <li>Total Records: {self.total_records}</li>
            <li>Successfully Transformed: {self.success_count}</li>
            <li>Errors: {self.error_count}</li>
        </ul>
        """

    def _parse_csv_for_import(self, content):
        """Parse CSV content for import"""
        csv_file = io.StringIO(content.decode('utf-8'))
        reader = csv.DictReader(csv_file)
        return list(reader)

    def _map_fields(self, source_data):
        """Map source data to target fields"""
        mapped_data = {}

        for line in self.mapping_lines.filtered('is_mapped'):
            source_value = source_data.get(line.source_column)

            if source_value is not None:
                # Convert value based on field type
                if line.target_field_type == 'integer':
                    mapped_data[line.target_field_name] = int(source_value) if source_value else 0
                elif line.target_field_type == 'float':
                    mapped_data[line.target_field_name] = float(source_value) if source_value else 0.0
                elif line.target_field_type == 'boolean':
                    mapped_data[line.target_field_name] = source_value.lower() in ['true', '1', 'yes']
                elif line.target_field_type == 'date':
                    mapped_data[line.target_field_name] = source_value
                elif line.target_field_type == 'datetime':
                    mapped_data[line.target_field_name] = source_value
                elif line.target_field_type == 'many2one':
                    # Try to find related record
                    if line.relation_field:
                        related_model = self.env[line.relation_model]
                        related_record = related_model.search([
                            (line.relation_field, '=', source_value)
                        ], limit=1)
                        mapped_data[line.target_field_name] = related_record.id if related_record else False
                else:
                    mapped_data[line.target_field_name] = source_value

        return mapped_data

    def _apply_transformations(self, data):
        """Apply transformation rules to data"""
        if not self.transformation_rules:
            return data

        try:
            local_dict = {
                'data': data,
                'env': self.env,
                'datetime': datetime,
                'fields': fields,
            }

            exec(self.transformation_rules, local_dict)
            return local_dict.get('data', data)

        except Exception as e:
            _logger.warning(f"Transformation error: {e}")
            return data

    def _generate_csv(self, data):
        """Generate CSV content from data"""
        if not data:
            return b''

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

        return output.getvalue().encode('utf-8')

    def _generate_preview_html(self):
        """Generate HTML preview of import mapping"""
        html = """
        <h3>Import Preview</h3>
        <table class="table table-sm">
            <thead>
                <tr>
                    <th>Source Field</th>
                    <th>Target Field</th>
                    <th>Type</th>
                    <th>Required</th>
                </tr>
            </thead>
            <tbody>
        """

        for line in self.mapping_lines.filtered('is_mapped'):
            html += f"""
                <tr>
                    <td>{line.source_column}</td>
                    <td>{line.target_field_name}</td>
                    <td>{line.target_field_type}</td>
                    <td>{'Yes' if line.is_required else 'No'}</td>
                </tr>
            """

        html += """
            </tbody>
        </table>
        """

        return html


class DataMigrationMapping(models.TransientModel):
    _name = 'clinic.data.migration.mapping'
    _description = 'Data Migration Field Mapping'

    wizard_id = fields.Many2one(
        'clinic.data.migration.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )

    # Target Field
    target_field_id = fields.Many2one(
        'ir.model.fields',
        string='Target Field',
        required=True
    )

    target_field_name = fields.Char(
        related='target_field_id.name',
        string='Field Name',
        readonly=True
    )

    target_field_type = fields.Selection(
        related='target_field_id.ttype',
        string='Field Type',
        readonly=True
    )

    # Source Mapping
    source_column = fields.Char(
        string='Source Column',
        help='Column name in the source file'
    )

    is_mapped = fields.Boolean(
        string='Mapped',
        help='Field is mapped to a source column'
    )

    is_required = fields.Boolean(
        related='target_field_id.required',
        string='Required',
        readonly=True
    )

    # For relational fields
    relation_model = fields.Char(
        related='target_field_id.relation',
        string='Relation Model',
        readonly=True
    )

    relation_field = fields.Char(
        string='Relation Field',
        help='Field to use for matching in related model'
    )

    # Transformation
    transformation = fields.Char(
        string='Transformation',
        help='Python expression to transform the value'
    )