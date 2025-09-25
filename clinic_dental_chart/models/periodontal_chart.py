# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PeriodontalChart(models.Model):
    _name = 'clinic.periodontal.chart'
    _description = 'Periodontal Chart'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'patient_id'
    
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        index=True
    )
    
    dental_chart_id = fields.Many2one(
        'clinic.dental.chart',
        string='Dental Chart'
    )
    
    examination_date = fields.Date(
        string='Examination Date',
        default=fields.Date.context_today,
        required=True
    )
    
    # Placeholder for periodontal measurements
    # Would include pocket depths, recession, mobility, etc.