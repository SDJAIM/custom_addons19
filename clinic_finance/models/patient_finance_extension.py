# -*- coding: utf-8 -*-

from odoo import models, fields

class PatientFinanceExtension(models.Model):
    """Extend patient model with finance-related fields"""
    _inherit = 'clinic.patient'

    insurance_ids = fields.One2many(
        'clinic.patient.insurance',
        'patient_id',
        string='Insurance Policies'
    )
