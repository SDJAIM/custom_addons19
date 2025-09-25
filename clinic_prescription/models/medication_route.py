# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MedicationRoute(models.Model):
    _name = 'clinic.medication.route'
    _description = 'Medication Route of Administration'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Route Name',
        required=True,
        translate=True
    )
    
    code = fields.Char(
        string='Code',
        required=True,
        help='Abbreviation (e.g., PO, IV, IM)'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    route_type = fields.Selection([
        ('enteral', 'Enteral'),
        ('parenteral', 'Parenteral'),
        ('topical', 'Topical'),
        ('inhalation', 'Inhalation'),
        ('other', 'Other'),
    ], string='Type', default='enteral', required=True)
    
    description = fields.Text(
        string='Description',
        translate=True
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    medication_form_ids = fields.Many2many(
        'clinic.medication.form',
        string='Compatible Forms',
        help='Medication forms compatible with this route'
    )
    
    instructions = fields.Text(
        string='Administration Instructions',
        translate=True,
        help='Default instructions for this route'
    )
    
    requires_equipment = fields.Boolean(
        string='Requires Equipment',
        default=False,
        help='Whether special equipment is needed'
    )
    
    equipment_notes = fields.Text(
        string='Equipment Notes'
    )
    
    @api.constrains('code')
    def _check_code_unique(self):
        for record in self:
            if record.code and self.search_count([('code', '=', record.code), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_('Route code must be unique!'))
    
    def name_get(self):
        result = []
        for route in self:
            name = f"{route.name} ({route.code})"
            result.append((route.id, name))
        return result