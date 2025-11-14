# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging
import requests
import json

_logger = logging.getLogger(__name__)


class WhatsAppTemplate(models.Model):
    _name = 'clinic.whatsapp.template'
    _description = 'WhatsApp Message Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Basic fields
    name = fields.Char(
        string='Template Name',
        required=True,
        tracking=True
    )

    template_name = fields.Char(
        string='WhatsApp Template ID',
        help='Template name registered in Meta Business Manager'
    )

    template_type = fields.Selection([
        ('appointment_reminder', 'Appointment Reminder'),
        ('appointment_confirmation', 'Appointment Confirmation'),
        ('prescription_reminder', 'Prescription Reminder'),
        ('general', 'General'),
    ], string='Type', default='general', tracking=True)

    language_code = fields.Char(
        string='Language Code',
        default='en',
        help='ISO language code (e.g., en, es, pt_BR)'
    )

    # Template content
    header = fields.Text(
        string='Header',
        help='Optional header text for template'
    )

    message_body = fields.Text(
        string='Message Body',
        required=True,
        tracking=True
    )

    footer = fields.Text(
        string='Footer',
        help='Optional footer text for template'
    )

    # Message type - base field for extension
    message_type = fields.Selection(
        selection=[
            ('text', 'Text Message'),
            ('template', 'WhatsApp Template'),
        ],
        string='Message Type',
        default='text',
        required=True,
        help='Type of WhatsApp message'
    )

    # Status tracking
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )

    approval_status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Approval Status', default='draft', tracking=True,
       help='Template approval status from Meta')

    # Meta Sync Tracking (Fase 2.1)
    meta_template_id = fields.Char(
        string='Meta Template ID',
        help='Unique template ID from Meta Business Manager',
        index=True,
        readonly=True
    )

    meta_status = fields.Selection([
        ('APPROVED', 'Approved'),
        ('PENDING', 'Pending Review'),
        ('REJECTED', 'Rejected'),
        ('PAUSED', 'Paused'),
        ('DISABLED', 'Disabled'),
    ], string='Meta Status',
       help='Current status in Meta Business Manager',
       readonly=True)

    meta_category = fields.Selection([
        ('AUTHENTICATION', 'Authentication'),
        ('MARKETING', 'Marketing'),
        ('UTILITY', 'Utility'),
    ], string='Meta Category',
       help='Template category in Meta',
       readonly=True)

    meta_last_sync = fields.Datetime(
        string='Last Synced',
        readonly=True,
        help='Last time this template was synced from Meta'
    )

    meta_rejection_reason = fields.Text(
        string='Rejection Reason',
        readonly=True,
        help='Reason provided by Meta if template was rejected'
    )

    is_synced_from_meta = fields.Boolean(
        string='Synced from Meta',
        default=False,
        help='True if this template was imported from Meta Business Manager',
        readonly=True
    )

    # PHI Compliance
    phi_compliant = fields.Boolean(
        string='PHI Compliant',
        compute='_compute_phi_compliant',
        store=True,
        help='False if template contains prohibited PHI keywords'
    )

    phi_warnings = fields.Text(
        string='PHI Warnings',
        compute='_compute_phi_compliant',
        store=True,
        help='List of PHI issues found in template'
    )

    # 🏥 PHI/HIPAA Protected Keywords
    # These keywords should NEVER appear in WhatsApp templates
    PHI_KEYWORDS = [
        # Medical conditions & diagnoses
        'diabetes', 'diabetic', 'cancer', 'tumor', 'hiv', 'aids',
        'depression', 'anxiety', 'schizophrenia', 'bipolar',
        'hepatitis', 'cirrhosis', 'stroke', 'heart attack',
        'covid', 'coronavirus', 'positive test', 'negative test',

        # Lab results & measurements
        'blood test', 'lab result', 'test result', 'biopsy',
        'x-ray', 'mri', 'ct scan', 'ultrasound result',
        'glucose level', 'cholesterol', 'blood pressure reading',

        # Personal identifiers
        'ssn', 'social security', 'date of birth', 'dob',
        'medical record number', 'mrn', 'patient id',
        'insurance number', 'policy number',

        # Specific medications (generic names ok, but not specific dosages)
        'oxycodone', 'morphine', 'fentanyl', 'methadone',
        'chemotherapy', 'radiation therapy',

        # Treatment details
        'surgery result', 'operation outcome', 'procedure outcome',
        'diagnosis of', 'diagnosed with',

        # Sensitive body parts/symptoms
        'genital', 'rectal', 'anal', 'breast lump',
        'sexually transmitted', 'std', 'sti',
    ]

    @api.depends('header', 'message_body', 'footer')
    def _compute_phi_compliant(self):
        """
        Check if template contains PHI keywords

        🏥 CRITICAL: WhatsApp is NOT HIPAA-compliant
        Templates should only contain generic notifications + portal links
        """
        for template in self:
            # Combine all text fields
            full_text = ' '.join([
                template.header or '',
                template.message_body or '',
                template.footer or ''
            ]).lower()

            # Check for PHI keywords
            found_keywords = []
            for keyword in self.PHI_KEYWORDS:
                if keyword in full_text:
                    found_keywords.append(keyword)

            if found_keywords:
                template.phi_compliant = False
                template.phi_warnings = (
                    f"⚠️ PHI VIOLATION: Found prohibited keywords:\n"
                    f"• {', '.join(found_keywords)}\n\n"
                    f"WhatsApp templates should only contain:\n"
                    f"• Generic appointment reminders\n"
                    f"• Links to patient portal for details\n"
                    f"• General notifications (no medical details)"
                )
                _logger.warning(
                    f"Template '{template.name}' contains PHI keywords: {found_keywords}"
                )
            else:
                template.phi_compliant = True
                template.phi_warnings = False

    @api.constrains('message_body', 'header', 'footer')
    def _check_phi_compliance(self):
        """
        Prevent saving templates with PHI content

        🔒 ENFORCES: PHI/HIPAA compliance
        """
        for template in self:
            if not template.phi_compliant:
                raise ValidationError(
                    f"❌ Cannot save template with PHI content!\n\n"
                    f"{template.phi_warnings}\n\n"
                    f"✅ CORRECT APPROACH:\n"
                    f"• Use generic notifications only\n"
                    f"• Include portal link for details\n"
                    f"• Example: 'You have a lab result available. "
                    f"View at: https://portal.clinic.com'"
                )

    def action_check_phi_compliance(self):
        """Manual PHI compliance check (for UI button)"""
        self.ensure_one()

        if self.phi_compliant:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '✅ PHI Compliant',
                    'message': 'This template does not contain prohibited PHI keywords.',
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '⚠️ PHI Violation',
                    'message': self.phi_warnings,
                    'type': 'warning',
                    'sticky': True,
                }
            }

    # ========================================================================
    # FASE 2.1: META TEMPLATE SYNC
    # ========================================================================

    @api.model
    def _get_meta_api_config(self):
        """
        Get Meta API configuration from settings

        Returns:
            dict: API configuration with access_token, business_account_id, api_version
        Raises:
            UserError: If required credentials are missing
        """
        ICP = self.env['ir.config_parameter'].sudo()

        business_account_id = ICP.get_param('clinic.whatsapp.business_account_id')
        access_token = ICP.get_param('clinic.whatsapp.access_token')
        api_version = ICP.get_param('clinic.whatsapp.api_version', 'v18.0')

        if not business_account_id:
            raise UserError(
                _("WhatsApp Business Account ID is not configured.\n\n"
                  "Please go to Settings > WhatsApp Configuration and set your "
                  "Business Account ID (WABA).")
            )

        if not access_token:
            raise UserError(
                _("WhatsApp Access Token is not configured.\n\n"
                  "Please go to Settings > WhatsApp Configuration and set your "
                  "Access Token.")
            )

        return {
            'business_account_id': business_account_id,
            'access_token': access_token,
            'api_version': api_version,
            'api_url': f'https://graph.facebook.com/{api_version}'
        }

    @api.model
    def fetch_templates_from_meta(self):
        """
        Fetch all message templates from Meta Business Manager

        API Endpoint: GET /{business_account_id}/message_templates
        Docs: https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates

        Returns:
            list: List of template dictionaries from Meta API
        Raises:
            UserError: If API request fails
        """
        config = self._get_meta_api_config()

        url = f"{config['api_url']}/{config['business_account_id']}/message_templates"
        headers = {
            'Authorization': f"Bearer {config['access_token']}",
            'Content-Type': 'application/json',
        }

        params = {
            'limit': 100,  # Fetch up to 100 templates per request
        }

        try:
            _logger.info(f"Fetching templates from Meta API: {url}")
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            templates = data.get('data', [])

            _logger.info(f"Successfully fetched {len(templates)} templates from Meta")
            return templates

        except requests.exceptions.HTTPError as e:
            error_data = {}
            try:
                error_data = e.response.json()
            except:
                pass

            error_message = error_data.get('error', {}).get('message', str(e))
            error_code = error_data.get('error', {}).get('code', 'Unknown')

            _logger.error(f"Meta API Error: {error_code} - {error_message}")

            if e.response.status_code == 401:
                raise UserError(
                    _("❌ Authentication Failed!\n\n"
                      "Your Access Token is invalid or expired.\n"
                      "Please update your token in Settings > WhatsApp Configuration.")
                )
            elif e.response.status_code == 404:
                raise UserError(
                    _("❌ Business Account Not Found!\n\n"
                      "Business Account ID: %s\n\n"
                      "Please verify your WABA ID in Settings > WhatsApp Configuration.")
                    % config['business_account_id']
                )
            else:
                raise UserError(
                    _("❌ Meta API Error\n\n"
                      "Code: %s\n"
                      "Message: %s")
                    % (error_code, error_message)
                )

        except requests.exceptions.RequestException as e:
            _logger.error(f"Network error fetching templates: {str(e)}")
            raise UserError(
                _("❌ Network Error\n\n"
                  "Could not connect to Meta API.\n"
                  "Error: %s") % str(e)
            )

    @api.model
    def sync_templates_from_meta(self):
        """
        Sync all templates from Meta Business Manager to Odoo

        Process:
        1. Fetch templates from Meta API
        2. For each template:
           - If exists (by meta_template_id): update
           - If new: create
        3. Update sync timestamp

        Returns:
            dict: Statistics about sync operation
        """
        templates_data = self.fetch_templates_from_meta()

        stats = {
            'total': len(templates_data),
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
        }

        for template_data in templates_data:
            try:
                meta_id = template_data.get('id')
                meta_name = template_data.get('name')
                meta_status = template_data.get('status')
                meta_category = template_data.get('category')
                meta_language = template_data.get('language')

                # Extract template content from components
                components = template_data.get('components', [])
                header_text = ''
                body_text = ''
                footer_text = ''

                for component in components:
                    comp_type = component.get('type')
                    comp_text = component.get('text', '')

                    if comp_type == 'HEADER':
                        header_text = comp_text
                    elif comp_type == 'BODY':
                        body_text = comp_text
                    elif comp_type == 'FOOTER':
                        footer_text = comp_text

                # Check if template already exists
                existing = self.search([('meta_template_id', '=', meta_id)], limit=1)

                vals = {
                    'meta_template_id': meta_id,
                    'template_name': meta_name,
                    'name': meta_name,  # Use Meta name as display name
                    'language_code': meta_language,
                    'meta_status': meta_status,
                    'meta_category': meta_category,
                    'meta_last_sync': fields.Datetime.now(),
                    'is_synced_from_meta': True,
                }

                # Only update content if not empty (preserve local edits if Meta didn't return content)
                if body_text:
                    vals['message_body'] = body_text
                if header_text:
                    vals['header'] = header_text
                if footer_text:
                    vals['footer'] = footer_text

                # Map Meta status to approval_status
                status_mapping = {
                    'APPROVED': 'approved',
                    'PENDING': 'pending',
                    'REJECTED': 'rejected',
                }
                vals['approval_status'] = status_mapping.get(meta_status, 'draft')

                # Get rejection reason if available
                if meta_status == 'REJECTED':
                    rejected_reason = template_data.get('rejected_reason', '')
                    if rejected_reason:
                        vals['meta_rejection_reason'] = rejected_reason

                if existing:
                    # Update existing template
                    existing.write(vals)
                    stats['updated'] += 1
                    _logger.info(f"Updated template: {meta_name} (ID: {meta_id})")
                else:
                    # Create new template
                    # NOTE: PHI compliance will be auto-checked via computed field
                    # If template contains PHI, creation will fail with constraint error
                    try:
                        self.create(vals)
                        stats['created'] += 1
                        _logger.info(f"Created template: {meta_name} (ID: {meta_id})")
                    except ValidationError as ve:
                        # PHI compliance error - skip this template
                        _logger.warning(
                            f"Skipped template '{meta_name}' due to PHI violation: {str(ve)}"
                        )
                        stats['skipped'] += 1

            except Exception as e:
                _logger.error(f"Error syncing template {template_data.get('name')}: {str(e)}")
                stats['errors'] += 1

        return stats

    # ========================
    # Template Variables (TASK-F1-009)
    # ========================
    def render_template(self, **params):
        """
        Replace {{1}}, {{2}}, ... placeholders with actual values

        Args:
            **params: Keyword arguments with values to substitute
                     Example: name='John', date='2025-01-15'

        Returns:
            str: Rendered message body with substituted values

        Example:
            template.message_body = "Hi {{1}}, your appointment is on {{2}}"
            result = template.render_template(name='John', date='2025-01-15')
            # Returns: "Hi John, your appointment is on 2025-01-15"
        """
        import re
        from datetime import datetime

        self.ensure_one()
        body = self.message_body

        if not body:
            return ''

        # Replace placeholders in order of parameters
        for i, (key, value) in enumerate(params.items(), 1):
            placeholder = f'{{{{{i}}}}}'

            # Safe type coercion
            if isinstance(value, datetime):
                # Format datetime to user-friendly string
                value = value.strftime('%Y-%m-%d %H:%M')
            elif isinstance(value, (int, float)):
                value = str(value)
            elif value is None:
                value = ''
            elif not isinstance(value, str):
                value = str(value)

            body = body.replace(placeholder, value)

        return body

    @api.constrains('message_body')
    def _validate_placeholders(self):
        """
        Validate placeholder sequence in template body

        Ensures placeholders are sequential ({{1}}, {{2}}, {{3}}...)
        without gaps or duplicates

        Raises:
            ValidationError: If placeholders are not sequential
        """
        import re

        for template in self:
            if not template.message_body:
                continue

            # Find all placeholders like {{1}}, {{2}}, etc.
            placeholders = re.findall(r'\{\{(\d+)\}\}', template.message_body)

            if not placeholders:
                # No placeholders is valid
                continue

            # Convert to integers and get unique values
            placeholder_nums = sorted(set(int(p) for p in placeholders))

            # Check for sequential starting from 1
            max_placeholder = max(placeholder_nums)
            expected = list(range(1, max_placeholder + 1))

            if placeholder_nums != expected:
                missing = set(expected) - set(placeholder_nums)
                raise ValidationError(
                    _('Placeholders must be sequential starting from {{1}}.\n'
                      'Found: %s\n'
                      'Expected: %s\n'
                      'Missing: %s') % (
                          ', '.join(f'{{{{{n}}}}}' for n in placeholder_nums),
                          ', '.join(f'{{{{{n}}}}}' for n in expected),
                          ', '.join(f'{{{{{n}}}}}' for n in missing) if missing else 'None'
                      )
                )

    def get_placeholder_count(self):
        """
        Get number of placeholders in template

        Returns:
            int: Maximum placeholder number (0 if no placeholders)
        """
        import re

        self.ensure_one()

        if not self.message_body:
            return 0

        placeholders = re.findall(r'\{\{(\d+)\}\}', self.message_body)

        if not placeholders:
            return 0

        return max(int(p) for p in placeholders)

    def action_sync_templates(self):
        """
        Manual sync action (called from UI button)

        Returns:
            dict: Notification action with sync results
        """
        try:
            stats = self.sync_templates_from_meta()

            message = (
                f"📥 Sync Complete!\n\n"
                f"• Total templates in Meta: {stats['total']}\n"
                f"• Created: {stats['created']}\n"
                f"• Updated: {stats['updated']}\n"
                f"• Skipped (PHI): {stats['skipped']}\n"
                f"• Errors: {stats['errors']}"
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '✅ Templates Synced',
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except UserError as e:
            # Re-raise UserError to show error dialog
            raise

        except Exception as e:
            _logger.error(f"Unexpected error during sync: {str(e)}")
            raise UserError(
                _("❌ Sync Failed\n\n"
                  "An unexpected error occurred:\n%s") % str(e)
            )