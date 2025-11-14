# -*- coding: utf-8 -*-
"""
TASK-F3-005: Social Sharing (Open Graph)

Extends appointment types with Open Graph meta tags for rich social media previews
when sharing booking links on WhatsApp, Facebook, Twitter, LinkedIn, etc.
"""
from odoo import api, fields, models, _


class AppointmentTypeOpenGraph(models.Model):
    _inherit = 'clinic.appointment.type'

    # Open Graph Fields
    og_image = fields.Binary(
        string='Social Share Image',
        help='Recommended size: 1200x630px. This image appears when sharing the booking link on social media.'
    )

    og_image_filename = fields.Char(
        string='Image Filename',
        help='Filename for the social share image'
    )

    og_title = fields.Char(
        string='Social Share Title',
        compute='_compute_og_title',
        store=True,
        help='Title that appears in social media previews (auto-generated from appointment type name)'
    )

    og_description = fields.Text(
        string='Social Share Description',
        compute='_compute_og_description',
        store=True,
        help='Description that appears in social media previews (max 160 characters recommended)'
    )

    og_custom_title = fields.Char(
        string='Custom Share Title',
        help='Override the auto-generated title with a custom one'
    )

    og_custom_description = fields.Text(
        string='Custom Share Description',
        help='Override the auto-generated description with a custom one (max 160 characters recommended)'
    )

    @api.depends('name', 'og_custom_title')
    def _compute_og_title(self):
        """
        Compute Open Graph title

        Uses custom title if provided, otherwise generates from appointment type name
        """
        for record in self:
            if record.og_custom_title:
                record.og_title = record.og_custom_title
            else:
                company_name = record.env.company.name
                record.og_title = f"Book {record.name} Appointment | {company_name}"

    @api.depends('name', 'description', 'og_custom_description')
    def _compute_og_description(self):
        """
        Compute Open Graph description

        Uses custom description if provided, otherwise generates from appointment type description
        Limits to 160 characters for optimal social media display
        """
        for record in self:
            if record.og_custom_description:
                desc = record.og_custom_description
            elif record.description:
                # Strip HTML tags if present
                desc = record.description
                # Simple HTML tag removal (could use html2text library for better results)
                import re
                desc = re.sub('<[^<]+?>', '', desc)
                desc = desc.strip()
            else:
                desc = f"Schedule your {record.name} appointment online with {record.env.company.name}. Easy, fast, and convenient booking."

            # Limit to 160 characters (meta description best practice)
            record.og_description = desc[:160] + ('...' if len(desc) > 160 else '')

    def get_og_data(self):
        """
        Get Open Graph data for this appointment type

        Returns dict with all Open Graph metadata for use in templates

        Returns:
            dict: Open Graph metadata including title, description, image URL, etc.
        """
        self.ensure_one()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # Get image URL
        if self.og_image:
            og_image_url = f"{base_url}/web/image/clinic.appointment.type/{self.id}/og_image"
        else:
            # Fall back to default clinic image
            og_image_url = f"{base_url}/clinic_appointment_web/static/img/default_og_image.jpg"

        # Get booking URL
        booking_url = f"{base_url}/appointments/{self.id}/book"

        return {
            'og:type': 'website',
            'og:site_name': self.env.company.name,
            'og:title': self.og_title or self.name,
            'og:description': self.og_description,
            'og:image': og_image_url,
            'og:image:width': '1200',
            'og:image:height': '630',
            'og:url': booking_url,

            # Twitter Card metadata
            'twitter:card': 'summary_large_image',
            'twitter:title': self.og_title or self.name,
            'twitter:description': self.og_description,
            'twitter:image': og_image_url,

            # Additional metadata
            'description': self.og_description,  # Standard meta description
        }
