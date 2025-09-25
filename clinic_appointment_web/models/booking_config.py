# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class BookingConfig(models.Model):
    _name = 'clinic.booking.config'
    _description = 'Booking Configuration'
    _rec_name = 'name'
    
    name = fields.Char(string='Configuration Name', default='Default')
    
    # Placeholder for booking configuration