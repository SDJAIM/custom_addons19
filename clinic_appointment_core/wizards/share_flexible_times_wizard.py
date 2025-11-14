# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import secrets
from datetime import timedelta


class ShareFlexibleTimesWizard(models.TransientModel):
    """
    Wizard to share flexible appointment time options with patients (TASK-F3-001)

    Similar to Calendly - allows staff to generate multiple time slot options
    and share a link with patients to choose their preferred time.
    """
    _name = 'clinic.appointment.share.flexible.times.wizard'
    _description = 'Share Flexible Times Wizard'

    # ========================
    # Basic Information
    # ========================
    appointment_type_id = fields.Many2one(
        'clinic.appointment.type',
        string='Appointment Type',
        required=True,
        help='Type of appointment to offer'
    )

    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        help='Patient who will receive the flexible times'
    )

    patient_email = fields.Char(
        string='Patient Email',
        related='patient_id.email',
        readonly=True
    )

    patient_mobile = fields.Char(
        string='Patient Mobile',
        related='patient_id.mobile',
        readonly=True
    )

    staff_id = fields.Many2one(
        'clinic.staff',
        string='Preferred Staff',
        help='Leave empty to show all available staff'
    )

    # ========================
    # Date Range Selection
    # ========================
    date_from = fields.Date(
        string='From Date',
        required=True,
        default=lambda self: fields.Date.today() + timedelta(days=1),
        help='Start date for available slots'
    )

    date_to = fields.Date(
        string='To Date',
        required=True,
        default=lambda self: fields.Date.today() + timedelta(days=14),
        help='End date for available slots'
    )

    # ========================
    # Generated Slots
    # ========================
    slot_ids = fields.Many2many(
        'clinic.appointment.slot',
        'wizard_slot_rel',
        'wizard_id',
        'slot_id',
        string='Available Slots',
        help='Pre-generated slots to choose from'
    )

    selected_slot_count = fields.Integer(
        string='Selected Slots',
        compute='_compute_selected_slot_count'
    )

    # ========================
    # Sharing Options
    # ========================
    send_by_email = fields.Boolean(
        string='Send by Email',
        default=True,
        help='Send link via email'
    )

    send_by_whatsapp = fields.Boolean(
        string='Send by WhatsApp',
        default=False,
        help='Send link via WhatsApp'
    )

    send_by_sms = fields.Boolean(
        string='Send by SMS',
        default=False,
        help='Send link via SMS'
    )

    custom_message = fields.Text(
        string='Custom Message',
        default=lambda self: _('Please select your preferred appointment time from the options below:'),
        help='Message to include with the link'
    )

    # ========================
    # Token & Expiry
    # ========================
    access_token = fields.Char(
        string='Access Token',
        readonly=True,
        copy=False
    )

    token_expires_at = fields.Datetime(
        string='Link Expires At',
        default=lambda self: fields.Datetime.now() + timedelta(days=7),
        required=True,
        help='Link will be valid until this date'
    )

    share_url = fields.Char(
        string='Share URL',
        compute='_compute_share_url',
        help='URL to share with patient'
    )

    # ========================
    # Computed Methods
    # ========================
    @api.depends('slot_ids')
    def _compute_selected_slot_count(self):
        """Count selected slots"""
        for wizard in self:
            wizard.selected_slot_count = len(wizard.slot_ids)

    @api.depends('access_token')
    def _compute_share_url(self):
        """Generate share URL"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for wizard in self:
            if wizard.access_token:
                wizard.share_url = f"{base_url}/appointment/flexible-times/{wizard.access_token}"
            else:
                wizard.share_url = False

    # ========================
    # Constraints
    # ========================
    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        """Validate date range"""
        for wizard in self:
            if wizard.date_from >= wizard.date_to:
                raise ValidationError(
                    _('End date must be after start date.\n\nFrom: %s\nTo: %s') % (
                        wizard.date_from, wizard.date_to
                    )
                )

            # Maximum 30 days range
            days_diff = (wizard.date_to - wizard.date_from).days
            if days_diff > 30:
                raise ValidationError(
                    _('Date range cannot exceed 30 days.\n\nCurrent range: %d days') % days_diff
                )

    @api.constrains('send_by_email', 'send_by_whatsapp', 'send_by_sms')
    def _check_send_method(self):
        """Ensure at least one send method is selected"""
        for wizard in self:
            if not (wizard.send_by_email or wizard.send_by_whatsapp or wizard.send_by_sms):
                raise ValidationError(
                    _('Please select at least one method to send the link:\n'
                      '- Email\n- WhatsApp\n- SMS')
                )

    # ========================
    # Actions
    # ========================
    def action_generate_slots(self):
        """Generate available slots based on criteria"""
        self.ensure_one()

        # Clear existing slots
        self.slot_ids = [(5, 0, 0)]

        # Generate slots using slot engine
        slot_engine = self.env['clinic.appointment.slot.engine']

        slots = slot_engine.generate_slots(
            appointment_type_id=self.appointment_type_id.id,
            start_date=self.date_from,
            end_date=self.date_to,
            staff_id=self.staff_id.id if self.staff_id else None
        )

        # Convert to slot records (temporary for wizard)
        slot_records = []
        for slot_data in slots[:20]:  # Limit to 20 slots
            slot = self.env['clinic.appointment.slot'].create({
                'start': slot_data['start'],
                'end': slot_data['end'],
                'staff_id': slot_data.get('staff_id'),
                'appointment_type_id': self.appointment_type_id.id,
                'is_available': True
            })
            slot_records.append(slot.id)

        self.slot_ids = [(6, 0, slot_records)]

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Slots Generated'),
                'message': _('Found %d available slots. Review and select slots to share.') % len(slot_records),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_share_slots(self):
        """Generate share link and send to patient"""
        self.ensure_one()

        if not self.slot_ids:
            raise ValidationError(_('Please generate and select at least one slot to share.'))

        # Generate access token
        if not self.access_token:
            self.access_token = secrets.token_urlsafe(32)

        # Create share record
        share = self.env['clinic.appointment.flexible.share'].create({
            'appointment_type_id': self.appointment_type_id.id,
            'patient_id': self.patient_id.id,
            'staff_id': self.staff_id.id if self.staff_id else False,
            'slot_ids': [(6, 0, self.slot_ids.ids)],
            'access_token': self.access_token,
            'token_expires_at': self.token_expires_at,
            'custom_message': self.custom_message,
            'share_url': self.share_url,
        })

        # Send notifications
        if self.send_by_email:
            share._send_email()

        if self.send_by_whatsapp:
            share._send_whatsapp()

        if self.send_by_sms:
            share._send_sms()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Link Shared'),
                'message': _('Flexible times link has been sent to the patient.\n\nURL: %s') % self.share_url,
                'type': 'success',
                'sticky': True,
            }
        }


class AppointmentFlexibleShare(models.Model):
    """
    Persistent record of shared flexible times (TASK-F3-001)
    """
    _name = 'clinic.appointment.flexible.share'
    _description = 'Flexible Appointment Times Share'
    _order = 'create_date desc'

    appointment_type_id = fields.Many2one('clinic.appointment.type', required=True, ondelete='restrict')
    patient_id = fields.Many2one('clinic.patient', required=True, ondelete='cascade')
    staff_id = fields.Many2one('clinic.staff', ondelete='set null')

    slot_ids = fields.Many2many('clinic.appointment.slot', string='Shared Slots')

    access_token = fields.Char(required=True, index=True, copy=False)
    token_expires_at = fields.Datetime(required=True)

    custom_message = fields.Text()
    share_url = fields.Char()

    state = fields.Selection([
        ('pending', 'Pending Selection'),
        ('selected', 'Slot Selected'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled')
    ], default='pending', required=True)

    selected_slot_id = fields.Many2one('clinic.appointment.slot', string='Selected Slot')
    appointment_id = fields.Many2one('clinic.appointment', string='Created Appointment')

    views_count = fields.Integer(string='Views', default=0)
    last_viewed_at = fields.Datetime(string='Last Viewed')

    def _send_email(self):
        """Send flexible times link via email"""
        self.ensure_one()
        template = self.env.ref('clinic_appointment_core.email_template_flexible_times', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    def _send_whatsapp(self):
        """Send flexible times link via WhatsApp"""
        self.ensure_one()
        # Integration with WhatsApp module
        if self.patient_id.whatsapp:
            message = f"{self.custom_message}\n\n{self.share_url}"
            self.env['clinic.whatsapp.message'].create({
                'phone': self.patient_id.whatsapp,
                'message_body': message,
                'direction': 'outbound'
            }).action_send()

    def _send_sms(self):
        """Send flexible times link via SMS"""
        self.ensure_one()
        if self.patient_id.mobile:
            short_url = self.share_url[:50] + '...' if len(self.share_url) > 50 else self.share_url
            message = f"Choose your appointment time: {short_url}"
            # SMS sending logic here

    def action_open_share_url(self):
        """Open the public share URL in a new tab.

        This is called by the 'Open Link' button in share_flexible_times_wizard_views.xml.
        """
        self.ensure_one()
        if not self.share_url:
            from odoo.exceptions import UserError
            raise UserError(_("No share URL is defined for this record."))

        return {
            'type': 'ir.actions.act_url',
            'url': self.share_url,
            'target': 'new',
        }
