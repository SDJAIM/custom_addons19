# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import requests

_logger = logging.getLogger(__name__)


class SMSManager(models.AbstractModel):
    """
    SMS Manager - Abstract model for sending SMS notifications
    Supports multiple providers (Twilio, AWS SNS, custom)
    """
    _name = 'clinic.appointment.sms.manager'
    _description = 'SMS Manager for Appointments'

    @api.model
    def get_sms_config(self):
        """
        Get SMS configuration from system parameters

        Returns:
            dict: SMS config with provider, credentials, etc.
        """
        ICP = self.env['ir.config_parameter'].sudo()

        config = {
            'enabled': ICP.get_param('clinic.sms.enabled', 'false').lower() == 'true',
            'provider': ICP.get_param('clinic.sms.provider', 'twilio'),
            'from_number': ICP.get_param('clinic.sms.from_number', ''),

            # Twilio
            'twilio_account_sid': ICP.get_param('clinic.sms.twilio.account_sid', ''),
            'twilio_auth_token': ICP.get_param('clinic.sms.twilio.auth_token', ''),

            # AWS SNS
            'aws_access_key': ICP.get_param('clinic.sms.aws.access_key', ''),
            'aws_secret_key': ICP.get_param('clinic.sms.aws.secret_key', ''),
            'aws_region': ICP.get_param('clinic.sms.aws.region', 'us-east-1'),

            # Generic HTTP API
            'api_url': ICP.get_param('clinic.sms.api.url', ''),
            'api_key': ICP.get_param('clinic.sms.api.key', ''),
            'api_method': ICP.get_param('clinic.sms.api.method', 'POST'),
        }

        return config

    @api.model
    def send_sms(self, phone_number, message, appointment=None):
        """
        Send SMS message

        Args:
            phone_number (str): Destination phone number (E.164 format recommended)
            message (str): Message content
            appointment (clinic.appointment, optional): Related appointment

        Returns:
            dict: Result with success status and message_id or error
        """
        config = self.get_sms_config()

        if not config['enabled']:
            _logger.info("SMS disabled in config, skipping send to %s", phone_number)
            return {
                'success': False,
                'error': 'SMS service is not enabled',
                'skipped': True
            }

        if not phone_number:
            return {
                'success': False,
                'error': 'No phone number provided'
            }

        # Clean phone number
        phone_number = self._clean_phone_number(phone_number)

        # Select provider
        provider = config['provider']

        try:
            if provider == 'twilio':
                result = self._send_via_twilio(phone_number, message, config)
            elif provider == 'aws_sns':
                result = self._send_via_aws_sns(phone_number, message, config)
            elif provider == 'http_api':
                result = self._send_via_http_api(phone_number, message, config)
            else:
                raise UserError(_('Unknown SMS provider: %s') % provider)

            # Log success
            if result.get('success'):
                _logger.info("SMS sent successfully to %s via %s: %s",
                           phone_number, provider, result.get('message_id'))

                # Create SMS log record
                self._create_sms_log(phone_number, message, appointment, result)

            return result

        except Exception as e:
            _logger.error("Error sending SMS to %s: %s", phone_number, str(e))
            return {
                'success': False,
                'error': str(e)
            }

    def _clean_phone_number(self, phone):
        """
        Clean and format phone number

        Args:
            phone (str): Raw phone number

        Returns:
            str: Cleaned phone number
        """
        if not phone:
            return ''

        # Remove common formatting characters
        phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')

        # Ensure + prefix for international format
        if not phone.startswith('+'):
            phone = '+' + phone

        return phone

    def _send_via_twilio(self, phone_number, message, config):
        """
        Send SMS via Twilio

        Args:
            phone_number (str): Destination
            message (str): Message
            config (dict): SMS config

        Returns:
            dict: Result
        """
        account_sid = config.get('twilio_account_sid')
        auth_token = config.get('twilio_auth_token')
        from_number = config.get('from_number')

        if not all([account_sid, auth_token, from_number]):
            raise UserError(_('Twilio credentials not configured'))

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"

        data = {
            'From': from_number,
            'To': phone_number,
            'Body': message
        }

        response = requests.post(url, data=data, auth=(account_sid, auth_token), timeout=10)

        if response.status_code == 201:
            result_data = response.json()
            return {
                'success': True,
                'message_id': result_data.get('sid'),
                'provider': 'twilio'
            }
        else:
            error_msg = response.json().get('message', 'Unknown error')
            return {
                'success': False,
                'error': f"Twilio API error: {error_msg}",
                'status_code': response.status_code
            }

    def _send_via_aws_sns(self, phone_number, message, config):
        """
        Send SMS via AWS SNS

        Args:
            phone_number (str): Destination
            message (str): Message
            config (dict): SMS config

        Returns:
            dict: Result
        """
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError:
            raise UserError(_('boto3 library not installed. Install with: pip install boto3'))

        access_key = config.get('aws_access_key')
        secret_key = config.get('aws_secret_key')
        region = config.get('aws_region')

        if not all([access_key, secret_key]):
            raise UserError(_('AWS credentials not configured'))

        client = boto3.client(
            'sns',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )

        try:
            response = client.publish(
                PhoneNumber=phone_number,
                Message=message,
                MessageAttributes={
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'
                    }
                }
            )

            return {
                'success': True,
                'message_id': response.get('MessageId'),
                'provider': 'aws_sns'
            }

        except ClientError as e:
            return {
                'success': False,
                'error': f"AWS SNS error: {e.response['Error']['Message']}"
            }

    def _send_via_http_api(self, phone_number, message, config):
        """
        Send SMS via generic HTTP API

        Args:
            phone_number (str): Destination
            message (str): Message
            config (dict): SMS config

        Returns:
            dict: Result
        """
        api_url = config.get('api_url')
        api_key = config.get('api_key')
        method = config.get('api_method', 'POST').upper()

        if not api_url:
            raise UserError(_('HTTP API URL not configured'))

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        } if api_key else {'Content-Type': 'application/json'}

        data = {
            'to': phone_number,
            'message': message
        }

        if method == 'POST':
            response = requests.post(api_url, json=data, headers=headers, timeout=10)
        elif method == 'GET':
            response = requests.get(api_url, params=data, headers=headers, timeout=10)
        else:
            raise UserError(_('Invalid HTTP method: %s') % method)

        if response.status_code in [200, 201]:
            return {
                'success': True,
                'message_id': response.json().get('id', 'unknown'),
                'provider': 'http_api'
            }
        else:
            return {
                'success': False,
                'error': f"HTTP API error: {response.text}",
                'status_code': response.status_code
            }

    def _create_sms_log(self, phone_number, message, appointment, result):
        """
        Create SMS log record

        Args:
            phone_number (str): Destination
            message (str): Message
            appointment (clinic.appointment): Related appointment
            result (dict): Send result
        """
        log_vals = {
            'phone_number': phone_number,
            'message': message,
            'success': result.get('success', False),
            'message_id': result.get('message_id'),
            'provider': result.get('provider'),
            'error': result.get('error'),
        }

        if appointment:
            log_vals['appointment_id'] = appointment.id

        self.env['clinic.appointment.sms.log'].sudo().create(log_vals)

    @api.model
    def send_appointment_reminder_sms(self, appointment):
        """
        Send appointment reminder SMS

        Args:
            appointment (clinic.appointment): Appointment record

        Returns:
            dict: Result
        """
        if not appointment.patient_phone:
            return {
                'success': False,
                'error': 'Patient has no phone number'
            }

        # Build reminder message
        start_time = appointment.start.strftime('%B %d at %H:%M')
        message = f"""Reminder: You have an appointment on {start_time} with {appointment.staff_id.name}.

Type: {appointment.appointment_type_id.name}
Location: {appointment.branch_id.name if appointment.branch_id else 'TBD'}

View details: {appointment.get_booking_url('view')}

To reschedule or cancel, use the link above."""

        return self.send_sms(appointment.patient_phone, message, appointment)

    @api.model
    def send_appointment_confirmation_sms(self, appointment):
        """
        Send appointment confirmation SMS

        Args:
            appointment (clinic.appointment): Appointment record

        Returns:
            dict: Result
        """
        if not appointment.patient_phone:
            return {
                'success': False,
                'error': 'Patient has no phone number'
            }

        start_time = appointment.start.strftime('%B %d at %H:%M')
        message = f"""Your appointment is confirmed!

Date: {start_time}
Doctor: {appointment.staff_id.name}
Location: {appointment.branch_id.name if appointment.branch_id else 'TBD'}

Confirmation #: {appointment.appointment_number}

Manage: {appointment.get_booking_url('view')}"""

        return self.send_sms(appointment.patient_phone, message, appointment)

    @api.model
    def send_appointment_cancelled_sms(self, appointment):
        """
        Send appointment cancellation SMS

        Args:
            appointment (clinic.appointment): Appointment record

        Returns:
            dict: Result
        """
        if not appointment.patient_phone:
            return {
                'success': False,
                'error': 'Patient has no phone number'
            }

        message = f"""Your appointment on {appointment.start.strftime('%B %d at %H:%M')} has been cancelled.

To book a new appointment, visit our website or call us."""

        return self.send_sms(appointment.patient_phone, message, appointment)


class AppointmentSMSLog(models.Model):
    """
    SMS Log for appointments
    Tracks all SMS messages sent
    """
    _name = 'clinic.appointment.sms.log'
    _description = 'Appointment SMS Log'
    _order = 'create_date desc'

    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Appointment',
        ondelete='set null',
        index=True
    )

    phone_number = fields.Char(string='Phone Number', required=True)
    message = fields.Text(string='Message', required=True)

    success = fields.Boolean(string='Success', default=False)
    message_id = fields.Char(string='Message ID')
    provider = fields.Char(string='Provider')
    error = fields.Text(string='Error')

    create_date = fields.Datetime(string='Sent Date', readonly=True)
