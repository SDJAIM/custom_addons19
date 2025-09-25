# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class DentalProcedure(models.Model):
    _name = 'clinic.dental.procedure'
    _description = 'Dental Procedure'
    _order = 'category_id, sequence, name'
    
    name = fields.Char(
        string='Procedure Name',
        required=True,
        translate=True
    )
    
    code = fields.Char(
        string='Procedure Code',
        help='CDT/CPT code'
    )
    
    category_id = fields.Many2one(
        'clinic.dental.procedure.category',
        string='Category',
        required=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    description = fields.Text(
        string='Description',
        translate=True
    )
    
    tooth_specific = fields.Boolean(
        string='Tooth Specific',
        default=True,
        help='Is this procedure specific to individual teeth?'
    )
    
    surface_specific = fields.Boolean(
        string='Surface Specific',
        default=False,
        help='Does this procedure apply to specific tooth surfaces?'
    )
    
    duration = fields.Float(
        string='Duration (minutes)',
        default=30.0
    )
    
    price = fields.Float(
        string='Standard Price',
        digits='Product Price'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    # Icon/Color for visualization
    icon = fields.Char(
        string='Icon',
        help='Icon name for UI display'
    )
    
    color = fields.Char(
        string='Color',
        help='Color code for visualization'
    )


class DentalProcedureCategory(models.Model):
    _name = 'clinic.dental.procedure.category'
    _description = 'Dental Procedure Category'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Category Name',
        required=True,
        translate=True
    )
    
    code = fields.Char(
        string='Category Code'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    parent_id = fields.Many2one(
        'clinic.dental.procedure.category',
        string='Parent Category'
    )
    
    child_ids = fields.One2many(
        'clinic.dental.procedure.category',
        'parent_id',
        string='Child Categories'
    )
    
    procedure_ids = fields.One2many(
        'clinic.dental.procedure',
        'category_id',
        string='Procedures'
    )