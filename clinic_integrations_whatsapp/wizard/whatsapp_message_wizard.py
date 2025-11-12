# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class WhatsAppMessageWizard(models.TransientModel):
    """
    Wizard to send WhatsApp messages with intelligent template suggestion

    Fase 3.4: Smart message wizard that:
    - Detects 24h window status automatically
    - Suggests templates when required
    - Allows free text when within window
    - Shows preview before sending
    """
    _name = 'clinic.whatsapp.message.wizard'
    _description = 'Send WhatsApp Message Wizard'

    # Patient information
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        readonly=True
    )

    phone_number = fields.Char(
        string='Phone Number',
        required=True,
        readonly=True
    )

    # Thread information
    thread_id = fields.Many2one(
        'clinic.whatsapp.thread',
        string='WhatsApp Thread',
        compute='_compute_thread_info',
        store=True
    )

    # Window status (computed from thread)
    window_status_text = fields.Char(
        string='Window Status',
        related='thread_id.window_status_text',
        readonly=True
    )

    window_urgency_level = fields.Selection(
        related='thread_id.window_urgency_level',
        readonly=True
    )

    can_send_free_text = fields.Boolean(
        string='Can Send Free Text',
        related='thread_id.can_send_text',
        readonly=True
    )

    requires_template = fields.Boolean(
        string='Requires Template',
        related='thread_id.requires_template',
        readonly=True
    )

    # Message type selection
    message_type = fields.Selection([
        ('text', 'Free Text'),
        ('template', 'Template'),
    ], string='Message Type',
       default='text',
       required=True)

    # Template selection
    template_id = fields.Many2one(
        'clinic.whatsapp.template',
        string='Template',
        domain="[('meta_status', '=', 'APPROVED'), ('active', '=', True), ('phi_compliant', '=', True)]"
    )

    # Template preview fields
    template_header = fields.Text(
        related='template_id.header',
        readonly=True
    )

    template_body = fields.Text(
        related='template_id.message_body',
        readonly=True
    )

    template_footer = fields.Text(
        related='template_id.footer',
        readonly=True
    )

    template_category = fields.Selection(
        related='template_id.meta_category',
        readonly=True
    )

    # Message content
    message_body = fields.Text(
        string='Message',
        help='Free text message or template body'
    )

    # Suggested templates (when outside window)
    suggested_template_ids = fields.Many2many(
        'clinic.whatsapp.template',
        string='Suggested Templates',
        compute='_compute_suggested_templates',
        help='Recommended templates for this patient'
    )

    suggested_templates_count = fields.Integer(
        compute='_compute_suggested_templates'
    )

    # UI helpers
    show_template_warning = fields.Boolean(
        compute='_compute_ui_helpers'
    )

    show_window_closing_warning = fields.Boolean(
        compute='_compute_ui_helpers'
    )

    @api.depends('patient_id', 'phone_number')
    def _compute_thread_info(self):
        """Get or create WhatsApp thread for patient"""
        for wizard in self:
            if wizard.patient_id and wizard.phone_number:
                thread = self.env['clinic.whatsapp.thread'].get_or_create_thread(
                    patient_id=wizard.patient_id.id,
                    phone_number=wizard.phone_number
                )
                wizard.thread_id = thread.id
            else:
                wizard.thread_id = False

    @api.depends('patient_id', 'requires_template')
    def _compute_suggested_templates(self):
        """
        Suggest appropriate templates based on context

        Fase 3.4: Smart template suggestion
        """
        for wizard in self:
            if not wizard.requires_template:
                wizard.suggested_template_ids = False
                wizard.suggested_templates_count = 0
                continue

            # Find approved, PHI-compliant templates
            templates = self.env['clinic.whatsapp.template'].search([
                ('meta_status', '=', 'APPROVED'),
                ('active', '=', True),
                ('phi_compliant', '=', True),
            ], limit=10, order='name')

            wizard.suggested_template_ids = templates
            wizard.suggested_templates_count = len(templates)

    @api.depends('message_type', 'requires_template', 'window_urgency_level')
    def _compute_ui_helpers(self):
        """Compute UI helper flags"""
        for wizard in self:
            # Show warning if trying to send free text outside window
            wizard.show_template_warning = (
                wizard.message_type == 'text' and
                wizard.requires_template
            )

            # Show warning if window is closing soon
            wizard.show_window_closing_warning = (
                wizard.window_urgency_level in ['warning', 'urgent']
            )

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Auto-fill message body when template selected"""
        if self.template_id and self.template_id.message_body:
            self.message_body = self.template_id.message_body
        elif not self.template_id:
            self.message_body = ''

    @api.onchange('message_type')
    def _onchange_message_type(self):
        """
        Handle message type change

        If switching to text outside window → show validation error
        """
        if self.message_type == 'text' and self.requires_template:
            # Allow it but show warning (validation happens on send)
            self.message_body = ''
            self.template_id = False
        elif self.message_type == 'template':
            self.message_body = ''

    def action_send_message(self):
        """
        Send WhatsApp message

        Validates 24h window rules before sending
        """
        self.ensure_one()

        # Validation: Free text outside window
        if self.message_type == 'text' and self.requires_template:
            raise ValidationError(
                _("❌ Cannot send free text outside 24-hour window!\n\n"
                  "Window Status: %s\n\n"
                  "Please select an approved template instead.")
                % self.window_status_text
            )

        # Validation: Template required but not selected
        if self.message_type == 'template' and not self.template_id:
            raise ValidationError(
                _("Please select a template to send.")
            )

        # Validation: Empty message
        if not self.message_body:
            raise ValidationError(
                _("Message body cannot be empty.")
            )

        # Create WhatsApp message
        try:
            message_vals = {
                'patient_id': self.patient_id.id,
                'phone_number': self.phone_number,
                'message_type': self.message_type,
                'message_body': self.message_body,
                'direction': 'outbound',
                'state': 'draft',
            }

            if self.message_type == 'template':
                message_vals['template_id'] = self.template_id.id

            message = self.env['clinic.whatsapp.message'].create(message_vals)

            # Send message
            message.action_send()

            # Update thread outbound count
            if self.thread_id:
                self.thread_id.update_outbound_message(self.message_body)

            _logger.info(
                f"✅ WhatsApp message sent via wizard: "
                f"Patient={self.patient_id.name}, Type={self.message_type}"
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '✅ Message Sent',
                    'message': f'WhatsApp message sent to {self.patient_id.name}',
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Error sending WhatsApp message: {str(e)}", exc_info=True)
            raise UserError(
                _("❌ Failed to send message:\n\n%s") % str(e)
            )

    def action_use_template(self, template_id):
        """
        Quick action to use a suggested template

        Called from template suggestion list
        """
        self.ensure_one()
        self.message_type = 'template'
        self.template_id = template_id
        return {'type': 'ir.actions.do_nothing'}
