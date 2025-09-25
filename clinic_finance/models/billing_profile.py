# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class BillingProfile(models.Model):
    _name = 'clinic.billing.profile'
    _description = 'Patient Billing Profile'
    _rec_name = 'patient_id'
    
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        index=True
    )
    
    # Placeholder for billing profile implementation