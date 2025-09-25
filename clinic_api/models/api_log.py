# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class ApiLog(models.Model):
    _name = 'clinic.api.log'
    _description = 'API Request Log'
    _order = 'timestamp desc'
    
    api_key_id = fields.Many2one('clinic.api.key', string='API Key')
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now)
    endpoint = fields.Char(string='Endpoint')
    method = fields.Char(string='HTTP Method')
    ip_address = fields.Char(string='IP Address')
    response_code = fields.Integer(string='Response Code')
    response_time = fields.Float(string='Response Time (ms)')
    error_message = fields.Text(string='Error Message')