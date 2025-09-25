# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ClinicBranch(models.Model):
    _name = 'clinic.branch'
    _description = 'Clinic Branch/Location'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Branch Name',
        required=True
    )
    
    code = fields.Char(
        string='Branch Code',
        required=True,
        help='Short code for the branch'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    
    # Contact Information
    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Mobile')
    email = fields.Char(string='Email')
    website = fields.Char(string='Website')
    
    # Address
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    country_id = fields.Many2one('res.country', string='Country')
    zip = fields.Char(string='ZIP')
    
    # Full address computed field
    address = fields.Text(
        string='Full Address',
        compute='_compute_address',
        store=True
    )
    
    # Operating Hours
    opening_time = fields.Float(
        string='Opening Time',
        default=8.0,
        help='Branch opening time (24-hour format)'
    )
    
    closing_time = fields.Float(
        string='Closing Time',
        default=20.0,
        help='Branch closing time (24-hour format)'
    )
    
    is_24_hours = fields.Boolean(
        string='24 Hours Service',
        help='Branch operates 24 hours'
    )
    
    working_days = fields.Selection([
        ('mon_fri', 'Monday to Friday'),
        ('mon_sat', 'Monday to Saturday'),
        ('all_days', 'All Days'),
        ('custom', 'Custom')
    ], string='Working Days', default='mon_sat')
    
    # Facilities
    has_emergency = fields.Boolean(string='Emergency Services')
    has_pharmacy = fields.Boolean(string='In-house Pharmacy')
    has_laboratory = fields.Boolean(string='Laboratory')
    has_radiology = fields.Boolean(string='Radiology/X-Ray')
    has_parking = fields.Boolean(string='Parking Available')
    has_wheelchair_access = fields.Boolean(string='Wheelchair Access')
    
    # Stats
    room_count = fields.Integer(
        string='Number of Rooms',
        compute='_compute_room_count'
    )
    
    staff_count = fields.Integer(
        string='Number of Staff',
        compute='_compute_staff_count'
    )
    
    active = fields.Boolean(string='Active', default=True)
    
    # Manager
    manager_id = fields.Many2one(
        'res.users',
        string='Branch Manager'
    )
    
    notes = fields.Text(string='Notes')
    
    @api.constrains('code')
    def _check_code_unique(self):
        for record in self:
            if record.code and self.search_count([('code', '=', record.code), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_('Branch code must be unique!'))
    
    @api.depends('street', 'street2', 'city', 'state_id', 'country_id', 'zip')
    def _compute_address(self):
        for record in self:
            address_parts = []
            if record.street:
                address_parts.append(record.street)
            if record.street2:
                address_parts.append(record.street2)
            if record.city:
                address_parts.append(record.city)
            if record.state_id:
                address_parts.append(record.state_id.name)
            if record.country_id:
                address_parts.append(record.country_id.name)
            if record.zip:
                address_parts.append(record.zip)
            
            record.address = ', '.join(address_parts)
    
    def _compute_room_count(self):
        for record in self:
            record.room_count = self.env['clinic.room'].search_count([
                ('branch_id', '=', record.id)
            ])
    
    def _compute_staff_count(self):
        for record in self:
            record.staff_count = self.env['clinic.staff'].search_count([
                ('branch_ids', 'in', record.id)
            ])
    
    def action_view_rooms(self):
        """View branch rooms"""
        self.ensure_one()
        return {
            'name': _('Rooms'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.room',
            'view_mode': 'tree,form',
            'domain': [('branch_id', '=', self.id)],
            'context': {'default_branch_id': self.id},
        }
    
    def action_view_staff(self):
        """View branch staff"""
        self.ensure_one()
        return {
            'name': _('Staff'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.staff',
            'view_mode': 'tree,form',
            'domain': [('branch_ids', 'in', self.id)],
        }