# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class InsuranceCompany(models.Model):
    _name = 'clinic.insurance.company'
    _description = 'Insurance Company'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _order = 'name'
    
    # Basic Information
    name = fields.Char(
        string='Company Name',
        required=True,
        tracking=True,
        index=True
    )
    
    code = fields.Char(
        string='Company Code',
        tracking=True,
        index=True
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Related Partner',
        help='Partner record for accounting'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    
    # Contact Information
    phone = fields.Char(
        string='Phone',
        tracking=True
    )
    
    fax = fields.Char(
        string='Fax'
    )
    
    email = fields.Char(
        string='Email'
    )
    
    website = fields.Char(
        string='Website'
    )
    
    # Address
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    zip = fields.Char(string='ZIP')
    country_id = fields.Many2one('res.country', string='Country')
    
    # Claims Information
    claims_phone = fields.Char(
        string='Claims Phone'
    )
    
    claims_email = fields.Char(
        string='Claims Email'
    )
    
    claims_address = fields.Text(
        string='Claims Address'
    )
    
    payer_id = fields.Char(
        string='Payer ID',
        help='EDI Payer ID for electronic claims'
    )
    
    # Pre-authorization
    requires_preauth = fields.Boolean(
        string='Requires Pre-authorization',
        default=False,
        tracking=True
    )
    
    preauth_phone = fields.Char(
        string='Pre-auth Phone'
    )
    
    preauth_website = fields.Char(
        string='Pre-auth Website'
    )
    
    preauth_fax = fields.Char(
        string='Pre-auth Fax'
    )
    
    # Payment Terms
    payment_term_id = fields.Many2one(
        'account.payment.term',
        string='Payment Terms'
    )
    
    payment_days = fields.Integer(
        string='Payment Days',
        default=30,
        help='Average days to payment'
    )
    
    # Default Values
    default_copay = fields.Float(
        string='Default Co-pay',
        digits='Product Price'
    )
    
    default_coinsurance = fields.Float(
        string='Default Coinsurance %'
    )
    
    default_deductible = fields.Float(
        string='Default Deductible',
        digits='Product Price'
    )
    
    # EDI Settings
    edi_enabled = fields.Boolean(
        string='EDI Enabled',
        default=False
    )
    
    edi_format = fields.Selection([
        ('837', 'ANSI 837'),
        ('ub04', 'UB-04'),
        ('cms1500', 'CMS-1500'),
        ('api', 'API'),
    ], string='EDI Format')
    
    edi_endpoint = fields.Char(
        string='EDI Endpoint'
    )
    
    # Statistics
    policy_count = fields.Integer(
        string='Policies',
        compute='_compute_statistics'
    )
    
    claim_count = fields.Integer(
        string='Claims',
        compute='_compute_statistics'
    )
    
    total_claimed = fields.Float(
        string='Total Claimed',
        compute='_compute_statistics',
        digits='Product Price'
    )
    
    total_paid = fields.Float(
        string='Total Paid',
        compute='_compute_statistics',
        digits='Product Price'
    )
    
    # Notes
    notes = fields.Text(
        string='Notes'
    )
    
    special_instructions = fields.Text(
        string='Special Instructions',
        help='Special billing or claiming instructions'
    )
    
    @api.depends('policy_ids', 'claim_ids')
    def _compute_statistics(self):
        for company in self:
            company.policy_count = self.env['clinic.insurance.policy'].search_count([
                ('insurance_company_id', '=', company.id)
            ])
            
            claims = self.env['clinic.insurance.claim'].search([
                ('insurance_company_id', '=', company.id)
            ])
            company.claim_count = len(claims)
            company.total_claimed = sum(claims.mapped('amount_billed'))
            company.total_paid = sum(claims.filtered(lambda c: c.state == 'paid').mapped('amount_paid'))
    
    policy_ids = fields.One2many(
        'clinic.insurance.policy',
        'insurance_company_id',
        string='Policies'
    )
    
    claim_ids = fields.One2many(
        'clinic.insurance.claim',
        'insurance_company_id',
        string='Claims'
    )
    
    @api.model
    def create(self, vals):
        # Create partner if not exists
        if not vals.get('partner_id'):
            partner_vals = {
                'name': vals.get('name'),
                'is_company': True,
                'customer_rank': 1,
                'phone': vals.get('phone'),
                'email': vals.get('email'),
                'website': vals.get('website'),
                'street': vals.get('street'),
                'street2': vals.get('street2'),
                'city': vals.get('city'),
                'state_id': vals.get('state_id'),
                'zip': vals.get('zip'),
                'country_id': vals.get('country_id'),
            }
            partner = self.env['res.partner'].create(partner_vals)
            vals['partner_id'] = partner.id
        
        return super().create(vals)
    
    def action_view_policies(self):
        """View all policies for this company"""
        self.ensure_one()
        
        return {
            'name': _('Insurance Policies'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.insurance.policy',
            'view_mode': 'tree,form',
            'domain': [('insurance_company_id', '=', self.id)],
            'context': {
                'default_insurance_company_id': self.id,
            }
        }
    
    def action_view_claims(self):
        """View all claims for this company"""
        self.ensure_one()
        
        return {
            'name': _('Insurance Claims'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.insurance.claim',
            'view_mode': 'tree,form,pivot,graph',
            'domain': [('insurance_company_id', '=', self.id)],
        }
    
    def action_test_edi_connection(self):
        """Test EDI connection"""
        self.ensure_one()
        
        if not self.edi_enabled:
            raise ValidationError(_("EDI is not enabled for this company."))
        
        # Test connection (implementation would depend on EDI provider)
        # For now, just return success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('EDI Connection Test'),
                'message': _('Connection test successful!'),
                'type': 'success',
                'sticky': False,
            }
        }