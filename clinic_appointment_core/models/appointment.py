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
        tracking=True
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

    # ========================
    # Insurance
    # ========================
    insurance_flag = fields.Boolean(string='Insurance Coverage', default=False)

    insurance_id = fields.Many2one(
        'clinic.patient.insurance',
        string='Insurance',
        domain="[('patient_id', '=', patient_id), ('is_active', '=', True)]"
    )

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
    reminder_sent = fields.Boolean(string='Reminder Sent', default=False)
    reminder_sent_date = fields.Datetime(string='Reminder Sent Date')

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
        """Generate secure access token for online booking"""
        self.ensure_one()
        token = secrets.token_urlsafe(32)
        self.access_token = token
        return token

    def get_booking_url(self, action='view'):
        """Get public URL for online booking actions"""
        self.ensure_one()
        if not self.access_token:
            self._generate_access_token()

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/appointment/{action}/{self.id}/{self.access_token}"

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

        # Generate token for online bookings
        if vals.get('booking_method') == 'online' and not vals.get('access_token'):
            vals['access_token'] = secrets.token_urlsafe(32)

        appointment = super().create(vals)

        # Add patient as attendee
        if appointment.patient_id and appointment.patient_id.partner_id:
            appointment.partner_ids = [(4, appointment.patient_id.partner_id.id)]

        # Set organizer
        if appointment.staff_id and appointment.staff_id.user_id and not appointment.user_id:
            appointment.user_id = appointment.staff_id.user_id

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

        return result

    # ========================
    # Constraints
    # ========================
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
        """Cancel appointment"""
        self.ensure_one()
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
        """Send confirmation email with ICS attachment"""
        template = self.env.ref(
            'clinic_appointment_core.email_template_appointment_confirmation',
            raise_if_not_found=False
        )
        if template and self.patient_email:
            # Generate/update ICS attachment
            ics_attachment = self._generate_and_attach_ics()

            # Send email with ICS attachment
            mail_id = template.send_mail(self.id, force_send=True)

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
    # SMS Notifications
    # ========================
    def _send_confirmation_sms(self):
        """Send confirmation SMS"""
        sms_manager = self.env['clinic.appointment.sms.manager'].sudo()
        return sms_manager.send_appointment_confirmation_sms(self)

    def _send_reminder_sms(self):
        """Send reminder SMS"""
        sms_manager = self.env['clinic.appointment.sms.manager'].sudo()
        return sms_manager.send_appointment_reminder_sms(self)

    def _send_cancellation_sms(self):
        """Send cancellation SMS"""
        sms_manager = self.env['clinic.appointment.sms.manager'].sudo()
        return sms_manager.send_appointment_cancelled_sms(self)

    # ========================
    # Cron
    # ========================
    @api.model
    def _cron_send_appointment_reminders(self):
        """Send reminders for tomorrow's appointments"""
        self = self.sudo()
        tomorrow = date.today() + timedelta(days=1)
        tomorrow_start = datetime.combine(tomorrow, datetime.min.time())
        tomorrow_end = datetime.combine(tomorrow, datetime.max.time())

        _logger.info("Starting appointment reminder cron job for %s", tomorrow)

        appointments = self.search([
            ('start', '>=', tomorrow_start),
            ('start', '<=', tomorrow_end),
            ('state', '=', 'confirmed'),
            ('reminder_sent', '=', False)
        ])

        _logger.info("Found %d appointments to send reminders for", len(appointments))

        for appointment in appointments:
            try:
                appointment._send_reminder_email()
                appointment._send_reminder_sms()
                appointment.write({
                    'reminder_sent': True,
                    'reminder_sent_date': fields.Datetime.now()
                })
                _logger.debug("Reminder sent for appointment %s", appointment.appointment_number)
            except Exception as e:
                _logger.error("Failed to send reminder for appointment %s: %s", appointment.appointment_number, e)

        _logger.info("Completed appointment reminder cron job. Processed: %d", len(appointments))

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
