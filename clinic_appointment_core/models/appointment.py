# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
from odoo.exceptions import ValidationError, UserError
import pytz
import secrets
import logging

_logger = logging.getLogger(__name__)


class ClinicAppointment(models.Model):
    """
    Medical Appointment - Enterprise-like with Calendar Integration

    Uses _inherits (delegation pattern) to link to calendar.event.
    Replicates Odoo Enterprise Appointments functionality in Community.

    Key Features:
    - Calendar.event delegation for Google/Outlook sync
    - Stage-based pipeline (like Enterprise)
    - Token-based online booking confirmation/reschedule/cancel
    - Slot-based booking with capacity management
    - Multi-timezone support
    - Questionnaire support
    - Staff assignment modes (round robin, by skill, customer choice)
    """
    _name = 'clinic.appointment'
    _description = 'Medical Appointment'
    _inherits = {'calendar.event': 'event_id'}  # Enterprise uses 'event_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'appointment_number'
    _order = 'start desc'

    # ========================
    # Delegation Link
    # ========================
    event_id = fields.Many2one(
        'calendar.event',
        string='Calendar Event',
        required=True,
        ondelete='cascade',
        help='Link to Odoo calendar event for sync and calendar features'
    )

    # ========================
    # Medical Identification
    # ========================
    appointment_number = fields.Char(
        string='Appointment Number',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'),
        tracking=True
    )

    # ========================
    # Enterprise-like Stage Management
    # ========================
    stage_id = fields.Many2one(
        'clinic.appointment.stage',
        string='Stage',
        required=True,
        tracking=True,
        group_expand='_read_group_stage_ids',
        default=lambda self: self._get_default_stage(),
        index=True
    )

    # Legacy state field for backward compatibility
    state = fields.Selection(
        related='stage_id.stage_type',
        string='Status',
        store=True,
        readonly=True,
        tracking=True,
        index=True  # ⚡ PERFORMANCE: Frequently used in searches
    )

    # ========================
    # Appointment Type & Configuration
    # ========================
    appointment_type_id = fields.Many2one(
        'clinic.appointment.type',
        string='Appointment Type',
        required=True,
        tracking=True,
        index=True
    )

    # Duration fields from type
    default_duration = fields.Float(
        related='appointment_type_id.default_duration',
        string='Default Duration',
        store=True,
        readonly=True
    )

    buffer_before = fields.Float(
        related='appointment_type_id.buffer_before',
        string='Buffer Before',
        store=True,
        readonly=True
    )

    buffer_after = fields.Float(
        related='appointment_type_id.buffer_after',
        string='Buffer After',
        store=True,
        readonly=True
    )

    # ========================
    # Online Booking (Enterprise-like)
    # ========================
    access_token = fields.Char(
        string='Access Token',
        copy=False,
        index=True,
        help='Token for online confirmation/reschedule/cancel without login'
    )

    # Token Expiration (TASK-F1-008)
    access_token_expires_at = fields.Datetime(
        string='Token Expires At',
        copy=False,
        help='Security: Token valid for 7 days from generation'
    )

    booking_method = fields.Selection([
        ('manual', 'Manual'),
        ('online', 'Online Booking'),
        ('portal', 'Customer Portal'),
    ], string='Booking Method', default='manual', tracking=True)

    confirmed_by_customer = fields.Boolean(
        string='Customer Confirmed',
        default=False,
        help='Customer confirmed appointment via token link'
    )

    confirmation_date = fields.Datetime(
        string='Confirmation Date'
    )

    # ========================
    # Questionnaire (Enterprise-like)
    # ========================
    questionnaire_answer_ids = fields.One2many(
        'clinic.appointment.questionnaire.answer',
        'appointment_id',
        string='Questionnaire Answers'
    )

    questionnaire_completed = fields.Boolean(
        string='Questionnaire Completed',
        compute='_compute_questionnaire_completed',
        store=True
    )

    # ========================
    # Medical Relationships
    # ========================
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        tracking=True,
        ondelete='restrict',
        index=True
    )

    # GUESTS (TASK-F2-002)
    allow_guests = fields.Boolean(
        string='Allow Guests',
        related='appointment_type_id.allow_guests',
        store=True,
        help='Indicates if guests are allowed for this appointment type'
    )

    guest_count = fields.Integer(
        string='Number of Guests',
        default=0,
        help='Number of accompanying guests (0-3)'
    )

    guest_names = fields.Text(
        string='Guest Names',
        help='Names of accompanying guests (one per line)'
    )

    staff_id = fields.Many2one(
        'clinic.staff',
        string='Doctor/Dentist',
        required=True,
        tracking=True,
        domain="[('state', '=', 'active')]",
        index=True
    )

    resource_id = fields.Many2one(
        'resource.resource',
        string='Resource',
        compute='_compute_resource_id',
        store=True,
        help='Automatically linked to staff resource'
    )

    service_type = fields.Selection([
        ('medical', 'Medical'),
        ('dental', 'Dental'),
        ('telemed', 'Telemedicine'),
        ('emergency', 'Emergency')
    ], string='Service Type', required=True, default='medical', tracking=True)

    # ========================
    # Location
    # ========================
    branch_id = fields.Many2one(
        'clinic.branch',
        string='Branch',
        required=True,
        tracking=True
    )

    room_id = fields.Many2one(
        'clinic.room',
        string='Room/Facility',
        domain="[('branch_id', '=', branch_id), ('status', '=', 'available')]",
        tracking=True
    )

    # ========================
    # Medical Information
    # ========================
    chief_complaint = fields.Text(string='Chief Complaint')
    symptoms = fields.Text(string='Symptoms')

    urgency = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('emergency', 'Emergency')
    ], string='Urgency Level', default='medium', tracking=True)

    # ========================
    # Patient Information (Denormalized)
    # ========================
    patient_age = fields.Integer(
        string='Age',
        related='patient_id.age',
        store=True
    )

    patient_phone = fields.Char(
        string='Phone',
        related='patient_id.mobile',
        store=True
    )

    patient_email = fields.Char(
        string='Email',
        related='patient_id.email',
        store=True
    )

    # CC Emails for notifications (TASK-F1-005)
    cc_emails = fields.Char(
        string='CC Emails',
        help='Comma-separated email addresses for CC notifications'
    )

    # ========================
    # Insurance
    # ========================
    insurance_flag = fields.Boolean(string='Insurance Coverage', default=False)

    # insurance_id moved to clinic_finance to avoid circular dependency
    # insurance_id = fields.Many2one('clinic.patient.insurance', ...)

    requires_authorization = fields.Boolean(string='Requires Authorization')
    insurance_auth_number = fields.Char(string='Authorization Number')

    copay_amount = fields.Monetary(
        string='Copay Amount',
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    # ========================
    # Telemedicine
    # ========================
    telemed_platform = fields.Selection([
        ('zoom', 'Zoom'),
        ('teams', 'Microsoft Teams'),
        ('meet', 'Google Meet'),
        ('whatsapp', 'WhatsApp'),
        ('other', 'Other')
    ], string='Platform')

    telemed_link = fields.Char(string='Meeting Link')

    # Google Meet Integration (TASK-F3-002)
    google_meet_id = fields.Char(
        string='Google Meet ID',
        copy=False,
        help='Unique identifier for the Google Meet session'
    )

    google_meet_url = fields.Char(
        string='Google Meet URL',
        compute='_compute_google_meet_url',
        store=True,
        help='Full URL for the Google Meet video conference'
    )

    auto_generate_meet = fields.Boolean(
        string='Auto-generate Google Meet',
        default=True,
        help='Automatically generate Google Meet link for telemedicine appointments'
    )

    # ========================
    # Follow-up
    # ========================
    is_follow_up = fields.Boolean(string='Is Follow-up', default=False)

    parent_appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Parent Appointment',
        domain="[('patient_id', '=', patient_id)]"
    )

    follow_up_ids = fields.One2many(
        'clinic.appointment',
        'parent_appointment_id',
        string='Follow-ups'
    )

    follow_up_count = fields.Integer(
        string='Follow-up Count',
        compute='_compute_follow_up_count'
    )

    # ========================
    # Timing Metrics
    # ========================
    arrived_time = fields.Datetime(string='Arrived At', readonly=True, tracking=True)
    waiting_time = fields.Float(
        string='Waiting Time (min)',
        compute='_compute_waiting_time',
        store=True
    )

    consultation_start_time = fields.Datetime(string='Consultation Started', readonly=True)
    consultation_end_time = fields.Datetime(string='Consultation Ended', readonly=True)
    consultation_duration = fields.Float(
        string='Consultation Duration (min)',
        compute='_compute_consultation_duration',
        store=True
    )

    # ========================
    # Notifications
    # ========================
    reminder_sent = fields.Boolean(string='Reminder Sent', default=False)  # Legacy - kept for backward compatibility
    reminder_sent_date = fields.Datetime(string='Reminder Sent Date')  # Legacy - kept for backward compatibility

    # TASK-F1-003: Multiple Reminders Support
    sent_reminder_ids = fields.One2many(
        'clinic.appointment.reminder.sent',
        'appointment_id',
        string='Sent Reminders',
        help='Track which reminders have been sent for this appointment'
    )

    # ========================
    # Approval
    # ========================
    requires_approval = fields.Boolean(
        string='Requires Approval',
        compute='_compute_requires_approval',
        store=True
    )

    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approval_date = fields.Datetime(string='Approval Date', readonly=True)

    # ========================
    # Notes
    # ========================
    notes = fields.Text(string='Public Notes')
    internal_notes = fields.Text(string='Internal Notes')

    # ========================
    # Computed Fields
    # ========================
    @api.model
    def _get_default_stage(self):
        """Get default stage (first draft stage)"""
        return self.env['clinic.appointment.stage'].search(
            [('stage_type', '=', 'draft')], limit=1
        )

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """Support for Kanban group_by stage_id"""
        return stages.search([], order=order)

    @api.depends('questionnaire_answer_ids')
    def _compute_questionnaire_completed(self):
        """Check if all required questions are answered"""
        for record in self:
            if not record.appointment_type_id:
                record.questionnaire_completed = True
                continue

            required_questions = self.env['clinic.appointment.questionnaire.line'].search([
                ('type_id', '=', record.appointment_type_id.id),
                ('required', '=', True),
                ('active', '=', True)
            ])

            if not required_questions:
                record.questionnaire_completed = True
            else:
                answered_questions = record.questionnaire_answer_ids.mapped('question_id')
                record.questionnaire_completed = all(q in answered_questions for q in required_questions)

    def _get_appointment_name(self):
        """Generate appointment name"""
        if self.patient_id:
            service = dict(self._fields['service_type'].selection).get(self.service_type, '')
            return f"{self.patient_id.name} - {service}"
        return _('New Appointment')

    @api.depends('staff_id')
    def _compute_resource_id(self):
        for record in self:
            if record.staff_id and record.staff_id.resource_id:
                record.resource_id = record.staff_id.resource_id
            else:
                record.resource_id = False

    @api.depends('google_meet_id')
    def _compute_google_meet_url(self):
        """Compute full Google Meet URL from ID (TASK-F3-002)"""
        for record in self:
            if record.google_meet_id:
                record.google_meet_url = f"https://meet.google.com/{record.google_meet_id}"
            else:
                record.google_meet_url = False

    @api.depends('urgency', 'service_type')
    def _compute_requires_approval(self):
        for record in self:
            record.requires_approval = (
                record.urgency == 'emergency' or
                record.service_type == 'emergency'
            )

    @api.depends('follow_up_ids')
    def _compute_follow_up_count(self):
        for record in self:
            record.follow_up_count = len(record.follow_up_ids)

    @api.depends('arrived_time', 'consultation_start_time')
    def _compute_waiting_time(self):
        for record in self:
            if record.arrived_time and record.consultation_start_time:
                delta = record.consultation_start_time - record.arrived_time
                record.waiting_time = delta.total_seconds() / 60
            else:
                record.waiting_time = 0

    @api.depends('consultation_start_time', 'consultation_end_time')
    def _compute_consultation_duration(self):
        for record in self:
            if record.consultation_start_time and record.consultation_end_time:
                delta = record.consultation_end_time - record.consultation_start_time
                record.consultation_duration = delta.total_seconds() / 60
            else:
                record.consultation_duration = 0

    # ========================
    # Onchange Methods
    # ========================
    @api.onchange('patient_id', 'appointment_type_id', 'service_type')
    def _onchange_update_name(self):
        """Update calendar subject"""
        self.name = self._get_appointment_name()

    @api.onchange('staff_id')
    def _onchange_staff_user(self):
        """Link calendar to staff user"""
        if self.staff_id and self.staff_id.user_id:
            self.user_id = self.staff_id.user_id

    # ========================
    # Token Management (Enterprise-like)
    # ========================
    def _generate_access_token(self):
        """Generate secure access token with expiration (TASK-F1-008)"""
        self.ensure_one()
        token = secrets.token_urlsafe(32)
        expires_at = fields.Datetime.now() + timedelta(days=7)  # 7 days validity
        self.write({
            'access_token': token,
            'access_token_expires_at': expires_at
        })
        return token

    def _verify_token(self, token):
        """Verify token validity (existence + expiration check)"""
        self.ensure_one()
        # Check token matches
        if not self.access_token or self.access_token != token:
            return False
        # Check expiration (TASK-F1-008)
        if self.access_token_expires_at and self.access_token_expires_at < fields.Datetime.now():
            return False
        return True

    def get_booking_url(self, action='view'):
        """Get public URL for online booking actions"""
        self.ensure_one()
        if not self.access_token:
            self._generate_access_token()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/appointment/{action}/{self.id}/{self.access_token}"

    def _generate_google_meet_id(self):
        """
        Generate unique Google Meet ID (TASK-F3-002)

        Note: This generates a meet-style ID format.
        For full Google Calendar API integration with proper meet.google.com links,
        you would need:
        1. OAuth2 credentials configured in Odoo
        2. Google Calendar API enabled
        3. Service account or user consent

        This implementation creates a valid meet-style ID that can be used
        as a placeholder or with manual meet creation.

        Returns:
            str: Google Meet ID in format xxx-yyyy-zzz
        """
        import string
        import random

        # Generate 3 groups of random characters (Google Meet format: xxx-yyyy-zzz)
        chars = string.ascii_lowercase + string.digits
        part1 = ''.join(random.choices(chars, k=3))
        part2 = ''.join(random.choices(chars, k=4))
        part3 = ''.join(random.choices(chars, k=3))

        return f"{part1}-{part2}-{part3}"

    def action_generate_google_meet(self):
        """
        Manually generate/regenerate Google Meet link (TASK-F3-002)

        Can be called from button action to generate or refresh the Meet link.
        """
        self.ensure_one()

        if self.service_type != 'telemed':
            raise ValidationError(
                _('Google Meet links can only be generated for Telemedicine appointments.')
            )

        # Generate new Meet ID
        meet_id = self._generate_google_meet_id()

        self.write({
            'telemed_platform': 'meet',
            'google_meet_id': meet_id,
            'telemed_link': f"https://meet.google.com/{meet_id}"
        })

        # Send notification to patient with new link
        if self.patient_id.email:
            self._send_meet_link_email()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Google Meet Link Generated'),
                'message': _('Meeting link: %s') % self.google_meet_url,
                'type': 'success',
                'sticky': True,
            }
        }

    def _send_meet_link_email(self):
        """Send Google Meet link to patient via email (TASK-F3-002)"""
        self.ensure_one()

        if not self.patient_id.email:
            return

        template = self.env.ref(
            'clinic_appointment_core.email_template_google_meet_link',
            raise_if_not_found=False
        )

        if template:
            template.send_mail(self.id, force_send=True)

    # ========================
    # CRUD
    # ========================
    @api.model
    def create(self, vals):
        """Create with sequence and token generation"""
        if vals.get('appointment_number', _('New')) == _('New'):
            vals['appointment_number'] = self.env['ir.sequence'].next_by_code(
                'clinic.appointment') or _('New')

        # Set name if not provided
        if not vals.get('name'):
            patient_id = vals.get('patient_id')
            service_type = vals.get('service_type', 'medical')
            if patient_id:
                patient = self.env['clinic.patient'].browse(patient_id)
                service = dict(self._fields['service_type'].selection).get(service_type, '')
                vals['name'] = f"{patient.name} - {service}"
            else:
                vals['name'] = _('New Appointment')

        # Generate token for online bookings (TASK-F1-008: with expiration)
        if vals.get('booking_method') == 'online' and not vals.get('access_token'):
            vals['access_token'] = secrets.token_urlsafe(32)
            vals['access_token_expires_at'] = fields.Datetime.now() + timedelta(days=7)

        # Generate Google Meet link for telemedicine (TASK-F3-002)
        if (vals.get('service_type') == 'telemed' and
            vals.get('telemed_platform') == 'meet' and
            vals.get('auto_generate_meet', True) and
            not vals.get('google_meet_id')):
            meet_id = self._generate_google_meet_id()
            vals['google_meet_id'] = meet_id
            vals['telemed_link'] = f"https://meet.google.com/{meet_id}"

        appointment = super().create(vals)

        # Add patient as attendee
        if appointment.patient_id and appointment.patient_id.partner_id:
            appointment.partner_ids = [(4, appointment.patient_id.partner_id.id)]

        # Set organizer
        if appointment.staff_id and appointment.staff_id.user_id and not appointment.user_id:
            appointment.user_id = appointment.staff_id.user_id

        # ⚡ CACHE INVALIDATION (P0-003): Clear slot engine cache when appointment is created
        self.env['clinic.appointment.slot.engine']._invalidate_slot_cache()

        return appointment

    def write(self, vals):
        """Update name on patient/service change"""
        result = super().write(vals)

        if 'patient_id' in vals or 'service_type' in vals:
            for appointment in self:
                appointment.name = appointment._get_appointment_name()

        # Auto-send stage email
        if 'stage_id' in vals:
            for appointment in self:
                if appointment.stage_id.send_email and appointment.stage_id.mail_template_id:
                    appointment.stage_id.mail_template_id.send_mail(appointment.id, force_send=True)

        # ⚡ CACHE INVALIDATION (P0-003): Clear slot engine cache when appointment is modified
        # (especially if start/stop/staff_id/state changed)
        if any(key in vals for key in ['start', 'stop', 'staff_id', 'state', 'stage_id']):
            self.env['clinic.appointment.slot.engine']._invalidate_slot_cache()

        return result

    def unlink(self):
        """Delete appointment and invalidate cache"""
        # ⚡ CACHE INVALIDATION (P0-003): Clear slot engine cache before deletion
        self.env['clinic.appointment.slot.engine']._invalidate_slot_cache()

        return super().unlink()

    # ========================
    # Constraints
    # ========================
    @api.constrains('cc_emails')
    def _check_cc_emails_format(self):
        """Validate CC emails format (TASK-F1-005)"""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        for appointment in self:
            if appointment.cc_emails:
                emails = [e.strip() for e in appointment.cc_emails.split(',') if e.strip()]
                for email in emails:
                    if not re.match(email_pattern, email):
                        raise ValidationError(
                            _('Invalid email format in CC: %s') % email
                        )

    @api.constrains('start', 'stop', 'staff_id')
    def _check_appointment_overlap(self):
        """Check staff availability"""
        for record in self:
            if record.state in ['cancelled', 'no_show']:
                continue

            domain = [
                ('id', '!=', record.id),
                ('staff_id', '=', record.staff_id.id),
                ('state', 'not in', ['cancelled', 'no_show']),
                '|',
                '&', ('start', '>=', record.start), ('start', '<', record.stop),
                '&', ('stop', '>', record.start), ('stop', '<=', record.stop)
            ]

            overlapping = self.search(domain, limit=1)
            if overlapping:
                raise ValidationError(_(
                    "Appointment overlaps with %s: %s"
                ) % (record.staff_id.name, overlapping.appointment_number))

    @api.constrains('start', 'stop', 'room_id')
    def _check_room_availability(self):
        """Check room availability"""
        for record in self:
            if not record.room_id or record.state in ['cancelled', 'no_show']:
                continue

            domain = [
                ('id', '!=', record.id),
                ('room_id', '=', record.room_id.id),
                ('state', 'not in', ['cancelled', 'no_show']),
                '|',
                '&', ('start', '>=', record.start), ('start', '<', record.stop),
                '&', ('stop', '>', record.start), ('stop', '<=', record.stop)
            ]

            overlapping = self.search(domain, limit=1)
            if overlapping:
                raise ValidationError(_(
                    "Room %s is already booked"
                ) % record.room_id.name)

    @api.constrains('guest_count', 'appointment_type_id')
    def _check_guest_capacity(self):
        """
        Validate guest capacity (TASK-F2-002)

        Ensures:
        1. Guest count is non-negative
        2. Total people (patient + guests) doesn't exceed slot capacity
        3. Guest count doesn't exceed maximum allowed guests
        """
        for record in self:
            # Check guest count is non-negative
            if record.guest_count < 0:
                raise ValidationError(
                    _('Guest count cannot be negative.\n\nGuest count: %d') % record.guest_count
                )

            # Check guests are allowed for this appointment type
            if record.guest_count > 0 and not record.allow_guests:
                raise ValidationError(
                    _('Guests are not allowed for this appointment type.\n\n'
                      'Appointment Type: %s\n'
                      'Guest Count: %d') % (record.appointment_type_id.name, record.guest_count)
                )

            # Check total capacity (patient + guests)
            if record.appointment_type_id:
                total_people = 1 + record.guest_count  # Patient + guests
                max_capacity = record.appointment_type_id.capacity_per_slot

                if total_people > max_capacity:
                    raise ValidationError(
                        _('Total number of people exceeds slot capacity.\n\n'
                          'Total People: %d (1 patient + %d guests)\n'
                          'Maximum Capacity: %d\n\n'
                          'Please reduce the number of guests.') % (
                              total_people, record.guest_count, max_capacity
                          )
                    )

                # Check maximum guests limit
                max_guests = record.appointment_type_id.max_guests
                if record.guest_count > max_guests:
                    raise ValidationError(
                        _('Number of guests exceeds the maximum allowed.\n\n'
                          'Guests: %d\n'
                          'Maximum Allowed: %d') % (record.guest_count, max_guests)
                    )

    # ========================
    # Business Logic
    # ========================
    def action_confirm(self):
        """Confirm appointment"""
        self.ensure_one()
        confirmed_stage = self.env['clinic.appointment.stage'].search(
            [('stage_type', '=', 'confirmed')], limit=1
        )
        if confirmed_stage:
            self.stage_id = confirmed_stage
            self._send_confirmation_email()
            self._send_confirmation_sms()

    def action_start(self):
        """Start consultation - mark as in_progress"""
        self.ensure_one()
        self.write({
            'consultation_start_time': fields.Datetime.now()
        })

    def action_done(self):
        """Complete appointment"""
        self.ensure_one()
        done_stage = self.env['clinic.appointment.stage'].search(
            [('stage_type', '=', 'done')], limit=1
        )
        if done_stage:
            self.write({
                'stage_id': done_stage.id,
                'consultation_end_time': fields.Datetime.now()
            })

    def action_cancel(self):
        """
        Cancel appointment with deadline enforcement (TASK-F2-007)

        Raises:
            UserError: If cancellation deadline has passed
        """
        self.ensure_one()

        # ⚠️ DEADLINE ENFORCEMENT (TASK-F2-007)
        appt_type = self.appointment_type_id

        if appt_type.allow_cancel:
            # Calculate hours until appointment
            hours_until = (self.start - fields.Datetime.now()).total_seconds() / 3600

            # Check if within deadline
            if hours_until < appt_type.cancel_limit_hours:
                raise UserError(
                    _('Cancellation deadline has passed.\n\n'
                      'This appointment requires cancellation at least %d hours in advance.\n'
                      'Time remaining: %.1f hours\n\n'
                      'Please contact the clinic directly.') % (
                          appt_type.cancel_limit_hours,
                          hours_until
                      )
                )
        else:
            # Cancellation not allowed at all
            raise UserError(
                _('Cancellation is not allowed for this appointment type.\n\n'
                  'Please contact the clinic directly.')
            )

        # Proceed with cancellation
        cancelled_stage = self.env['clinic.appointment.stage'].search(
            [('stage_type', '=', 'cancelled')], limit=1
        )
        if cancelled_stage:
            self.stage_id = cancelled_stage
            self._send_cancellation_email()
            self._send_cancellation_sms()

    def action_no_show(self):
        """Mark as no-show"""
        self.ensure_one()
        no_show_stage = self.env['clinic.appointment.stage'].search(
            [('stage_type', '=', 'no_show')], limit=1
        )
        if no_show_stage:
            self.stage_id = no_show_stage

    def action_reschedule(self):
        """Open reschedule wizard"""
        self.ensure_one()
        return {
            'name': _('Reschedule Appointment'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.appointment.reschedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_appointment_id': self.id}
        }

    def action_create_follow_up(self):
        """Create follow-up appointment"""
        self.ensure_one()
        follow_up_date = self.start + timedelta(days=7)

        return {
            'name': _('Schedule Follow-up'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.appointment',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_staff_id': self.staff_id.id,
                'default_branch_id': self.branch_id.id,
                'default_is_follow_up': True,
                'default_parent_appointment_id': self.id,
                'default_start': follow_up_date,
                'default_service_type': self.service_type,
            }
        }

    # ========================
    # Email & ICS
    # ========================
    def _generate_and_attach_ics(self):
        """Generate ICS file and attach to appointment"""
        self.ensure_one()
        ics_generator = self.env['clinic.appointment.ics.generator'].sudo()
        return ics_generator.update_ics_attachment(self)

    def _send_confirmation_email(self):
        """Send confirmation email with ICS attachment (and CC if provided)"""
        template = self.env.ref(
            'clinic_appointment_core.email_template_appointment_confirmation',
            raise_if_not_found=False
        )
        if template and self.patient_email:
            # Generate/update ICS attachment
            ics_attachment = self._generate_and_attach_ics()

            # Prepare context with CC emails (TASK-F1-005)
            ctx = dict(self.env.context)
            if self.cc_emails:
                ctx['email_cc'] = self.cc_emails

            # Send email with ICS attachment
            mail_id = template.with_context(ctx).send_mail(self.id, force_send=True)

            # Attach ICS to email
            if mail_id and ics_attachment:
                mail = self.env['mail.mail'].sudo().browse(mail_id)
                if mail.exists():
                    mail.write({
                        'attachment_ids': [(4, ics_attachment.id)]
                    })

            self.write({
                'reminder_sent': True,
                'reminder_sent_date': fields.Datetime.now()
            })

    def _send_reminder_email(self):
        """Send reminder email with ICS attachment"""
        template = self.env.ref(
            'clinic_appointment_core.email_template_appointment_reminder',
            raise_if_not_found=False
        )
        if template and self.patient_email:
            # Update ICS attachment
            ics_attachment = self._generate_and_attach_ics()

            # Send email
            mail_id = template.send_mail(self.id, force_send=True)

            # Attach ICS to email
            if mail_id and ics_attachment:
                mail = self.env['mail.mail'].sudo().browse(mail_id)
                if mail.exists():
                    mail.write({
                        'attachment_ids': [(4, ics_attachment.id)]
                    })

    def _send_cancellation_email(self):
        """Send cancellation email"""
        template = self.env.ref(
            'clinic_appointment_core.email_template_appointment_cancellation',
            raise_if_not_found=False
        )
        if template and self.patient_email:
            template.send_mail(self.id, force_send=True)

    def _send_rescheduled_email(self):
        """Send rescheduled email with updated ICS attachment"""
        template = self.env.ref(
            'clinic_appointment_core.email_template_appointment_rescheduled',
            raise_if_not_found=False
        )
        if template and self.patient_email:
            # Update ICS attachment with new times
            ics_attachment = self._generate_and_attach_ics()

            # Send email
            mail_id = template.send_mail(self.id, force_send=True)

            # Attach updated ICS to email
            if mail_id and ics_attachment:
                mail = self.env['mail.mail'].sudo().browse(mail_id)
                if mail.exists():
                    mail.write({
                        'attachment_ids': [(4, ics_attachment.id)]
                    })

    # ========================
    # SMS Notifications (TASK-F1-006: Migrated to Odoo CE's sms module)
    # ========================
    def _send_confirmation_sms(self):
        """Send confirmation SMS using Odoo CE's sms.template"""
        self.ensure_one()
        if not self.patient_phone:
            _logger.warning("Cannot send confirmation SMS for appointment %s: no phone number", self.appointment_number)
            return False

        template = self.env.ref('clinic_appointment_core.sms_template_appointment_confirmation', raise_if_not_found=False)
        if template:
            return self._message_sms_with_template(
                template=template,
                partner_ids=self.patient_id.partner_id.ids if self.patient_id.partner_id else False,
                number_field='patient_phone',
            )
        return False

    def _send_reminder_sms(self):
        """Send reminder SMS using Odoo CE's sms.template"""
        self.ensure_one()
        if not self.patient_phone:
            _logger.warning("Cannot send reminder SMS for appointment %s: no phone number", self.appointment_number)
            return False

        template = self.env.ref('clinic_appointment_core.sms_template_appointment_reminder', raise_if_not_found=False)
        if template:
            return self._message_sms_with_template(
                template=template,
                partner_ids=self.patient_id.partner_id.ids if self.patient_id.partner_id else False,
                number_field='patient_phone',
            )
        return False

    def _send_cancellation_sms(self):
        """Send cancellation SMS using Odoo CE's sms.template"""
        self.ensure_one()
        if not self.patient_phone:
            _logger.warning("Cannot send cancellation SMS for appointment %s: no phone number", self.appointment_number)
            return False

        template = self.env.ref('clinic_appointment_core.sms_template_appointment_cancelled', raise_if_not_found=False)
        if template:
            return self._message_sms_with_template(
                template=template,
                partner_ids=self.patient_id.partner_id.ids if self.patient_id.partner_id else False,
                number_field='patient_phone',
            )
        return False

    # ========================
    # Cron
    # ========================
    @api.model
    def _cron_send_appointment_reminders(self):
        """
        TASK-F1-003: Send multiple reminders based on reminder configurations
        Checks all future appointments and sends reminders according to their type's reminder_ids
        """
        self = self.sudo()
        now = fields.Datetime.now()

        # Get all future confirmed appointments (next 30 days)
        future_limit = now + timedelta(days=30)
        appointments = self.search([
            ('start', '>', now),
            ('start', '<=', future_limit),
            ('state', '=', 'confirmed'),
        ])

        _logger.info("Starting appointment reminder cron job. Checking %d appointments", len(appointments))

        reminders_sent_count = 0

        for appointment in appointments:
            # Get reminder configurations for this appointment type
            reminder_configs = appointment.appointment_type_id.reminder_ids.filtered(lambda r: r.active)

            if not reminder_configs:
                continue  # No reminders configured for this type

            # Calculate time until appointment
            time_until_appointment = appointment.start - now
            hours_until = time_until_appointment.total_seconds() / 3600

            for config in reminder_configs:
                # Check if it's time to send this reminder (within 1 hour window)
                # Allow 1-hour tolerance to account for cron frequency
                if not (config.hours_before - 1 <= hours_until <= config.hours_before + 1):
                    continue  # Not time yet or already passed

                # Check if this reminder has already been sent
                already_sent = appointment.sent_reminder_ids.filtered(
                    lambda r: r.reminder_config_id == config and r.status == 'success'
                )
                if already_sent:
                    continue  # Already sent this reminder

                # Send reminder based on channel
                try:
                    success = False
                    error_msg = None
                    mail_msg_id = sms_msg_id = whatsapp_msg_id = None

                    if config.channel == 'email':
                        mail_msg_id = self._send_reminder_by_email(appointment, config)
                        success = bool(mail_msg_id)
                    elif config.channel == 'sms':
                        sms_msg_id = self._send_reminder_by_sms(appointment, config)
                        success = bool(sms_msg_id)
                    elif config.channel == 'whatsapp':
                        whatsapp_msg_id = self._send_reminder_by_whatsapp(appointment, config)
                        success = bool(whatsapp_msg_id)

                    # Log the sent reminder
                    self.env['clinic.appointment.reminder.sent'].create({
                        'appointment_id': appointment.id,
                        'reminder_config_id': config.id,
                        'sent_date': fields.Datetime.now(),
                        'status': 'success' if success else 'failed',
                        'error_message': error_msg,
                        'mail_message_id': mail_msg_id,
                        'sms_message_id': sms_msg_id,
                        'whatsapp_message_id': whatsapp_msg_id,
                    })

                    if success:
                        reminders_sent_count += 1
                        _logger.info("Reminder sent for appointment %s: %s channel, %d hours before",
                                   appointment.appointment_number, config.channel, config.hours_before)
                    else:
                        _logger.warning("Failed to send reminder for appointment %s: %s channel",
                                      appointment.appointment_number, config.channel)

                except Exception as e:
                    _logger.error("Error sending reminder for appointment %s: %s",
                                appointment.appointment_number, str(e))
                    # Log the failed attempt
                    self.env['clinic.appointment.reminder.sent'].create({
                        'appointment_id': appointment.id,
                        'reminder_config_id': config.id,
                        'sent_date': fields.Datetime.now(),
                        'status': 'failed',
                        'error_message': str(e),
                    })

        _logger.info("Completed appointment reminder cron job. Sent %d reminders", reminders_sent_count)
        return True

    def _send_reminder_by_email(self, appointment, config):
        """Send email reminder using template from config or default"""
        template = config.email_template_id or self.env.ref(
            'clinic_appointment_core.email_template_appointment_reminder',
            raise_if_not_found=False
        )
        if template and appointment.patient_email:
            mail_id = template.send_mail(appointment.id, force_send=True)
            return mail_id
        return None

    def _send_reminder_by_sms(self, appointment, config):
        """
        Send SMS reminder using template from config or default
        TASK-F1-006: Updated to use Odoo CE's sms.template
        """
        # Use template from config if specified, otherwise use default
        template = config.sms_template_id or self.env.ref(
            'clinic_appointment_core.sms_template_appointment_reminder',
            raise_if_not_found=False
        )

        if not template or not appointment.patient_phone:
            return None

        # Send SMS and return the created sms.sms record ID
        sms_message = appointment._message_sms_with_template(
            template=template,
            partner_ids=appointment.patient_id.partner_id.ids if appointment.patient_id.partner_id else False,
            number_field='patient_phone',
        )

        # Return the ID of the first SMS record created
        if sms_message and hasattr(sms_message, 'id'):
            return sms_message.id
        return None

    def _send_reminder_by_whatsapp(self, appointment, config):
        """
        Send WhatsApp reminder using template from config
        TASK-F1-009: Implemented with template variable substitution
        """
        if not config.whatsapp_template_id:
            _logger.warning("No WhatsApp template configured for reminder config %s", config.id)
            return None

        if not appointment.patient_phone:
            _logger.warning("Patient has no phone for appointment %s", appointment.appointment_number)
            return None

        template = config.whatsapp_template_id

        # Prepare template parameters using appointment data
        template_params = self._get_whatsapp_template_params(appointment)

        # Render template with parameters
        try:
            rendered_body = template.render_template(**template_params)
        except Exception as e:
            _logger.error("Failed to render WhatsApp template for appointment %s: %s",
                         appointment.appointment_number, str(e))
            return None

        # Create WhatsApp message
        try:
            whatsapp_message = self.env['clinic.whatsapp.message'].sudo().create({
                'patient_id': appointment.patient_id.id,
                'phone_number': appointment.patient_phone,
                'message_type': 'template',
                'template_id': template.id,
                'message_body': rendered_body,  # Rendered body for preview/logging
                'appointment_id': appointment.id,
                'category': 'appointment_reminder',
                'priority': 'normal',
                'state': 'queued',  # Will be sent by cron
            })

            _logger.info("Created WhatsApp reminder for appointment %s: message ID %s",
                        appointment.appointment_number, whatsapp_message.id)
            return whatsapp_message.id

        except Exception as e:
            _logger.error("Failed to create WhatsApp message for appointment %s: %s",
                         appointment.appointment_number, str(e))
            return None

    def _get_whatsapp_template_params(self, appointment):
        """
        Get template parameters for WhatsApp template rendering
        TASK-F1-009: Maps appointment data to template placeholders

        Returns:
            dict: Parameters for template.render_template()
        """
        params = {
            'patient_name': appointment.patient_id.name,
            'appointment_date': appointment.start.strftime('%B %d, %Y'),
            'appointment_time': appointment.start.strftime('%I:%M %p'),
            'doctor_name': appointment.staff_id.name if appointment.staff_id else 'your provider',
            'appointment_type': appointment.appointment_type_id.name,
            'location': appointment.branch_id.name if appointment.branch_id else 'our clinic',
            'confirmation_number': appointment.appointment_number,
        }

        # Add optional booking URL if available
        if hasattr(appointment, 'get_booking_url') and callable(appointment.get_booking_url):
            try:
                params['booking_url'] = appointment.get_booking_url('view')
            except:
                params['booking_url'] = ''

        return params

    @api.model
    def _cron_mark_no_shows(self):
        """Mark past confirmed appointments as no-show"""
        self = self.sudo()
        cutoff_time = fields.Datetime.now() - timedelta(hours=1)

        _logger.info("Starting no-show marking cron job with cutoff time: %s", cutoff_time)

        appointments = self.search([
            ('start', '<', cutoff_time),
            ('state', '=', 'confirmed')
        ])

        _logger.info("Found %d appointments to mark as no-show", len(appointments))

        for appointment in appointments:
            try:
                appointment.action_no_show()
                _logger.debug("Marked appointment %s as no-show", appointment.appointment_number)
            except Exception as e:
                _logger.error("Failed to mark appointment %s as no-show: %s", appointment.appointment_number, e)

        _logger.info("Completed no-show marking cron job. Processed: %d", len(appointments))

    # ========================
    # Portal
    # ========================
    def get_portal_url(self):
        """Get portal URL"""
        self.ensure_one()
        return f'/my/appointments/{self.id}'
