# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ClaimLine(models.Model):
    _name = 'clinic.claim.line'
    _description = 'Insurance Claim Line'
    _order = 'sequence, id'
    
    claim_id = fields.Many2one(
        'clinic.insurance.claim',
        string='Claim',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    # Service Information
    service_id = fields.Many2one(
        'clinic.service',
        string='Service'
    )
    
    procedure_code = fields.Char(
        string='Procedure Code',
        help='CPT/HCPCS code'
    )
    
    modifier_codes = fields.Char(
        string='Modifiers',
        help='Procedure modifiers (comma-separated)'
    )
    
    description = fields.Text(
        string='Description',
        required=True
    )
    
    service_date = fields.Date(
        string='Service Date',
        required=True
    )
    
    # Diagnosis
    diagnosis_ids = fields.Many2many(
        'clinic.diagnosis',
        string='Diagnoses',
        help='Related diagnoses for this service'
    )
    
    # Quantities and Amounts
    quantity = fields.Float(
        string='Quantity',
        default=1.0,
        required=True
    )
    
    unit_price = fields.Float(
        string='Unit Price',
        required=True,
        digits='Product Price'
    )
    
    amount = fields.Float(
        string='Amount',
        compute='_compute_amount',
        store=True,
        digits='Product Price'
    )
    
    # Insurance Response
    approved_amount = fields.Float(
        string='Approved Amount',
        digits='Product Price'
    )
    
    paid_amount = fields.Float(
        string='Paid Amount',
        digits='Product Price'
    )
    
    denied_amount = fields.Float(
        string='Denied Amount',
        compute='_compute_denied_amount',
        store=True,
        digits='Product Price'
    )
    
    # Denial Information
    is_denied = fields.Boolean(
        string='Denied',
        default=False
    )
    
    denial_reason = fields.Text(
        string='Denial Reason'
    )
    
    denial_code = fields.Char(
        string='Denial Code'
    )
    
    # Place of Service
    place_of_service = fields.Selection([
        ('11', 'Office'),
        ('12', 'Home'),
        ('21', 'Inpatient Hospital'),
        ('22', 'Outpatient Hospital'),
        ('23', 'Emergency Room'),
        ('31', 'Skilled Nursing Facility'),
        ('32', 'Nursing Facility'),
        ('81', 'Independent Laboratory'),
    ], string='Place of Service', default='11')
    
    # Provider
    provider_id = fields.Many2one(
        'clinic.staff',
        string='Provider',
        domain=[('is_practitioner', '=', True)]
    )
    
    # Notes
    notes = fields.Text(
        string='Notes'
    )
    
    @api.depends('quantity', 'unit_price')
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.unit_price
    
    @api.depends('amount', 'paid_amount')
    def _compute_denied_amount(self):
        for line in self:
            if line.is_denied:
                line.denied_amount = line.amount
            else:
                line.denied_amount = max(0, line.amount - line.paid_amount)
    
    @api.constrains('approved_amount', 'amount')
    def _check_approved_amount(self):
        for line in self:
            if line.approved_amount > line.amount:
                raise ValidationError(_("Approved amount cannot exceed billed amount."))
    
    @api.constrains('paid_amount', 'approved_amount')
    def _check_paid_amount(self):
        for line in self:
            if line.paid_amount > line.approved_amount and line.approved_amount > 0:
                raise ValidationError(_("Paid amount cannot exceed approved amount."))
    
    @api.onchange('service_id')
    def _onchange_service_id(self):
        if self.service_id:
            self.description = self.service_id.description
            self.unit_price = self.service_id.list_price
            self.procedure_code = self.service_id.procedure_code
    
    @api.onchange('is_denied')
    def _onchange_is_denied(self):
        if self.is_denied:
            self.approved_amount = 0.0
            self.paid_amount = 0.0
        else:
            self.denial_reason = False
            self.denial_code = False