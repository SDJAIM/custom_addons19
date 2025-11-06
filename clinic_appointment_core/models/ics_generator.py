# -*- coding: utf-8 -*-

from odoo import models, api, _
from datetime import datetime
import base64
import uuid
import logging

_logger = logging.getLogger(__name__)


class ICSGenerator(models.AbstractModel):
    """
    ICS (iCalendar) File Generator
    Generates .ics files for appointment calendar attachments
    Compatible with Google Calendar, Outlook, Apple Calendar, etc.
    """
    _name = 'clinic.appointment.ics.generator'
    _description = 'ICS File Generator for Appointments'

    @api.model
    def generate_ics(self, appointment):
        """
        Generate ICS file content for an appointment

        Args:
            appointment: clinic.appointment record

        Returns:
            str: ICS file content
        """
        appointment.ensure_one()

        # Generate unique UID
        uid = f"appointment-{appointment.id}-{appointment.create_date.strftime('%Y%m%d%H%M%S')}@{self.env.cr.dbname}"

        # Format dates for ICS (YYYYMMDDTHHMMSSZ in UTC)
        start_dt = appointment.start.strftime('%Y%m%dT%H%M%SZ')
        end_dt = appointment.stop.strftime('%Y%m%dT%H%M%SZ')
        created_dt = appointment.create_date.strftime('%Y%m%dT%H%M%SZ')
        modified_dt = appointment.write_date.strftime('%Y%m%dT%H%M%SZ')

        # Prepare description
        description_parts = []
        description_parts.append(f"Appointment Type: {appointment.appointment_type_id.name}")
        description_parts.append(f"Patient: {appointment.patient_id.name}")
        description_parts.append(f"Staff: {appointment.staff_id.name}")

        if appointment.chief_complaint:
            description_parts.append(f"Reason: {appointment.chief_complaint}")

        if appointment.appointment_number:
            description_parts.append(f"Confirmation #: {appointment.appointment_number}")

        # Add booking link if available
        if appointment.access_token:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            booking_url = f"{base_url}/appointment/view/{appointment.id}/{appointment.access_token}"
            description_parts.append(f"Manage appointment: {booking_url}")

        description = "\\n".join(description_parts)

        # Prepare location
        location_parts = []
        if appointment.appointment_type_id.meeting_mode == 'onsite':
            if appointment.branch_id:
                location_parts.append(appointment.branch_id.name)
            if appointment.room_id:
                location_parts.append(f"Room: {appointment.room_id.name}")
        elif appointment.appointment_type_id.meeting_mode == 'online':
            if appointment.telemed_link:
                location_parts.append(f"Online: {appointment.telemed_link}")
        elif appointment.appointment_type_id.meeting_mode == 'phone':
            location_parts.append("Phone Call")
            if appointment.patient_phone:
                location_parts.append(f"Tel: {appointment.patient_phone}")

        location = ", ".join(location_parts) if location_parts else "TBD"

        # Prepare organizer
        organizer_email = appointment.staff_id.work_email or 'noreply@clinic.local'
        organizer_name = appointment.staff_id.name

        # Prepare attendee
        attendee_email = appointment.patient_email or 'patient@clinic.local'
        attendee_name = appointment.patient_id.name

        # Build ICS content
        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Clinic Appointment System//Odoo 19//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{created_dt}
