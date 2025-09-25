# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AppointmentSlotWeb(models.Model):
    _inherit = 'clinic.appointment.slot'
    
    # Web-specific fields
    available_online = fields.Boolean(string='Available Online', default=True)