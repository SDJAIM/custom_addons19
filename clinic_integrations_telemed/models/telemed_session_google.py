# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import requests
import time

_logger = logging.getLogger(__name__)


class TelemedicineSessionGoogleMeet(models.Model):
    """
    TASK-F3-002: Extend Telemed Session with Google Meet Integration
    """
    _inherit = 'clinic.telemed.session'

    # ========================
    # Google Meet Fields
    # ========================
    provider = fields.Selection(
        selection_add=[('google_meet', 'Google Meet')],
        ondelete={'google_meet': 'set default'}
    )

    google_meet_link = fields.Char(
        string='Google Meet Link',
        readonly=True,
        tracking=True,
        help='Auto-generated Google Meet link for this session'
    )

    google_event_id = fields.Char(
        string='Google Calendar Event ID',
        copy=False,
        readonly=True,
        help='Google Calendar event ID for API operations'
    )

    google_meet_config_id = fields.Many2one(
        'clinic.google.meet.config',
        string='Google Meet Config',
        compute='_compute_google_meet_config',
        help='Google Meet configuration for the staff member'
    )

    can_create_google_meet = fields.Boolean(
        string='Can Create Google Meet',
        compute='_compute_can_create_google_meet',
        help='Whether Google Meet can be created for this session'
    )

    # ========================
    # Computed Fields
    # ========================
    @api.depends('doctor_id')
    def _compute_google_meet_config(self):
        """Get Google Meet config for doctor"""
        for session in self:
            if session.doctor_id:
                session.google_meet_config_id = self.env['clinic.google.meet.config'].search([
                    ('staff_id', '=', session.doctor_id.id)
                ], limit=1)
            else:
                session.google_meet_config_id = False

    @api.depends('doctor_id', 'google_meet_link', 'state')
    def _compute_can_create_google_meet(self):
        """Check if Google Meet can be created"""
        for session in self:
            session.can_create_google_meet = (
                session.doctor_id and
                not session.google_meet_link and
                session.state in ['draft', 'scheduled'] and
                bool(session.google_meet_config_id)
            )

    # ========================
    # Actions
    # ========================
    def action_create_google_meet(self):
        """
        Create Google Meet link via Google Calendar API
        """
        self.ensure_one()

        if self.google_meet_link:
            raise UserError(_('Google Meet link already exists for this session.'))

        if not self.doctor_id:
            raise UserError(_('Doctor is required to create Google Meet link.'))

        # Get staff's Google config
        google_config = self.env['clinic.google.meet.config'].search([
            ('staff_id', '=', self.doctor_id.id)
        ], limit=1)

        if not google_config:
            raise UserError(_(
                'Doctor %s has not connected their Google account.\n\n'
                'Please go to Settings → Google Meet Configuration to connect.'
            ) % self.doctor_id.name)

        # Get credentials
        try:
            creds = google_config._get_google_credentials()
        except Exception as e:
            raise UserError(_(
                'Failed to get Google credentials:\n\n%s\n\n'
                'Please reconnect your Google account.'
            ) % str(e))

        # Prepare event data
        start_datetime = self.session_date or self.appointment_id.start
        end_datetime = self.session_end_date or self.appointment_id.stop

        event_data = {
            'summary': f"Telemedicine: {self.patient_id.name}",
            'description': (
                f"Telemedicine Session\n"
                f"Appointment: #{self.appointment_id.appointment_number}\n"
                f"Patient: {self.patient_id.name}\n"
                f"Doctor: {self.doctor_id.name}\n\n"
                f"Notes: {self.appointment_id.notes or 'N/A'}"
            ),
            'start': {
                'dateTime': start_datetime.isoformat(),
                'timeZone': self.env.user.tz or 'UTC',
            },
            'end': {
                'dateTime': end_datetime.isoformat(),
                'timeZone': self.env.user.tz or 'UTC',
            },
            'attendees': [],
            'conferenceData': {
                'createRequest': {
                    'requestId': f"clinic-{self.id}-{int(time.time())}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                }
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                    {'method': 'popup', 'minutes': 10},       # 10 minutes before
                ],
            },
        }

        # Add attendees (with valid emails only)
        if self.patient_id.email:
            event_data['attendees'].append({'email': self.patient_id.email})
        if self.doctor_id.user_id and self.doctor_id.user_id.email:
            event_data['attendees'].append({'email': self.doctor_id.user_id.email})

        # Call Google Calendar API
        try:
            headers = {'Authorization': f"Bearer {creds['token']}"}

            response = requests.post(
                f"https://www.googleapis.com/calendar/v3/calendars/{google_config.google_calendar_id}/events",
                json=event_data,
                params={'conferenceDataVersion': 1},
                headers=headers,
                timeout=30
            )

            if response.status_code in [200, 201]:
                event = response.json()

                # Extract Google Meet link
                meet_link = (
                    event.get('hangoutLink') or
                    event.get('conferenceData', {}).get('entryPoints', [{}])[0].get('uri')
                )

                if not meet_link:
                    raise UserError(_('Google Meet link was not generated. Please try again.'))

                # Update session
                self.write({
                    'google_meet_link': meet_link,
                    'google_event_id': event['id'],
                    'meeting_url': meet_link,
                    'provider': 'google_meet',
                    'state': 'scheduled',
                })

                # Send notification to patient
                if self.patient_id.email:
                    self.appointment_id.message_post(
                        body=_(
                            '<p>Your telemedicine appointment is ready!</p>'
                            '<p><strong>Google Meet Link:</strong> <a href="%s" target="_blank">Join Video Call</a></p>'
                            '<p>The meeting will be available 10 minutes before your appointment time.</p>'
                        ) % meet_link,
                        subject=_('Google Meet Link Ready'),
                        partner_ids=self.patient_id.partner_id.ids if self.patient_id.partner_id else [],
                    )

                _logger.info(f"Created Google Meet for session {self.id}: {meet_link}")

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Google Meet Created'),
                        'message': _('Google Meet link has been created and sent to the patient.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                error_msg = response.json().get('error', {}).get('message', response.text)
                _logger.error(f"Failed to create Google Meet: {error_msg}")
                raise UserError(_(
                    'Failed to create Google Meet.\n\n'
                    'Error: %s\n\n'
                    'Please check your Google Calendar API permissions.'
                ) % error_msg)

        except requests.exceptions.RequestException as e:
            _logger.error(f"Network error creating Google Meet: {str(e)}")
            raise UserError(_(
                'Network error while creating Google Meet.\n\n'
                'Error: %s\n\n'
                'Please check your internet connection and try again.'
            ) % str(e))

    def action_cancel_google_meet(self):
        """
        Cancel Google Calendar event
        """
        self.ensure_one()

        if not self.google_event_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Nothing to Cancel'),
                    'message': _('No Google Meet event found for this session.'),
                    'type': 'info',
                }
            }

        # Get Google config
        google_config = self.env['clinic.google.meet.config'].search([
            ('staff_id', '=', self.doctor_id.id)
        ], limit=1)

        if not google_config:
            _logger.warning(f"No Google config found for doctor {self.doctor_id.name}")
            self.write({
                'google_meet_link': False,
                'google_event_id': False,
            })
            return

        try:
            creds = google_config._get_google_credentials()
            headers = {'Authorization': f"Bearer {creds['token']}"}

            response = requests.delete(
                f"https://www.googleapis.com/calendar/v3/calendars/{google_config.google_calendar_id}/events/{self.google_event_id}",
                headers=headers,
                timeout=10
            )

            if response.status_code in [200, 204]:
                _logger.info(f"Cancelled Google Meet event {self.google_event_id}")
            else:
                _logger.warning(f"Failed to cancel Google event: {response.text}")

        except Exception as e:
            _logger.error(f"Error cancelling Google Meet: {str(e)}")

        # Clear Google Meet data regardless of API result
        self.write({
            'google_meet_link': False,
            'google_event_id': False,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Cancelled'),
                'message': _('Google Meet has been cancelled.'),
                'type': 'info',
            }
        }

    def action_open_google_meet(self):
        """Open Google Meet link in new tab"""
        self.ensure_one()

        if not self.google_meet_link:
            raise UserError(_('No Google Meet link available for this session.'))

        return {
            'type': 'ir.actions.act_url',
            'url': self.google_meet_link,
            'target': 'new',
        }
