# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
from odoo.exceptions import ValidationError, UserError
import pytz


class ClinicAppointment(models.Model):
    """
    Medical Appointment - Delegates to Odoo Calendar Event

    Uses _inherits (delegation pattern) to link to calendar.event.
    This creates a clinic.appointment record with its own table,
    while delegating calendar functionality to a linked calendar.event.

    Benefits:
    - Appears in Odoo Calendar app
    - Google Calendar / Outlook sync
    - Automatic reminders (calendar.alarm)
    - Free/busy calculation
    - Recurring appointments support
    - Clean separation: clinic fields in clinic table, calendar fields in calendar table

    Technical Note:
    - _inherits creates delegation (composition pattern)
    - Creates calendar_event_id Many2one link
    - All calendar.event fields are accessible via delegation
    - No Many2many field conflicts
    """
    _name = 'clinic.appointment'
    _description = 'Medical Appointment'
    _inherits = {'calendar.event': 'calendar_event_id'}  # Delegation pattern
    _inherit = ['mail.thread', 'mail.activity.mixin']    # Mixin inheritance
    _rec_name = 'appointment_number'
    _order = 'start desc'

    # ========================
    # Delegation Link (Required for _inherits)
    # ========================
    calendar_event_id = fields.Many2one(
        'calendar.event',
        string='Calendar Event',
        required=True,
        ondelete='cascade',
        auto_join=True,
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

    # Note: 'name' field comes from calendar.event via _inherits
    # We set it in the create() method instead of using compute
    # to avoid conflicts with delegated fields

    # ========================
    # Delegated Fields from calendar.event (via _inherits)
    # ========================
    # These fields are accessible directly but stored in calendar.event:
    # - start, stop, duration, allday (date/time management)
    # - categ_ids (categories/tags)
    # - partner_ids (attendees)
    # - alarm_ids (reminders)
    # - recurrency, rrule (recurring appointments)
    # - location, videocall_location
    # - description, privacy
    # - user_id (organizer)
    #
    # With _inherits, you can read/write these fields as if they were local,
    # but they're stored in the linked calendar.event record.
    # This prevents table conflicts and keeps data normalized.

    # ========================
    # Medical Relationships (NEW fields specific to clinic)
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
    def _get_appointment_name(self):
        """Helper method to generate appointment name"""
        if self.patient_id:
            service = dict(self._fields['service_type'].selection).get(self.service_type, '')
            return f"{self.patient_id.name} - {service}"
        return _('New Appointment')

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
    # Onchange Methods (Calendar Integration)
    # ========================
    @api.onchange('patient_id', 'appointment_type_id', 'service_type')
    def _onchange_update_name(self):
        """Update calendar subject when patient or type changes"""
        self.name = self._get_appointment_name()

    @api.onchange('staff_id')
    def _onchange_staff_user(self):
        """Link calendar event to staff user for calendar ownership"""
        if self.staff_id and self.staff_id.user_id:
            self.user_id = self.staff_id.user_id

    # ========================
    # Calendar Integration Methods
    # ========================
    # duration is automatically computed by calendar.event from start/stop
    # No need to override _compute_duration

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
        """
        Override to generate appointment number and create linked calendar event.

        With _inherits, Odoo automatically creates the calendar.event record
        when we create clinic.appointment. We just need to set up additional
        relationships.
        """
        if vals.get('appointment_number', _('New')) == _('New'):
            vals['appointment_number'] = self.env['ir.sequence'].next_by_code(
                'clinic.appointment') or _('New')

        # Set name if not provided (will be stored in calendar.event via _inherits)
        if not vals.get('name'):
            # Get patient and service_type to generate name
            patient_id = vals.get('patient_id')
            service_type = vals.get('service_type', 'medical')
            if patient_id:
                patient = self.env['clinic.patient'].browse(patient_id)
                service = dict(self._fields['service_type'].selection).get(service_type, '')
                vals['name'] = f"{patient.name} - {service}"
            else:
                vals['name'] = _('New Appointment')

        # Create appointment (this will auto-create calendar.event via _inherits)
        appointment = super().create(vals)

        # Add patient as calendar attendee (for email notifications and calendar sync)
        if appointment.patient_id and appointment.patient_id.partner_id:
            appointment.partner_ids = [(4, appointment.patient_id.partner_id.id)]

        # Add staff user as organizer if not already set
        if appointment.staff_id and appointment.staff_id.user_id and not appointment.user_id:
            appointment.user_id = appointment.staff_id.user_id

        return appointment

    def write(self, vals):
        """Override write to update name when patient or service_type changes"""
        result = super().write(vals)

        # Update name if patient_id or service_type changed
        if 'patient_id' in vals or 'service_type' in vals:
            for appointment in self:
                appointment.name = appointment._get_appointment_name()

        return result

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