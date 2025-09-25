# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TreatmentProcedure(models.Model):
    _name = 'clinic.treatment.procedure'
    _description = 'Treatment Procedure'
    _order = 'category_id, sequence, name'
    
    name = fields.Char(
        string='Procedure Name',
        required=True,
        translate=True
    )
    
    code = fields.Char(
        string='Procedure Code',
        required=True,
        help='Internal or insurance code'
    )
    
    category_id = fields.Many2one(
        'clinic.procedure.category',
        string='Category',
        required=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    service_type = fields.Selection([
        ('medical', 'Medical'),
        ('dental', 'Dental'),
        ('surgical', 'Surgical'),
        ('diagnostic', 'Diagnostic'),
        ('preventive', 'Preventive'),
        ('cosmetic', 'Cosmetic')
    ], string='Service Type', required=True, default='medical')
    
    description = fields.Text(
        string='Description',
        translate=True
    )
    
    # Duration and complexity
    duration = fields.Float(
        string='Duration (hours)',
        default=0.5,
        help='Estimated duration of the procedure'
    )
    
    complexity = fields.Selection([
        ('simple', 'Simple'),
        ('moderate', 'Moderate'),
        ('complex', 'Complex'),
        ('very_complex', 'Very Complex')
    ], string='Complexity', default='moderate')
    
    # Requirements
    requires_anesthesia = fields.Boolean(
        string='Requires Anesthesia'
    )
    
    anesthesia_type = fields.Selection([
        ('local', 'Local'),
        ('regional', 'Regional'),
        ('general', 'General'),
        ('sedation', 'Sedation')
    ], string='Anesthesia Type')
    
    requires_fasting = fields.Boolean(
        string='Requires Fasting'
    )
    
    fasting_hours = fields.Integer(
        string='Fasting Hours',
        help='Hours of fasting required before procedure'
    )
    
    # Staff requirements
    min_staff_required = fields.Integer(
        string='Minimum Staff Required',
        default=1
    )
    
    specialist_required = fields.Boolean(
        string='Specialist Required'
    )
    
    specialization_ids = fields.Many2many(
        'clinic.staff.specialization',
        string='Required Specializations'
    )
    
    # Room requirements
    room_type_required = fields.Selection([
        ('consultation', 'Consultation'),
        ('surgery', 'Surgery'),
        ('emergency', 'Emergency'),
        ('imaging', 'Imaging/X-Ray'),
        ('laboratory', 'Laboratory')
    ], string='Room Type Required')
    
    # Financial
    standard_cost = fields.Float(
        string='Standard Cost'
    )
    
    insurance_coverage_percentage = fields.Float(
        string='Typical Insurance Coverage (%)',
        default=80
    )
    
    # Risk and contraindications
    risk_level = fields.Selection([
        ('low', 'Low Risk'),
        ('moderate', 'Moderate Risk'),
        ('high', 'High Risk')
    ], string='Risk Level', default='low')
    
    contraindications = fields.Text(
        string='Contraindications'
    )
    
    precautions = fields.Text(
        string='Precautions'
    )
    
    # Recovery
    recovery_time_days = fields.Integer(
        string='Recovery Time (days)'
    )
    
    post_procedure_instructions = fields.Html(
        string='Post-Procedure Instructions'
    )
    
    # Follow-up
    requires_follow_up = fields.Boolean(
        string='Requires Follow-up'
    )
    
    follow_up_days = fields.Integer(
        string='Follow-up After (days)'
    )
    
    # Materials/Equipment
    materials_required = fields.Text(
        string='Materials Required'
    )
    
    equipment_required = fields.Text(
        string='Equipment Required'
    )
    
    # Documentation
    consent_template = fields.Html(
        string='Consent Template'
    )
    
    preparation_instructions = fields.Html(
        string='Patient Preparation Instructions'
    )
    
    # Statistics
    success_rate = fields.Float(
        string='Success Rate (%)',
        default=95
    )
    
    complication_rate = fields.Float(
        string='Complication Rate (%)',
        default=5
    )
    
    # Settings
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    is_emergency = fields.Boolean(
        string='Emergency Procedure'
    )
    
    can_repeat = fields.Boolean(
        string='Can Be Repeated',
        default=True
    )
    
    min_repeat_interval_days = fields.Integer(
        string='Minimum Repeat Interval (days)'
    )
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Procedure code must be unique!'),
    ]
    
    @api.constrains('standard_cost')
    def _check_standard_cost(self):
        for record in self:
            if record.standard_cost < 0:
                raise ValidationError(_("Standard cost cannot be negative!"))
    
    @api.constrains('duration')
    def _check_duration(self):
        for record in self:
            if record.duration <= 0:
                raise ValidationError(_("Duration must be greater than zero!"))
    
    @api.onchange('requires_anesthesia')
    def _onchange_requires_anesthesia(self):
        if not self.requires_anesthesia:
            self.anesthesia_type = False
    
    @api.onchange('requires_fasting')
    def _onchange_requires_fasting(self):
        if not self.requires_fasting:
            self.fasting_hours = 0


class ProcedureCategory(models.Model):
    _name = 'clinic.procedure.category'
    _description = 'Procedure Category'
    _order = 'parent_id, sequence, name'
    
    name = fields.Char(
        string='Category Name',
        required=True,
        translate=True
    )
    
    code = fields.Char(
        string='Category Code'
    )
    
    parent_id = fields.Many2one(
        'clinic.procedure.category',
        string='Parent Category'
    )
    
    child_ids = fields.One2many(
        'clinic.procedure.category',
        'parent_id',
        string='Sub-categories'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    service_type = fields.Selection([
        ('medical', 'Medical'),
        ('dental', 'Dental'),
        ('all', 'All')
    ], string='Service Type', default='all')
    
    description = fields.Text(
        string='Description'
    )
    
    procedure_count = fields.Integer(
        string='Procedures',
        compute='_compute_procedure_count'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Category code must be unique!'),
    ]
    
    def _compute_procedure_count(self):
        for record in self:
            record.procedure_count = self.env['clinic.treatment.procedure'].search_count([
                ('category_id', '=', record.id)
            ])
    
    @api.depends('name', 'parent_id.name')
    def name_get(self):
        result = []
        for record in self:
            if record.parent_id:
                name = f"{record.parent_id.name} / {record.name}"
            else:
                name = record.name
            result.append((record.id, name))
        return result