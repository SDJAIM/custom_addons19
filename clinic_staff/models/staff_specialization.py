# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


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
    
    @api.constrains('name', 'category_id')
    def _check_name_unique(self):
        for record in self:
            domain = [('name', '=', record.name), ('id', '!=', record.id)]
            if record.category_id:
                domain.append(('category_id', '=', record.category_id.id))
            else:
                domain.append(('category_id', '=', False))
            if self.search_count(domain) > 0:
                raise ValidationError(_('Specialization name must be unique within category!'))

    @api.constrains('code')
    def _check_code_unique(self):
        for record in self:
            if record.code and self.search_count([('code', '=', record.code), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_('Specialization code must be unique!'))
    
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
    
    @api.constrains('name')
    def _check_name_unique(self):
        for record in self:
            if self.search_count([('name', '=', record.name), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_('Category name must be unique!'))