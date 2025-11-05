# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DoseUnit(models.Model):
    _name = 'clinic.dose.unit'
    _description = 'Medication Dose Unit'
    _order = 'unit_type, name'
    
    name = fields.Char(
        string='Unit Name',
        required=True,
        translate=True
    )
    
    abbreviation = fields.Char(
        string='Abbreviation',
        required=True,
        help='e.g., mg, ml, mcg'
    )
    
    unit_type = fields.Selection([
        ('weight', 'Weight'),
        ('volume', 'Volume'),
        ('unit', 'Unit'),
        ('area', 'Area'),
        ('international', 'International Unit'),
        ('other', 'Other'),
    ], string='Type', default='weight', required=True)
    
    conversion_factor = fields.Float(
        string='Conversion Factor',
        default=1.0,
        help='Conversion factor to base unit'
    )
    
    base_unit_id = fields.Many2one(
        'clinic.dose.unit',
        string='Base Unit',
        help='Base unit for conversion'
    )
    
    description = fields.Text(
        string='Description',
        translate=True
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )

    @api.constrains('abbreviation')
    def _check_abbreviation_unique(self):
        for record in self:
            if record.abbreviation and self.search_count([('abbreviation', '=', record.abbreviation), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_('Abbreviation must be unique!'))
    
    def name_get(self):
        result = []
        for unit in self:
            name = f"{unit.name} ({unit.abbreviation})"
            result.append((unit.id, name))
        return result
    
    @api.model
    def convert_dose(self, from_unit_id, to_unit_id, dose):
        """Convert dose from one unit to another"""
        from_unit = self.browse(from_unit_id)
        to_unit = self.browse(to_unit_id)
        
        if from_unit.unit_type != to_unit.unit_type:
            raise ValueError(_("Cannot convert between different unit types"))
        
        # Convert to base unit first
        if from_unit.base_unit_id:
            base_dose = dose * from_unit.conversion_factor
        else:
            base_dose = dose
        
        # Convert from base unit to target unit
        if to_unit.base_unit_id:
            result_dose = base_dose / to_unit.conversion_factor
        else:
            result_dose = base_dose
        
        return result_dose