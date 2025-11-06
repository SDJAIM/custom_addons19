# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # SMS Settings
    clinic_sms_enabled = fields.Boolean(
        string='Enable SMS Notifications',
        config_parameter='clinic.sms.enabled'
    )

    clinic_sms_provider = fields.Selection([
        ('twilio', 'Twilio'),
        ('aws_sns', 'AWS SNS'),
        ('http_api', 'HTTP API (Custom)'),
    ], string='SMS Provider', default='twilio',
       config_parameter='clinic.sms.provider')

    clinic_sms_from_number = fields.Char(
        string='From Number',
        config_parameter='clinic.sms.from_number'
    )

    # Twilio
    clinic_sms_twilio_account_sid = fields.Char(
        string='Twilio Account SID',
        config_parameter='clinic.sms.twilio.account_sid'
    )

    clinic_sms_twilio_auth_token = fields.Char(
        string='Twilio Auth Token',
        config_parameter='clinic.sms.twilio.auth_token'
    )

    # AWS SNS
    clinic_sms_aws_access_key = fields.Char(
        string='AWS Access Key',
        config_parameter='clinic.sms.aws.access_key'
    )

    clinic_sms_aws_secret_key = fields.Char(
        string='AWS Secret Key',
        config_parameter='clinic.sms.aws.secret_key'
    )

    clinic_sms_aws_region = fields.Char(
        string='AWS Region',
        default='us-east-1',
        config_parameter='clinic.sms.aws.region'
    )

    # HTTP API
    clinic_sms_api_url = fields.Char(
        string='API URL',
        config_parameter='clinic.sms.api.url'
    )

    clinic_sms_api_key = fields.Char(
        string='API Key',
        config_parameter='clinic.sms.api.key'
    )

    clinic_sms_api_method = fields.Selection([
        ('POST', 'POST'),
        ('GET', 'GET'),
    ], string='HTTP Method', default='POST',
       config_parameter='clinic.sms.api.method')
