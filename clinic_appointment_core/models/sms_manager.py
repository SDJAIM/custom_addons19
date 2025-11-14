# -*- coding: utf-8 -*-
"""
TASK-F1-006: Deprecated SMS Manager
====================================
This module has been deprecated in favor of Odoo CE's built-in 'sms' module.

The methods in this class now act as compatibility wrappers that:
1. Log deprecation warnings
2. Delegate to Odoo's native SMS functionality

Future versions will remove this module entirely.
Use sms.template and _message_sms() methods instead.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SMSManager(models.AbstractModel):
    """
    DEPRECATED: SMS Manager - Compatibility wrapper for legacy code
    Use Odoo CE's sms.template and mail.thread._message_sms() instead
    """
    _name = 'clinic.appointment.sms.manager'
    _description = 'SMS Manager for Appointments (DEPRECATED)'

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
        DEPRECATED: Send SMS message
        Use sms.sms.create() or _message_sms() instead

        Args:
            phone_number (str): Destination phone number (E.164 format recommended)
            message (str): Message content
            appointment (clinic.appointment, optional): Related appointment

        Returns:
            dict: Result with success status and message_id or error
        """
        _logger.warning(
            "DEPRECATED: clinic.appointment.sms.manager.send_sms() is deprecated. "
            "Use Odoo CE's sms.sms model instead."
        )

        if not phone_number:
            return {
                'success': False,
                'error': 'No phone number provided'
            }

        try:
            # Use Odoo CE's SMS system
            sms_record = self.env['sms.sms'].sudo().create({
                'number': phone_number,
                'body': message,
            })

            # Send immediately
            sms_record.send()

            # Check if sent successfully
            if sms_record.state in ['pending', 'sent']:
                _logger.info("SMS sent successfully via Odoo CE to %s: %s", phone_number, sms_record.uuid)
                return {
                    'success': True,
                    'message_id': sms_record.uuid,
                    'provider': 'odoo_ce'
                }
            else:
                return {
                    'success': False,
                    'error': f'SMS failed with state: {sms_record.state}',
                }

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
        DEPRECATED: Send appointment reminder SMS
        Use appointment._send_reminder_sms() instead

        Args:
            appointment (clinic.appointment): Appointment record

        Returns:
            dict: Result
        """
        _logger.warning(
            "DEPRECATED: send_appointment_reminder_sms() is deprecated. "
            "Use appointment._send_reminder_sms() or _message_sms_with_template() instead."
        )

        if not appointment.patient_phone:
            return {
                'success': False,
                'error': 'Patient has no phone number'
            }

        # Delegate to the new method
        result = appointment._send_reminder_sms()
        return {
            'success': bool(result),
            'message_id': result if result else None,
        }

    @api.model
    def send_appointment_confirmation_sms(self, appointment):
        """
        DEPRECATED: Send appointment confirmation SMS
        Use appointment._send_confirmation_sms() instead

        Args:
            appointment (clinic.appointment): Appointment record

        Returns:
            dict: Result
        """
        _logger.warning(
            "DEPRECATED: send_appointment_confirmation_sms() is deprecated. "
            "Use appointment._send_confirmation_sms() or _message_sms_with_template() instead."
        )

        if not appointment.patient_phone:
            return {
                'success': False,
                'error': 'Patient has no phone number'
            }

        # Delegate to the new method
        result = appointment._send_confirmation_sms()
        return {
            'success': bool(result),
            'message_id': result if result else None,
        }

    @api.model
    def send_appointment_cancelled_sms(self, appointment):
        """
        DEPRECATED: Send appointment cancellation SMS
        Use appointment._send_cancellation_sms() instead

        Args:
            appointment (clinic.appointment): Appointment record

        Returns:
            dict: Result
        """
        _logger.warning(
            "DEPRECATED: send_appointment_cancelled_sms() is deprecated. "
            "Use appointment._send_cancellation_sms() or _message_sms_with_template() instead."
        )

        if not appointment.patient_phone:
            return {
                'success': False,
                'error': 'Patient has no phone number'
            }

        # Delegate to the new method
        result = appointment._send_cancellation_sms()
        return {
            'success': bool(result),
            'message_id': result if result else None,
        }


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
