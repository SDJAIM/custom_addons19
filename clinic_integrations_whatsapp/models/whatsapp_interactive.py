# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class WhatsAppTemplateButton(models.Model):
    """
    TASK-F3-003: WhatsApp Interactive Button Configuration

    Reply buttons for interactive WhatsApp messages (max 3 buttons)
    """
    _name = 'clinic.whatsapp.template.button'
    _description = 'WhatsApp Template Button'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'clinic.whatsapp.template',
        string='Template',
        required=True,
        ondelete='cascade',
        index=True
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Display order'
    )

    button_text = fields.Char(
        string='Button Text',
        required=True,
        size=20,  # WhatsApp Cloud API limit
        help='Text displayed on the button (max 20 characters)'
    )

    button_id = fields.Char(
        string='Button ID',
        required=True,
        help='Unique identifier used to detect which button was clicked'
    )

    button_type = fields.Selection([
        ('reply', 'Reply Button'),
        ('url', 'URL Button'),
        ('call', 'Call Button'),
    ], string='Button Type', default='reply', required=True)

    url = fields.Char(
        string='URL',
        help='URL for URL buttons'
    )

    phone_number = fields.Char(
        string='Phone Number',
        help='Phone number for call buttons'
    )

    @api.constrains('button_text')
    def _check_button_text_length(self):
        """Validate button text length"""
        for button in self:
            if len(button.button_text) > 20:
                raise ValidationError(_(
                    'Button text cannot exceed 20 characters.\n\n'
                    'Current length: %d\n'
                    'Text: "%s"'
                ) % (len(button.button_text), button.button_text))


class WhatsAppTemplateListSection(models.Model):
    """
    TASK-F3-003: WhatsApp List Section

    Groups related list items together (max 10 sections)
    """
    _name = 'clinic.whatsapp.template.list.section'
    _description = 'WhatsApp Template List Section'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'clinic.whatsapp.template',
        string='Template',
        required=True,
        ondelete='cascade',
        index=True
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    title = fields.Char(
        string='Section Title',
        required=True,
        size=24,  # WhatsApp limit
        help='Title for this section (max 24 characters)'
    )

    row_ids = fields.One2many(
        'clinic.whatsapp.template.list.row',
        'section_id',
        string='Rows'
    )

    row_count = fields.Integer(
        string='Rows',
        compute='_compute_row_count'
    )

    @api.depends('row_ids')
    def _compute_row_count(self):
        """Count rows in section"""
        for section in self:
            section.row_count = len(section.row_ids)

    @api.constrains('title')
    def _check_title_length(self):
        """Validate title length"""
        for section in self:
            if len(section.title) > 24:
                raise ValidationError(_(
                    'Section title cannot exceed 24 characters.\n\n'
                    'Current: %d\n'
                    'Title: "%s"'
                ) % (len(section.title), section.title))


class WhatsAppTemplateListRow(models.Model):
    """
    TASK-F3-003: WhatsApp List Row

    Individual selectable items in a list (max 10 per section)
    """
    _name = 'clinic.whatsapp.template.list.row'
    _description = 'WhatsApp Template List Row'
    _order = 'sequence, id'

    section_id = fields.Many2one(
        'clinic.whatsapp.template.list.section',
        string='Section',
        required=True,
        ondelete='cascade',
        index=True
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    row_id = fields.Char(
        string='Row ID',
        required=True,
        help='Unique identifier for this row'
    )

    title = fields.Char(
        string='Title',
        required=True,
        size=24,  # WhatsApp limit
        help='Row title (max 24 characters)'
    )

    description = fields.Char(
        string='Description',
        size=72,  # WhatsApp limit
        help='Optional description (max 72 characters)'
    )

    @api.constrains('title', 'description')
    def _check_field_lengths(self):
        """Validate field lengths"""
        for row in self:
            if len(row.title) > 24:
                raise ValidationError(_(
                    'Row title cannot exceed 24 characters.\n\n'
                    'Current: %d'
                ) % len(row.title))

            if row.description and len(row.description) > 72:
                raise ValidationError(_(
                    'Row description cannot exceed 72 characters.\n\n'
                    'Current: %d'
                ) % len(row.description))


class WhatsAppTemplate(models.Model):
    """
    TASK-F3-003: Extend WhatsApp Template with Interactive Message Types
    """
    _inherit = 'clinic.whatsapp.template'

    message_type = fields.Selection(
        selection_add=[
            ('interactive_buttons', 'Interactive Buttons'),
            ('interactive_list', 'Interactive List'),
        ],
        ondelete={
            'interactive_buttons': 'set default',
            'interactive_list': 'set default'
        }
    )

    button_ids = fields.One2many(
        'clinic.whatsapp.template.button',
        'template_id',
        string='Buttons'
    )

    button_count = fields.Integer(
        string='Buttons',
        compute='_compute_button_count'
    )

    list_section_ids = fields.One2many(
        'clinic.whatsapp.template.list.section',
        'template_id',
        string='List Sections'
    )

    list_section_count = fields.Integer(
        string='Sections',
        compute='_compute_list_section_count'
    )

    list_button_text = fields.Char(
        string='List Button Text',
        size=20,
        default='Select Option',
        help='Text for button that opens the list (max 20 characters)'
    )

    @api.depends('button_ids')
    def _compute_button_count(self):
        """Count buttons"""
        for template in self:
            template.button_count = len(template.button_ids)

    @api.depends('list_section_ids')
    def _compute_list_section_count(self):
        """Count list sections"""
        for template in self:
            template.list_section_count = len(template.list_section_ids)

    @api.constrains('button_ids', 'message_type')
    def _check_button_count(self):
        """
        WhatsApp Cloud API allows maximum 3 reply buttons
        """
        for template in self:
            if template.message_type == 'interactive_buttons':
                button_count = len(template.button_ids)
                if button_count > 3:
                    raise ValidationError(_(
                        'Maximum 3 buttons allowed for interactive messages.\n\n'
                        'Current: %d buttons\n\n'
                        'Please remove %d button(s).'
                    ) % (button_count, button_count - 3))

                if button_count < 1:
                    raise ValidationError(_(
                        'At least 1 button is required for interactive button messages.'
                    ))

    @api.constrains('list_section_ids', 'message_type')
    def _check_list_sections(self):
        """
        WhatsApp limits: max 10 sections, max 10 rows per section
        """
        for template in self:
            if template.message_type == 'interactive_list':
                section_count = len(template.list_section_ids)

                if section_count > 10:
                    raise ValidationError(_(
                        'Maximum 10 sections allowed.\n\n'
                        'Current: %d sections'
                    ) % section_count)

                if section_count < 1:
                    raise ValidationError(_(
                        'At least 1 section is required for list messages.'
                    ))

                # Check rows per section
                for section in template.list_section_ids:
                    row_count = len(section.row_ids)
                    if row_count > 10:
                        raise ValidationError(_(
                            'Maximum 10 rows per section allowed.\n\n'
                            'Section "%s" has %d rows'
                        ) % (section.title, row_count))

                    if row_count < 1:
                        raise ValidationError(_(
                            'Section "%s" must have at least 1 row.'
                        ) % section.title)
