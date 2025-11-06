# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging
import secrets
import string
import hashlib
import hmac
import json
from datetime import datetime, timedelta

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
        tracking=True
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

    # Platform Information
    platform = fields.Selection([
        ('zoom', 'Zoom'),
        ('google_meet', 'Google Meet'),
        ('jitsi', 'Jitsi Meet'),
        ('teams', 'Microsoft Teams'),
        ('custom', 'Custom Platform'),
    ], string='Platform', compute='_compute_platform', store=True)

    meeting_id = fields.Char(
        string='Meeting ID',
        readonly=True,
        copy=False
    )

    meeting_url = fields.Char(
        string='Meeting URL',
        readonly=True,
        copy=False
    )

    meeting_password = fields.Char(
        string='Meeting Password',
        readonly=True,
        copy=False
    )

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('ready', 'Ready to Start'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ], string='Status', default='draft', tracking=True)

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
        compute='_compute_recording_enabled'
    )

    recording_url = fields.Char(
        string='Recording URL',
        readonly=True
    )

    recording_id = fields.Many2one(
        'clinic.telemed.recording',
        string='Recording',
        readonly=True
    )

    # Session Security
    session_token = fields.Char(
        string='Session Token',
        readonly=True,
        copy=False,
        help='Secure token for session validation'
    )

    session_secret = fields.Char(
        string='Session Secret',
        readonly=True,
        copy=False,
        help='Secret key for session signature'
    )

    token_expiry = fields.Datetime(
        string='Token Expiry',
        readonly=True,
        help='When the session token expires'
    )

    # Technical Details
    external_meeting_data = fields.Text(
        string='External Meeting Data',
        readonly=True,
        help='JSON data from external platform'
    )

    error_message = fields.Text(
        string='Error Message',
        readonly=True
    )

    # Session Validation
    validation_attempts = fields.Integer(
        string='Validation Attempts',
        default=0,
        readonly=True,
        help='Number of failed validation attempts'
    )

    max_validation_attempts = fields.Integer(
        string='Max Validation Attempts',
        default=3,
        readonly=True
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

    reminder_sent = fields.Boolean(
        string='Reminder Sent',
        default=False
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

    @api.depends()
    def _compute_platform(self):
        """Get platform from configuration"""
        config_helper = self.env['clinic.telemed.config.helper']
        platform = config_helper.get_config_value('platform', 'jitsi')
        for session in self:
            session.platform = platform

    @api.depends()
    def _compute_recording_enabled(self):
        """Get recording setting from configuration"""
        config_helper = self.env['clinic.telemed.config.helper']
        recording_enabled = config_helper.get_config_value('recording_enabled', 'False') == 'True'
        for session in self:
            session.recording_enabled = recording_enabled

    def action_schedule_session(self):
        """Schedule the telemedicine session with enhanced error handling"""
        self.ensure_one()

        if self.state != 'draft':
            raise UserError(_("Only draft sessions can be scheduled."))

        # Get configuration
        try:
            config_helper = self.env['clinic.telemed.config.helper']
            if not config_helper.is_configured():
                raise UserError(_("Telemedicine platform is not configured. Please configure it in Settings."))

            config = config_helper.get_platform_config()
        except Exception as e:
            _logger.error(f"Failed to get telemedicine configuration: {str(e)}")
            raise UserError(_("Configuration error: %s") % str(e))

        try:
            # Generate session security tokens
            self._generate_session_tokens()

            # Create meeting based on platform with error handling
            platform = config.get('platform')
            if platform == 'zoom':
                self._create_zoom_meeting(config)
            elif platform == 'google_meet':
                self._create_google_meeting(config)
            elif platform == 'teams':
                self._create_teams_meeting(config)
            elif platform == 'jitsi':
                self._create_jitsi_meeting(config)
            elif platform == 'custom':
                self._create_custom_meeting(config)
            else:
                raise ValidationError(_("Unknown platform: %s") % platform)

            self.state = 'scheduled'

            # Send invitations if configured with error handling
            try:
                notification_config = config_helper.get_notification_config()
                if notification_config.get('send_email_invites'):
                    self._send_email_invitation()
            except Exception as e:
                _logger.warning(f"Failed to send invitation for session {self.id}: {str(e)}")
                # Don't fail the whole scheduling if invitation fails

            self.message_post(
                body=_("Telemedicine session scheduled successfully. Meeting ID: %s") % self.meeting_id,
                message_type='notification'
            )

        except (UserError, ValidationError):
            raise  # Re-raise user-friendly errors
        except Exception as e:
            _logger.error(f"Failed to schedule telemedicine session {self.id}: {str(e)}", exc_info=True)
            self.write({
                'state': 'failed',
                'error_message': str(e)
            })
            raise UserError(_("Failed to schedule session: %s") % str(e))

        return True

    def _generate_session_tokens(self):
        """Generate secure session tokens for validation"""
        # Generate secure session token
        session_token = secrets.token_urlsafe(32)
        session_secret = secrets.token_urlsafe(48)

        # Set token expiry (24 hours from now)
        token_expiry = fields.Datetime.now() + timedelta(hours=24)

        self.write({
            'session_token': session_token,
            'session_secret': session_secret,
            'token_expiry': token_expiry,
        })

    def validate_session_token(self, token, signature=None):
        """Validate session token with signature verification"""
        self.ensure_one()

        # Check if token hasn't expired
        if self.token_expiry and fields.Datetime.now() > self.token_expiry:
            raise ValidationError(_("Session token has expired"))

        # Check validation attempts
        if self.validation_attempts >= self.max_validation_attempts:
            raise ValidationError(_("Maximum validation attempts exceeded. Session blocked."))

        # Verify token
        if not secrets.compare_digest(self.session_token or '', token):
            self.validation_attempts += 1
            _logger.warning(f"Invalid session token attempt {self.validation_attempts} for session {self.id}")
            raise ValidationError(_("Invalid session token"))

        # Verify signature if provided
        if signature and self.session_secret:
            expected_signature = self._generate_token_signature(token)
            if not secrets.compare_digest(expected_signature, signature):
                self.validation_attempts += 1
                raise ValidationError(_("Invalid session signature"))

        # Reset validation attempts on successful validation
        if self.validation_attempts > 0:
            self.validation_attempts = 0

        return True

    def _generate_token_signature(self, token):
        """Generate HMAC signature for token"""
        if not self.session_secret:
            return ''
        return hmac.new(
            self.session_secret.encode(),
            token.encode(),
            hashlib.sha256
        ).hexdigest()

    def _create_zoom_meeting(self, config):
        """Create Zoom meeting with error handling"""
        try:
            if not config.get('api_key') or not config.get('api_secret'):
                raise ValidationError(_("Zoom API credentials not configured."))

            # Generate meeting password if required
            password = self._generate_meeting_password() if config.get('require_password') else None

            # Zoom API implementation would go here
            # For now, we'll create a placeholder with error simulation
            meeting_id = f"zoom_{secrets.token_hex(8)}"
            meeting_url = f"https://zoom.us/j/{secrets.token_hex(10)}"

            # Add session token to URL for validation
            if self.session_token:
                meeting_url += f"?token={self.session_token[:8]}"

            self.write({
                'meeting_id': meeting_id,
                'meeting_url': meeting_url,
                'meeting_password': password,
            })
        except Exception as e:
            _logger.error(f"Zoom meeting creation failed: {str(e)}")
            raise ValidationError(_("Failed to create Zoom meeting: %s") % str(e))

    def _create_google_meeting(self, config):
        """Create Google Meet meeting with error handling"""
        try:
            if not config.get('client_id') or not config.get('client_secret'):
                raise ValidationError(_("Google API credentials not configured."))

            # Google Calendar API implementation would go here
            meeting_id = f"google_{secrets.token_hex(8)}"
            meeting_url = f"https://meet.google.com/{secrets.token_urlsafe(12)}"

            # Add session validation parameter
            if self.session_token:
                meeting_url += f"?authuser=0&token={self.session_token[:8]}"

            self.write({
                'meeting_id': meeting_id,
                'meeting_url': meeting_url,
                'meeting_password': None,  # Google Meet doesn't use passwords
            })
        except Exception as e:
            _logger.error(f"Google Meet creation failed: {str(e)}")
            raise ValidationError(_("Failed to create Google Meet: %s") % str(e))

    def _create_teams_meeting(self, config):
        """Create Microsoft Teams meeting with error handling"""
        try:
            if not config.get('tenant_id') or not config.get('client_id') or not config.get('client_secret'):
                raise ValidationError(_("Microsoft Teams API credentials not configured."))

            # Teams API implementation would go here
            meeting_id = f"teams_{secrets.token_hex(8)}"
            meeting_url = f"https://teams.microsoft.com/l/meetup-join/{secrets.token_urlsafe(20)}"

            # Add session context
            if self.session_token:
                meeting_url += f"?context=%7B%22token%22%3A%22{self.session_token[:8]}%22%7D"

            self.write({
                'meeting_id': meeting_id,
                'meeting_url': meeting_url,
                'meeting_password': None,  # Teams uses different authentication
            })
        except Exception as e:
            _logger.error(f"Teams meeting creation failed: {str(e)}")
            raise ValidationError(_("Failed to create Teams meeting: %s") % str(e))

    def _create_jitsi_meeting(self, config):
        """Create Jitsi Meet meeting with error handling"""
        try:
            domain = config.get('domain', 'meet.jit.si')

            # Validate domain
            if not domain or not isinstance(domain, str):
                raise ValidationError(_("Invalid Jitsi domain configuration"))

            # Generate room name
            room_name = f"clinic-{self.patient_id.id}-{self.id}-{secrets.token_hex(4)}"

            # Generate password if required
            password = self._generate_meeting_password() if config.get('require_password') else None

            # Build URL with JWT if configured
            meeting_url = f"https://{domain}/{room_name}"
            if self.session_token:
                # Add JWT token for Jitsi authentication
                meeting_url += f"#config.token={self.session_token[:16]}"

            self.write({
                'meeting_id': room_name,
                'meeting_url': meeting_url,
                'meeting_password': password,
            })
        except Exception as e:
            _logger.error(f"Jitsi meeting creation failed: {str(e)}")
            raise ValidationError(_("Failed to create Jitsi meeting: %s") % str(e))

    def _create_custom_meeting(self, config):
        """Create custom platform meeting with error handling"""
        try:
            api_url = config.get('api_url')
            if not api_url:
                raise ValidationError(_("Custom platform API URL not configured."))

            # Validate URL format
            if not api_url.startswith(('http://', 'https://')):
                raise ValidationError(_("Invalid API URL format. Must start with http:// or https://"))

            # Custom API implementation would go here
            meeting_id = f"custom_{secrets.token_hex(8)}"
            meeting_token = secrets.token_hex(10)
            meeting_url = f"{api_url.rstrip('/')}/meeting/{meeting_token}"

            # Add session validation
            if self.session_token:
                meeting_url += f"?session={self.session_token}&sig={self._generate_token_signature(self.session_token)[:16]}"

            self.write({
                'meeting_id': meeting_id,
                'meeting_url': meeting_url,
                'meeting_password': self._generate_meeting_password() if config.get('require_password') else None,
            })
        except Exception as e:
            _logger.error(f"Custom platform meeting creation failed: {str(e)}")
            raise ValidationError(_("Failed to create meeting on custom platform: %s") % str(e))

    def _generate_meeting_password(self):
        """Generate secure meeting password"""
        # Generate 8-character password with letters and numbers
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for i in range(8))

    def _send_email_invitation(self):
        """Send email invitation to patient and doctor"""
        template = self.env.ref('clinic_integrations_telemed.email_template_telemed_invitation', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
            self.write({
                'invitation_sent': True,
                'invitation_sent_date': fields.Datetime.now()
            })

    def action_start_session(self):
        """Mark session as ready to start"""
        self.ensure_one()

        if self.state != 'scheduled':
            raise UserError(_("Only scheduled sessions can be started."))

        self.state = 'ready'
        return {
            'type': 'ir.actions.act_url',
            'url': self.meeting_url,
            'target': 'new',
        }

    def action_join_patient(self, token=None):
        """Patient joins the session with token validation"""
        self.ensure_one()

        # Validate session if token provided
        if token:
            try:
                self.validate_session_token(token)
            except ValidationError as e:
                _logger.warning(f"Patient join validation failed for session {self.id}: {str(e)}")
                raise UserError(_("Session validation failed: %s") % str(e))

        try:
            if not self.patient_joined:
                self.write({
                    'patient_joined': True,
                    'patient_join_time': fields.Datetime.now()
                })

            if self.doctor_joined and self.state != 'in_progress':
                self.state = 'in_progress'

            return {
                'type': 'ir.actions.act_url',
                'url': self.meeting_url,
                'target': 'new',
            }
        except Exception as e:
            _logger.error(f"Error joining patient to session {self.id}: {str(e)}")
            raise UserError(_("Failed to join session: %s") % str(e))

    def action_join_doctor(self, token=None):
        """Doctor joins the session with token validation"""
        self.ensure_one()

        # Validate session if token provided
        if token:
            try:
                self.validate_session_token(token)
            except ValidationError as e:
                _logger.warning(f"Doctor join validation failed for session {self.id}: {str(e)}")
                raise UserError(_("Session validation failed: %s") % str(e))

        try:
            if not self.doctor_joined:
                self.write({
                    'doctor_joined': True,
                    'doctor_join_time': fields.Datetime.now()
                })

            if self.patient_joined and self.state != 'in_progress':
                self.state = 'in_progress'

            return {
                'type': 'ir.actions.act_url',
                'url': self.meeting_url,
                'target': 'new',
            }
        except Exception as e:
            _logger.error(f"Error joining doctor to session {self.id}: {str(e)}")
            raise UserError(_("Failed to join session: %s") % str(e))

    def action_complete_session(self):
        """Complete the session"""
        self.ensure_one()

        if self.state not in ['ready', 'in_progress']:
            raise UserError(_("Only active sessions can be completed."))

        self.state = 'completed'

        # Update appointment status
        if self.appointment_id:
            self.appointment_id.write({'state': 'done'})

        self.message_post(
            body=_("Telemedicine session completed successfully."),
            message_type='notification'
        )

        return True

    def action_cancel_session(self):
        """Cancel the session"""
        self.ensure_one()

        if self.state in ['completed', 'cancelled']:
            raise UserError(_("Session cannot be cancelled in current state."))

        self.state = 'cancelled'

        self.message_post(
            body=_("Telemedicine session cancelled."),
            message_type='notification'
        )

        return True

    @api.model
    def send_session_reminders(self):
        """Cron job to send session reminders with error handling"""
        try:
            config_helper = self.env['clinic.telemed.config.helper']
            notification_config = config_helper.get_notification_config()
            reminder_time = notification_config.get('reminder_time', 15)
        except Exception as e:
            _logger.error(f"Failed to get reminder configuration: {str(e)}")
            reminder_time = 15  # Use default

        # Find sessions starting soon
        reminder_cutoff = fields.Datetime.now() + timedelta(minutes=reminder_time)

        try:
            sessions = self.search([
                ('state', '=', 'scheduled'),
                ('session_date', '<=', reminder_cutoff),
                ('session_date', '>', fields.Datetime.now()),
                ('reminder_sent', '=', False),
            ])
        except Exception as e:
            _logger.error(f"Failed to search for sessions needing reminders: {str(e)}")
            return

        success_count = 0
        failure_count = 0

        for session in sessions:
            try:
                # Send reminder email
                template = self.env.ref('clinic_integrations_telemed.email_template_telemed_reminder', raise_if_not_found=False)
                if template:
                    template.send_mail(session.id, force_send=True)
                    session.reminder_sent = True
                    success_count += 1
                    _logger.info(f"Reminder sent for telemedicine session {session.id}")
                else:
                    _logger.warning("Reminder email template not found")
                    failure_count += 1

            except Exception as e:
                _logger.error(f"Failed to send reminder for session {session.id}: {str(e)}", exc_info=True)
                failure_count += 1

        if success_count > 0 or failure_count > 0:
            _logger.info(f"Reminder sending completed: {success_count} successful, {failure_count} failed")

    def name_get(self):
        return [(session.id, session.display_name) for session in self]


class TelemedicineRecording(models.Model):
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
        required=True
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
        help='Date when recording will be automatically deleted'
    )

    # Access Control
    access_code = fields.Char(
        string='Access Code',
        default=lambda self: secrets.token_hex(8),
        help='Code required to access recording'
    )

    download_count = fields.Integer(
        string='Download Count',
        default=0
    )

    # Technical
    external_id = fields.Char(
        string='External Recording ID',
        help='ID from external platform'
    )

    platform = fields.Selection([
        ('zoom', 'Zoom'),
        ('google_meet', 'Google Meet'),
        ('teams', 'Microsoft Teams'),
        ('custom', 'Custom Platform'),
    ], string='Platform', related='session_id.platform')

    def action_download_recording(self):
        """Download recording"""
        self.ensure_one()

        if not self.recording_url:
            raise UserError(_("Recording URL not available."))

        self.download_count += 1

        return {
            'type': 'ir.actions.act_url',
            'url': self.recording_url,
            'target': 'new',
        }