# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class PatientWhatsApp(models.Model):
    _inherit = 'clinic.patient'
    
    whatsapp_opt_in = fields.Boolean(
        string='WhatsApp Opt-In',
        default=False,
        help='Patient has consented to receive WhatsApp messages'
    )
    
    whatsapp_number = fields.Char(
        string='WhatsApp Number',
        help='WhatsApp enabled phone number'
    )
    
    whatsapp_opt_in_date = fields.Datetime(
        string='Opt-In Date'
    )
    
    @api.onchange('whatsapp_opt_in')
    def _onchange_whatsapp_opt_in(self):
        if self.whatsapp_opt_in:
            self.whatsapp_opt_in_date = fields.Datetime.now()
            if not self.whatsapp_number:
                self.whatsapp_number = self.mobile or self.phone