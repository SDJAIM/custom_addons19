# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)


class TelemedicineSession(models.Model):
    _name = 'clinic.telemed.session'
    _description = 'Telemedicine Session'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'session_date desc'
    _rec_name = 'display_name'

    # Basic Information
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Related Appointment',
        required=True,
        tracking=True,
        ondelete='cascade'
    )

    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        related='appointment_id.patient_id',
        store=True,
        readonly=True
    )

    doctor_id = fields.Many2one(
        'clinic.staff',
        string='Doctor',
        related='appointment_id.staff_id',
        store=True,
        readonly=True
    )

    # Session Details
    session_date = fields.Datetime(
        string='Session Date',
        required=True,
        tracking=True,
        default=fields.Datetime.now
    )

    duration_minutes = fields.Integer(
        string='Duration (minutes)',
        default=30,
        required=True
    )

    session_end_date = fields.Datetime(
        string='Session End',
        compute='_compute_session_end_date',
        store=True
    )

    # Discuss Integration
    discuss_channel_id = fields.Many2one(
        'discuss.channel',
        string='Video Call Channel',
        help='Discuss channel for video consultation',
        tracking=True
    )

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('waiting', 'In Waiting Room'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True)

    # Participants
    patient_joined = fields.Boolean(
        string='Patient Joined',
        default=False
    )

    doctor_joined = fields.Boolean(
        string='Doctor Joined',
        default=False
    )

    patient_join_time = fields.Datetime(
        string='Patient Join Time',
        readonly=True
    )

    doctor_join_time = fields.Datetime(
        string='Doctor Join Time',
        readonly=True
    )

    # Recording
    recording_enabled = fields.Boolean(
        string='Recording Enabled',
        default=False,
        help='Enable session recording (if supported by configuration)'
    )

    # Notes
    session_notes = fields.Text(
        string='Session Notes',
        help='Private notes about the session'
    )

    # Invitations
    invitation_sent = fields.Boolean(
        string='Invitation Sent',
        default=False
    )

    invitation_sent_date = fields.Datetime(
        string='Invitation Sent Date',
        readonly=True
    )

    @api.depends('patient_id', 'doctor_id', 'session_date')
    def _compute_display_name(self):
        for session in self:
            parts = []
            if session.patient_id:
                parts.append(session.patient_id.name)
            if session.doctor_id:
                parts.append(f"Dr. {session.doctor_id.name}")
            if session.session_date:
                parts.append(session.session_date.strftime('%Y-%m-%d %H:%M'))
            session.display_name = ' - '.join(parts) if parts else 'New Session'

    @api.depends('session_date', 'duration_minutes')
    def _compute_session_end_date(self):
        for session in self:
            if session.session_date and session.duration_minutes:
                session.session_end_date = session.session_date + timedelta(minutes=session.duration_minutes)
            else:
                session.session_end_date = False

    def action_create_video_channel(self):
        """Create Discuss channel with video call capability"""
        self.ensure_one()

        if self.discuss_channel_id:
            raise UserError(_("Video channel already created for this session."))

        if not self.patient_id or not self.doctor_id:
            raise UserError(_("Patient and doctor must be assigned before creating video channel."))

        # Get patient partner (create if doesn't exist)
        patient_partner = self.patient_id.partner_id
        if not patient_partner:
            raise UserError(_("Patient must have a related partner/user to join video calls."))

        # Get doctor partner
        doctor_partner = self.doctor_id.user_id.partner_id if self.doctor_id.user_id else False
        if not doctor_partner:
            raise UserError(_("Doctor must have a related user account to host video calls."))

        # Create private channel with patient + doctor
        channel = self.env['discuss.channel'].sudo().create({
            'name': f"🎥 Consultation: {self.patient_id.name}",
            'description': f"Telemedicine session for appointment {self.appointment_id.name} on {self.session_date.strftime('%Y-%m-%d %H:%M')}",
            'channel_type': 'group',
            'public': 'private',  # Only invited members
            'email_send': False,  # Don't send emails
        })

        # Add members to channel
        channel.sudo().write({
            'channel_member_ids': [
                (0, 0, {'partner_id': patient_partner.id}),
                (0, 0, {'partner_id': doctor_partner.id}),
            ],
        })

        self.discuss_channel_id = channel.id
        self.state = 'scheduled'

        self.message_post(
            body=_("✅ Video call channel created successfully. Channel: %s") % channel.name,
            message_type='notification'
        )

        _logger.info(f"Created Discuss channel {channel.id} for telemed session {self.id}")
        return True

    def action_join_call(self):
        """Open Discuss and start/join RTC session"""
        self.ensure_one()

        if not self.discuss_channel_id:
            self.action_create_video_channel()

        # Update state based on who's joining
        current_user = self.env.user

        if self.doctor_id and self.doctor_id.user_id == current_user:
            if not self.doctor_joined:
                self.write({
                    'doctor_joined': True,
                    'doctor_join_time': fields.Datetime.now()
                })
        elif self.patient_id and self.patient_id.partner_id == current_user.partner_id:
            if not self.patient_joined:
                self.write({
                    'patient_joined': True,
                    'patient_join_time': fields.Datetime.now()
                })

        # Update session state
        if self.state == 'scheduled':
            self.state = 'waiting'

        if self.doctor_joined and self.patient_joined and self.state != 'in_progress':
            self.state = 'in_progress'

        # Open Discuss with RTC session
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'discuss.channel',
            'res_id': self.discuss_channel_id.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'start_rtc_session': True,  # Auto-start video call
            },
        }

    def action_end_session(self):
        """Complete the telemedicine session"""
        self.ensure_one()

        if self.state not in ['waiting', 'in_progress']:
            raise UserError(_("Only active sessions can be completed."))

        self.state = 'completed'

        # Update appointment status
        if self.appointment_id and self.appointment_id.state != 'done':
            self.appointment_id.write({'state': 'done'})

        self.message_post(
            body=_("✅ Telemedicine session completed successfully."),
            message_type='notification'
        )

        return True

    def action_cancel_session(self):
        """Cancel the telemedicine session"""
        self.ensure_one()

        if self.state in ['completed', 'cancelled']:
            raise UserError(_("Session cannot be cancelled in current state."))

        self.state = 'cancelled'

        self.message_post(
            body=_("❌ Telemedicine session cancelled."),
            message_type='notification'
        )

        return True

    def action_send_invitation(self):
        """Send invitation email/SMS to patient and doctor"""
        self.ensure_one()

        if not self.discuss_channel_id:
            raise UserError(_("Please create video channel first before sending invitations."))

        # Send email invitation
        template = self.env.ref(
            'clinic_integrations_telemed.email_template_telemed_invitation',
            raise_if_not_found=False
        )

        if template:
            template.send_mail(self.id, force_send=True)
            self.write({
                'invitation_sent': True,
                'invitation_sent_date': fields.Datetime.now()
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Invitation Sent'),
                    'message': _('Video call invitation sent to patient and doctor.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            raise UserError(_("Email template not found. Please configure the invitation template."))

    @api.model
    def send_session_reminders(self):
        """Cron job to send session reminders"""
        # Find sessions starting in 15 minutes
        reminder_cutoff = fields.Datetime.now() + timedelta(minutes=15)

        sessions = self.search([
            ('state', '=', 'scheduled'),
            ('session_date', '<=', reminder_cutoff),
            ('session_date', '>', fields.Datetime.now()),
        ])

        success_count = 0

        for session in sessions:
            try:
                # Create activity for doctor
                if session.doctor_id and session.doctor_id.user_id:
                    session.activity_schedule(
                        'mail.mail_activity_data_todo',
                        user_id=session.doctor_id.user_id.id,
                        summary=_('Telemedicine session starting soon'),
                        note=_('Session with %s starts in 15 minutes') % session.patient_id.name,
                    )

                # Send notification to discuss channel
                if session.discuss_channel_id:
                    session.discuss_channel_id.message_post(
                        body=_("⏰ Reminder: Video consultation starts in 15 minutes!"),
                        message_type='notification'
                    )

                success_count += 1
                _logger.info(f"Reminder sent for telemedicine session {session.id}")

            except Exception as e:
                _logger.error(f"Failed to send reminder for session {session.id}: {str(e)}")

        if success_count > 0:
            _logger.info(f"Sent {success_count} telemedicine session reminders")

    def name_get(self):
        return [(session.id, session.display_name) for session in self]


class TelemedicineRecording(models.Model):
    """
    Recording model kept for future use
    (Discuss recordings would be handled by mail/discuss modules)
    """
    _name = 'clinic.telemed.recording'
    _description = 'Telemedicine Session Recording'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Recording Name',
        required=True
    )

    session_id = fields.Many2one(
        'clinic.telemed.session',
        string='Session',
        required=True,
        ondelete='cascade'
    )

    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        related='session_id.patient_id',
        store=True
    )

    recording_url = fields.Char(
        string='Recording URL',
        help='URL or path to recording file'
    )

    recording_duration = fields.Integer(
        string='Duration (seconds)'
    )

    file_size = fields.Integer(
        string='File Size (bytes)'
    )

    recording_date = fields.Datetime(
        string='Recording Date',
        default=fields.Datetime.now
    )

    expiry_date = fields.Datetime(
        string='Expiry Date',
        help='Date when recording will be automatically deleted for compliance'
    )

    download_count = fields.Integer(
        string='Download Count',
        default=0
    )

    notes = fields.Text(
        string='Notes',
        help='Additional notes about the recording'
    )