DTSTART:{start_dt}
DTEND:{end_dt}
SUMMARY:{self._escape_ics(appointment.name)}
DESCRIPTION:{self._escape_ics(description)}
LOCATION:{self._escape_ics(location)}
STATUS:{self._get_ics_status(appointment.state)}
ORGANIZER;CN={self._escape_ics(organizer_name)}:mailto:{organizer_email}
ATTENDEE;CN={self._escape_ics(attendee_name)};RSVP=TRUE;PARTSTAT={self._get_partstat(appointment)}:mailto:{attendee_email}
CREATED:{created_dt}
LAST-MODIFIED:{modified_dt}
SEQUENCE:0
END:VEVENT
END:VCALENDAR"""

        return ics_content

    def _escape_ics(self, text):
        """
        Escape special characters for ICS format

        Args:
            text: str to escape

        Returns:
            str: escaped text
        """
        if not text:
            return ''

        # Replace special characters
        text = str(text)
        text = text.replace('\\', '\\\\')
        text = text.replace(',', '\\,')
        text = text.replace(';', '\\;')
        text = text.replace('\n', '\\n')

        return text

    def _get_ics_status(self, state):
        """
        Convert appointment state to ICS STATUS

        Args:
            state: appointment state

        Returns:
            str: ICS status (CONFIRMED, TENTATIVE, CANCELLED)
        """
        status_map = {
            'draft': 'TENTATIVE',
            'confirmed': 'CONFIRMED',
            'arrived': 'CONFIRMED',
            'in_progress': 'CONFIRMED',
            'done': 'CONFIRMED',
            'cancelled': 'CANCELLED',
            'no_show': 'CANCELLED',
        }
        return status_map.get(state, 'TENTATIVE')

    def _get_partstat(self, appointment):
        """
        Get participant status for attendee

        Args:
            appointment: clinic.appointment record

        Returns:
            str: PARTSTAT value (NEEDS-ACTION, ACCEPTED, DECLINED, TENTATIVE)
        """
        if appointment.confirmed_by_customer:
            return 'ACCEPTED'
        elif appointment.state == 'cancelled':
            return 'DECLINED'
        elif appointment.state == 'confirmed':
            return 'TENTATIVE'
        else:
            return 'NEEDS-ACTION'

    @api.model
    def generate_ics_attachment(self, appointment):
        """
        Generate ICS file and create attachment

        Args:
            appointment: clinic.appointment record

        Returns:
            ir.attachment record
        """
        appointment.ensure_one()

        # Generate ICS content
        ics_content = self.generate_ics(appointment)

        # Encode to base64
        ics_base64 = base64.b64encode(ics_content.encode('utf-8'))

        # Create attachment
        attachment_vals = {
            'name': f"appointment_{appointment.appointment_number}.ics",
            'type': 'binary',
            'datas': ics_base64,
            'res_model': 'clinic.appointment',
            'res_id': appointment.id,
            'mimetype': 'text/calendar',
            'description': f'ICS file for appointment {appointment.appointment_number}',
        }

        attachment = self.env['ir.attachment'].sudo().create(attachment_vals)

        return attachment

    @api.model
    def update_ics_attachment(self, appointment):
        """
        Update existing ICS attachment or create new one

        Args:
            appointment: clinic.appointment record

        Returns:
            ir.attachment record
        """
        appointment.ensure_one()

        # Search for existing ICS attachment
        existing_attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'clinic.appointment'),
            ('res_id', '=', appointment.id),
            ('mimetype', '=', 'text/calendar'),
        ], limit=1)

        if existing_attachment:
            # Update existing
            ics_content = self.generate_ics(appointment)
            ics_base64 = base64.b64encode(ics_content.encode('utf-8'))
            existing_attachment.write({
                'datas': ics_base64,
                'name': f"appointment_{appointment.appointment_number}.ics",
            })
            return existing_attachment
        else:
            # Create new
            return self.generate_ics_attachment(appointment)

    @api.model
    def get_ics_download_url(self, appointment):
        """
        Get download URL for ICS file

        Args:
            appointment: clinic.appointment record

        Returns:
            str: Download URL
        """
        appointment.ensure_one()

        # Ensure attachment exists
        attachment = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'clinic.appointment'),
            ('res_id', '=', appointment.id),
            ('mimetype', '=', 'text/calendar'),
        ], limit=1)

        if not attachment:
            attachment = self.generate_ics_attachment(appointment)

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        download_url = f"{base_url}/web/content/{attachment.id}?download=true"

        return download_url
