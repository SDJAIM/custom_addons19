# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ClinicStaffSpecialization(models.Model):
    _name = 'clinic.staff.specialization'
    _description = 'Staff Specialization'
    _order = 'category_id, name'
    
    name = fields.Char(
        string='Specialization',
        required=True,
        translate=True
    )
    
    code = fields.Char(
        string='Code',
        help='Short code for the specialization'
    )
    
    category_id = fields.Many2one(
        'clinic.staff.specialization.category',
        string='Category',
        required=True
    )
    
    staff_type = fields.Selection([
        ('doctor', 'Doctor'),
        ('dentist', 'Dentist'),
        ('nurse', 'Nurse'),
        ('therapist', 'Therapist'),
        ('all', 'All')
    ], string='Applicable For', default='all', required=True)
    
    description = fields.Text(
        string='Description',
        translate=True
    )
    
    parent_id = fields.Many2one(
        'clinic.staff.specialization',
        string='Parent Specialization',
        help='For sub-specializations'
    )
    
    child_ids = fields.One2many(
        'clinic.staff.specialization',
        'parent_id',
        string='Sub-specializations'
    )
    
    active = fields.Boolean(string='Active', default=True)
    
    _sql_constraints = [
        ('name_unique', 'UNIQUE(name, category_id)', 'Specialization name must be unique within category!'),
        ('code_unique', 'UNIQUE(code)', 'Specialization code must be unique!'),
    ]
    
    @api.depends('name', 'category_id')
    def name_get(self):
        result = []
        for record in self:
            if record.category_id:
                name = f"[{record.category_id.name}] {record.name}"
            else:
                name = record.name
            result.append((record.id, name))
        return result


class ClinicStaffSpecializationCategory(models.Model):
    _name = 'clinic.staff.specialization.category'
    _description = 'Specialization Category'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Category Name',
        required=True,
        translate=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    active = fields.Boolean(string='Active', default=True)
    
    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Category name must be unique!'),
    ]