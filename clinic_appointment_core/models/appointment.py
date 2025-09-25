# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
from odoo.exceptions import ValidationError, UserError
import pytz


class ClinicAppointment(models.Model):
    """
    Medical Appointment with calendar-like functionality
    Independent model with appointment-specific features
    """
    _name = 'clinic.appointment'
    _description = 'Medical Appointment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'appointment_number'
    _order = 'start desc'

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

    # Override name to auto-generate from patient and service
    name = fields.Char(
        string='Subject',
        compute='_compute_name',
        store=True,
        readonly=False
    )

    # ========================
    # Date and Time Fields
    # ========================
    start = fields.Datetime(
        string='Start',
        required=True,
        tracking=True,
        index=True,
        help='Appointment start date and time'
    )

    stop = fields.Datetime(
        string='End',
        required=True,
        tracking=True,
        help='Appointment end date and time'
    )

    duration = fields.Float(
        string='Duration',
        compute='_compute_duration',
        store=True,
        help='Duration in hours'
    )

    allday = fields.Boolean(
        string='All Day',
        default=False
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

    # Link staff to calendar resource
    resource_id = fields.Many2one(
        'resource.resource',
        string='Resource',
        compute='_compute_resource_id',
        store=True,
        help='Automatically linked to staff resource'
    )

    appointment_type_id = fields.Many2one(
        'clinic.appointment.type',
        string='Appointment Type',
        required=True,
        tracking=True
    )

    service_type = fields.Selection([
        ('medical', 'Medical'),
        ('dental', 'Dental'),
        ('telemed', 'Telemedicine'),
        ('emergency', 'Emergency')
    ], string='Service Type', required=True, default='medical', tracking=True)

    # ========================
    # Location (Using Resources)
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
        tracking=True,
        help='Physical room or facility'
    )

    # ========================
    # Medical Information
    # ========================
    chief_complaint = fields.Text(
        string='Chief Complaint',
        help='Main reason for visit'
    )

    symptoms = fields.Text(
        string='Symptoms',
        help='Patient reported symptoms'
    )

    urgency = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('emergency', 'Emergency')
    ], string='Urgency Level', default='medium', tracking=True)

    # ========================
    # Appointment Status
    # ========================
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('arrived', 'Arrived'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show')
    ], string='Status', default='draft', required=True, tracking=True)

    # ========================
    # Patient Information (Denormalized for quick access)
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
    # Insurance Information
    # ========================
    insurance_flag = fields.Boolean(
        string='Insurance Coverage',
        default=False
    )

    insurance_id = fields.Many2one(
        'clinic.patient.insurance',
        string='Insurance',
        domain="[('patient_id', '=', patient_id), ('is_active', '=', True)]"
    )

    requires_authorization = fields.Boolean(
        string='Requires Authorization'
    )

    insurance_auth_number = fields.Char(
        string='Authorization Number'
    )

    copay_amount = fields.Monetary(
        string='Copay Amount',
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    # ========================
    # Telemedicine Fields
    # ========================
    telemed_platform = fields.Selection([
        ('zoom', 'Zoom'),
        ('teams', 'Microsoft Teams'),
        ('meet', 'Google Meet'),
        ('whatsapp', 'WhatsApp'),
        ('other', 'Other')
    ], string='Platform')

    telemed_link = fields.Char(
        string='Meeting Link',
        help='Video consultation link'
    )

    # ========================
    # Follow-up Management
    # ========================
    is_follow_up = fields.Boolean(
        string='Is Follow-up',
        default=False
    )

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
    arrived_time = fields.Datetime(
        string='Arrived At',
        readonly=True,
        tracking=True
    )

    waiting_time = fields.Float(
        string='Waiting Time (min)',
        compute='_compute_waiting_time',
        store=True
    )

    consultation_start_time = fields.Datetime(
        string='Consultation Started',
        readonly=True
    )

    consultation_end_time = fields.Datetime(
        string='Consultation Ended',
        readonly=True
    )

    consultation_duration = fields.Float(
        string='Consultation Duration (min)',
        compute='_compute_consultation_duration',
        store=True
    )

    # ========================
    # Notification Settings
    # ========================
    reminder_sent = fields.Boolean(
        string='Reminder Sent',
        default=False
    )

    reminder_sent_date = fields.Datetime(
        string='Reminder Sent Date'
    )

    confirmed_by_patient = fields.Boolean(
        string='Patient Confirmed',
        default=False
    )

    confirmation_date = fields.Datetime(
        string='Confirmation Date'
    )

    # ========================
    # Approval Workflow
    # ========================
    requires_approval = fields.Boolean(
        string='Requires Approval',
        compute='_compute_requires_approval',
        store=True
    )

    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True
    )

    approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True
    )

    # ========================
    # Notes
    # ========================
    notes = fields.Text(
        string='Public Notes'
    )

    internal_notes = fields.Text(
        string='Internal Notes'
    )

    # ========================
    # Computed Fields
    # ========================
    @api.depends('patient_id', 'service_type')
    def _compute_name(self):
        for record in self:
            if record.patient_id:
                service = dict(self._fields['service_type'].selection).get(record.service_type, '')
                record.name = f"{record.patient_id.name} - {service}"
            else:
                record.name = _('New Appointment')

    @api.depends('staff_id')
    def _compute_resource_id(self):
        """Link appointment to staff's resource for calendar management"""
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
    # Override Calendar Methods
    # ========================
    @api.depends('start', 'stop')
    def _compute_duration(self):
        for appointment in self:
            if appointment.start and appointment.stop:
                delta = appointment.stop - appointment.start
                appointment.duration = delta.total_seconds() / 3600.0
            else:
                appointment.duration = 0.0

    @api.model
    def search_read_with_prefetch(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Optimized search_read that prefetches related data"""
        # Perform the search
        records = self.search(domain or [], offset=offset, limit=limit, order=order)

        # Prefetch commonly accessed related fields
        if records:
            # Force loading of related records in batch
            records.mapped('patient_id.name')
            records.mapped('staff_id.name')
            records.mapped('branch_id.name')
            records.mapped('appointment_type_id.name')
            records.mapped('prescription_ids')
            records.mapped('treatment_plan_ids')

        # Now do the read with fields already cached
        return records.read(fields)

    @api.model
    def create(self, vals):
        """Override to generate appointment number and set attendees"""
        if vals.get('appointment_number', _('New')) == _('New'):
            vals['appointment_number'] = self.env['ir.sequence'].next_by_code(
                'clinic.appointment') or _('New')

        # Note: Calendar attendees and alarms removed since we're not inheriting calendar.event
        # These features can be re-implemented with custom fields if needed

        return super().create(vals)

    @api.constrains('start', 'stop', 'staff_id')
    def _check_appointment_overlap(self):
        """Check for overlapping appointments for the same staff"""
        for record in self:
            if record.state == 'cancelled':
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
                    "This appointment overlaps with another appointment for %s: %s"
                ) % (record.staff_id.name, overlapping.appointment_number))

    @api.constrains('start', 'stop', 'room_id')
    def _check_room_availability(self):
        """Check if room is available for the time slot"""
        for record in self:
            if not record.room_id or record.state == 'cancelled':
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
                    "Room %s is already booked for this time slot"
                ) % record.room_id.name)

    # ========================
    # Business Logic
    # ========================
    def action_confirm(self):
        """Confirm the appointment"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft appointments can be confirmed'))

        # Check staff availability using resource calendar
        if self.staff_id.resource_calendar_id:
            work_intervals = self.staff_id.resource_calendar_id._work_intervals_batch(
                self.start, self.stop,
                resources=self.staff_id.resource_id
            )[self.staff_id.resource_id.id]

            if not work_intervals:
                raise UserError(_(
                    '%s is not available at this time according to their working schedule'
                ) % self.staff_id.name)

        self.state = 'confirmed'
        self._send_confirmation_email()

    def action_arrive(self):
        """Mark patient as arrived"""
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('Only confirmed appointments can be marked as arrived'))

        self.write({
            'state': 'arrived',
            'arrived_time': fields.Datetime.now()
        })

    def action_start(self):
        """Start consultation"""
        self.ensure_one()
        if self.state != 'arrived':
            raise UserError(_('Patient must be arrived before starting consultation'))

        self.write({
            'state': 'in_progress',
            'consultation_start_time': fields.Datetime.now()
        })

    def action_done(self):
        """Complete appointment"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('Only in-progress appointments can be completed'))

        self.write({
            'state': 'done',
            'consultation_end_time': fields.Datetime.now()
        })

    def action_cancel(self):
        """Cancel appointment"""
        self.ensure_one()
        if self.state in ['done', 'cancelled']:
            raise UserError(_('Cannot cancel completed or already cancelled appointments'))

        self.state = 'cancelled'
        self._send_cancellation_email()

    def action_no_show(self):
        """Mark as no-show"""
        self.ensure_one()
        if self.state not in ['confirmed', 'arrived']:
            raise UserError(_('Invalid state for marking as no-show'))

        self.state = 'no_show'

    def action_reschedule(self):
        """Open wizard to reschedule"""
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

        # Calculate default follow-up date (1 week later)
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

    def action_approve(self):
        """Approve appointment (for emergency cases)"""
        self.ensure_one()
        if not self.requires_approval:
            raise UserError(_('This appointment does not require approval'))

        self.write({
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now()
        })

    # ========================
    # Email Notifications
    # ========================
    def _send_confirmation_email(self):
        """Send confirmation email to patient"""
        template = self.env.ref(
            'clinic_appointment_core.email_template_appointment_confirmation',
            raise_if_not_found=False
        )
        if template and self.patient_email:
            template.send_mail(self.id, force_send=True)
            self.write({
                'reminder_sent': True,
                'reminder_sent_date': fields.Datetime.now()
            })

    def _send_cancellation_email(self):
        """Send cancellation email to patient"""
        template = self.env.ref(
            'clinic_appointment_core.email_template_appointment_cancellation',
            raise_if_not_found=False
        )
        if template and self.patient_email:
            template.send_mail(self.id, force_send=True)

    # ========================
    # Cron Jobs
    # ========================
    @api.model
    def _cron_send_appointment_reminders(self):
        """Send reminders for tomorrow's appointments"""
        tomorrow = date.today() + timedelta(days=1)
        tomorrow_start = datetime.combine(tomorrow, datetime.min.time())
        tomorrow_end = datetime.combine(tomorrow, datetime.max.time())

        appointments = self.search([
            ('start', '>=', tomorrow_start),
            ('start', '<=', tomorrow_end),
            ('state', '=', 'confirmed'),
            ('reminder_sent', '=', False)
        ])

        for appointment in appointments:
            appointment._send_confirmation_email()

    @api.model
    def _cron_mark_no_shows(self):
        """Mark past confirmed appointments as no-show"""
        cutoff_time = fields.Datetime.now() - timedelta(hours=1)

        appointments = self.search([
            ('start', '<', cutoff_time),
            ('state', '=', 'confirmed')
        ])

        for appointment in appointments:
            appointment.action_no_show()

    # ========================
    # Portal Methods
    # ========================
    def get_portal_url(self):
        """Get portal URL for patient access"""
        self.ensure_one()
        return f'/my/appointments/{self.id}'

    # ========================
    # Calendar Integration
    # ========================
    @api.model
    def get_available_slots(self, staff_id, date_from, date_to, duration=30):
        """
        Get available time slots for a staff member
        Uses resource.calendar to respect working hours
        """
        staff = self.env['clinic.staff'].browse(staff_id)
        if not staff.resource_calendar_id:
            raise UserError(_('%s has no working schedule defined') % staff.name)

        slots = []
        current_date = fields.Datetime.from_string(date_from)
        end_date = fields.Datetime.from_string(date_to)

        while current_date <= end_date:
            day_start = current_date.replace(hour=0, minute=0, second=0)
            day_end = current_date.replace(hour=23, minute=59, second=59)

            # Get working intervals from resource calendar
            work_intervals = staff.resource_calendar_id._work_intervals_batch(
                day_start, day_end,
                resources=staff.resource_id
            )[staff.resource_id.id]

            for start, stop, meta in work_intervals:
                current_slot = start
                while current_slot + timedelta(minutes=duration) <= stop:
                    slot_end = current_slot + timedelta(minutes=duration)

                    # Check if slot is available (no existing appointments)
                    existing = self.search_count([
                        ('staff_id', '=', staff_id),
                        ('state', 'not in', ['cancelled', 'no_show']),
                        ('start', '<', slot_end),
                        ('stop', '>', current_slot)
                    ])

                    if not existing:
                        slots.append({
                            'start': current_slot,
                            'stop': slot_end,
                            'available': True
                        })

                    current_slot = slot_end

            current_date += timedelta(days=1)

        return slots