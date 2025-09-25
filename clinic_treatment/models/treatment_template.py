# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class TreatmentTemplate(models.Model):
    _name = 'clinic.treatment.template'
    _description = 'Treatment Plan Template'
    _order = 'category_id, sequence, name'
    
    name = fields.Char(
        string='Template Name',
        required=True,
        translate=True
    )
    
    code = fields.Char(
        string='Template Code'
    )
    
    category_id = fields.Many2one(
        'clinic.treatment.template.category',
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
        ('both', 'Both')
    ], string='Service Type', default='medical', required=True)
    
    description = fields.Text(
        string='Description',
        translate=True
    )
    
    # Conditions
    diagnosis_ids = fields.Many2many(
        'clinic.diagnosis',
        string='Applicable Diagnoses',
        help='Diagnoses this template is designed for'
    )
    
    # Template lines
    line_ids = fields.One2many(
        'clinic.treatment.template.line',
        'template_id',
        string='Procedures'
    )
    
    # Duration
    estimated_duration_days = fields.Integer(
        string='Estimated Duration (days)',
        compute='_compute_duration',
        store=True
    )
    
    # Cost
    estimated_total_cost = fields.Float(
        string='Estimated Total Cost',
        compute='_compute_total_cost',
        store=True
    )
    
    # Instructions
    objectives = fields.Text(
        string='Treatment Objectives'
    )
    
    expected_outcomes = fields.Text(
        string='Expected Outcomes'
    )
    
    contraindications = fields.Text(
        string='Contraindications'
    )
    
    # Usage statistics
    usage_count = fields.Integer(
        string='Times Used',
        compute='_compute_usage_count'
    )
    
    success_rate = fields.Float(
        string='Success Rate (%)',
        help='Based on completed treatment plans using this template'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    @api.depends('line_ids')
    def _compute_duration(self):
        for record in self:
            if record.line_ids:
                # Calculate based on sequential procedures
                total_days = sum(record.line_ids.mapped('estimated_days'))
                record.estimated_duration_days = total_days
            else:
                record.estimated_duration_days = 0
    
    @api.depends('line_ids.estimated_cost')
    def _compute_total_cost(self):
        for record in self:
            record.estimated_total_cost = sum(record.line_ids.mapped('estimated_cost'))
    
    def _compute_usage_count(self):
        for record in self:
            record.usage_count = self.env['clinic.treatment.plan'].search_count([
                ('template_id', '=', record.id)
            ])
    
    def action_create_plan(self):
        """Create a treatment plan from this template"""
        self.ensure_one()
        return {
            'name': _('New Treatment Plan'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.treatment.plan',
            'view_mode': 'form',
            'context': {
                'default_template_id': self.id,
                'default_name': self.name,
                'default_objectives': self.objectives,
            }
        }


class TreatmentTemplateLine(models.Model):
    _name = 'clinic.treatment.template.line'
    _description = 'Treatment Template Line'
    _order = 'template_id, sequence'
    
    template_id = fields.Many2one(
        'clinic.treatment.template',
        string='Template',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    procedure_id = fields.Many2one(
        'clinic.treatment.procedure',
        string='Procedure',
        required=True
    )
    
    estimated_days = fields.Integer(
        string='Days After Start',
        help='Number of days after treatment start'
    )
    
    estimated_cost = fields.Float(
        string='Estimated Cost'
    )
    
    is_optional = fields.Boolean(
        string='Optional',
        default=False
    )
    
    notes = fields.Text(
        string='Notes'
    )


class TreatmentTemplateCategory(models.Model):
    _name = 'clinic.treatment.template.category'
    _description = 'Treatment Template Category'
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
    
    active = fields.Boolean(
        string='Active',
        default=True
    )