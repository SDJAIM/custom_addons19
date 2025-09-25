# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class PrescriptionTemplate(models.Model):
    _name = 'clinic.prescription.template'
    _description = 'Prescription Template'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'category_id, name'
    
    # Basic Information
    name = fields.Char(
        string='Template Name',
        required=True,
        tracking=True
    )
    
    code = fields.Char(
        string='Template Code',
        index=True
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    
    # Category
    category_id = fields.Many2one(
        'clinic.prescription.template.category',
        string='Category',
        required=True,
        tracking=True
    )
    
    # Condition/Diagnosis
    diagnosis_ids = fields.Many2many(
        'clinic.diagnosis',
        string='Diagnoses',
        help='Conditions this template is designed for'
    )
    
    indication = fields.Text(
        string='Indication',
        help='When to use this template'
    )
    
    # Template Type
    template_type = fields.Selection([
        ('standard', 'Standard Protocol'),
        ('starter', 'Starter Pack'),
        ('chronic', 'Chronic Management'),
        ('acute', 'Acute Treatment'),
        ('prophylaxis', 'Prophylaxis'),
        ('post_op', 'Post-Operative'),
        ('pediatric', 'Pediatric'),
        ('geriatric', 'Geriatric'),
    ], string='Type', default='standard', required=True)
    
    # Age Restrictions
    min_age = fields.Integer(
        string='Minimum Age',
        help='Minimum patient age in years'
    )
    
    max_age = fields.Integer(
        string='Maximum Age',
        help='Maximum patient age in years'
    )
    
    age_unit = fields.Selection([
        ('years', 'Years'),
        ('months', 'Months'),
        ('days', 'Days'),
    ], string='Age Unit', default='years')
    
    # Gender Restriction
    gender_restriction = fields.Selection([
        ('all', 'All'),
        ('male', 'Male Only'),
        ('female', 'Female Only'),
    ], string='Gender', default='all')
    
    # Template Lines
    line_ids = fields.One2many(
        'clinic.prescription.template.line',
        'template_id',
        string='Medications',
        copy=True
    )
    
    # Instructions
    general_instructions = fields.Text(
        string='General Instructions',
        help='Instructions to include with all prescriptions from this template'
    )
    
    follow_up_instructions = fields.Text(
        string='Follow-up Instructions'
    )
    
    # Warnings
    warnings = fields.Text(
        string='Warnings',
        help='Important warnings for this protocol'
    )
    
    contraindications = fields.Text(
        string='Contraindications'
    )
    
    # Clinical Guidelines
    clinical_guideline = fields.Text(
        string='Clinical Guideline',
        help='Reference to clinical guidelines'
    )
    
    evidence_level = fields.Selection([
        ('A', 'Level A - High Quality Evidence'),
        ('B', 'Level B - Moderate Quality Evidence'),
        ('C', 'Level C - Low Quality Evidence'),
        ('expert', 'Expert Opinion'),
    ], string='Evidence Level')
    
    # Usage Statistics
    usage_count = fields.Integer(
        string='Times Used',
        compute='_compute_usage_count',
        store=True
    )
    
    last_used_date = fields.Date(
        string='Last Used',
        compute='_compute_last_used',
        store=True
    )
    
    # Approval
    is_approved = fields.Boolean(
        string='Approved',
        default=False,
        tracking=True
    )
    
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True
    )
    
    approval_date = fields.Date(
        string='Approval Date',
        readonly=True
    )
    
    # Review
    review_date = fields.Date(
        string='Next Review Date',
        tracking=True
    )
    
    notes = fields.Text(
        string='Internal Notes'
    )
    
    prescription_ids = fields.One2many(
        'clinic.prescription',
        'template_id',
        string='Prescriptions'
    )
    
    @api.depends('prescription_ids')
    def _compute_usage_count(self):
        for template in self:
            template.usage_count = len(template.prescription_ids)
    
    @api.depends('prescription_ids.create_date')
    def _compute_last_used(self):
        for template in self:
            if template.prescription_ids:
                last_prescription = template.prescription_ids.sorted('create_date', reverse=True)[0]
                template.last_used_date = last_prescription.create_date.date()
            else:
                template.last_used_date = False
    
    @api.constrains('min_age', 'max_age')
    def _check_age_range(self):
        for template in self:
            if template.min_age and template.max_age and template.min_age > template.max_age:
                raise ValidationError(_("Maximum age must be greater than minimum age."))
    
    def action_approve(self):
        """Approve template for use"""
        self.ensure_one()
        
        if self.is_approved:
            raise UserError(_("Template is already approved."))
        
        self.write({
            'is_approved': True,
            'approved_by': self.env.user.id,
            'approval_date': fields.Date.today(),
        })
        
        return True
    
    def action_create_prescription(self):
        """Create prescription from template"""
        self.ensure_one()
        
        if not self.is_approved:
            raise UserError(_("Cannot use unapproved template."))
        
        # Create prescription wizard
        return {
            'name': _('Create Prescription from Template'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.prescription.from.template.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
            }
        }
    
    def action_duplicate(self):
        """Duplicate template"""
        self.ensure_one()
        
        new_template = self.copy({
            'name': f"{self.name} (Copy)",
            'is_approved': False,
            'approved_by': False,
            'approval_date': False,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.prescription.template',
            'res_id': new_template.id,
            'view_mode': 'form',
        }
    
    def check_patient_eligibility(self, patient_id):
        """Check if patient is eligible for this template"""
        self.ensure_one()
        
        patient = self.env['clinic.patient'].browse(patient_id)
        errors = []
        
        # Check age
        if self.min_age or self.max_age:
            age = patient.age_years
            if self.age_unit == 'months':
                age = patient.age_months
            elif self.age_unit == 'days':
                age = patient.age_days
            
            if self.min_age and age < self.min_age:
                errors.append(f"Patient age ({age}) is below minimum ({self.min_age})")
            if self.max_age and age > self.max_age:
                errors.append(f"Patient age ({age}) is above maximum ({self.max_age})")
        
        # Check gender
        if self.gender_restriction != 'all':
            if self.gender_restriction != patient.gender:
                errors.append(f"Template is for {self.gender_restriction} patients only")
        
        # Check contraindications
        # This would check patient allergies and conditions against template contraindications
        
        return errors
    
    def name_get(self):
        result = []
        for template in self:
            name = template.name
            if template.category_id:
                name = f"[{template.category_id.name}] {name}"
            result.append((template.id, name))
        return result


class PrescriptionTemplateLine(models.Model):
    _name = 'clinic.prescription.template.line'
    _description = 'Prescription Template Line'
    _order = 'sequence, id'
    
    template_id = fields.Many2one(
        'clinic.prescription.template',
        string='Template',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    medication_id = fields.Many2one(
        'clinic.medication',
        string='Medication',
        required=True,
        domain=[('active', '=', True)]
    )
    
    dose = fields.Float(
        string='Dose',
        required=True
    )
    
    dose_unit_id = fields.Many2one(
        'clinic.dose.unit',
        string='Dose Unit',
        required=True
    )
    
    route_id = fields.Many2one(
        'clinic.medication.route',
        string='Route',
        required=True
    )
    
    frequency_id = fields.Many2one(
        'clinic.frequency',
        string='Frequency',
        required=True
    )
    
    duration = fields.Integer(
        string='Duration (Days)',
        required=True
    )
    
    quantity = fields.Float(
        string='Total Quantity',
        compute='_compute_quantity',
        store=True
    )
    
    instructions = fields.Text(
        string='Instructions'
    )
    
    allow_substitution = fields.Boolean(
        string='Allow Substitution',
        default=True
    )
    
    prn = fields.Boolean(
        string='PRN',
        default=False
    )
    
    prn_condition = fields.Char(
        string='PRN Condition'
    )
    
    notes = fields.Text(
        string='Notes'
    )
    
    @api.depends('dose', 'frequency_id', 'duration')
    def _compute_quantity(self):
        for line in self:
            if line.frequency_id and line.duration:
                daily_doses = line.frequency_id.times_per_day
                line.quantity = line.dose * daily_doses * line.duration
            else:
                line.quantity = line.dose
    
    @api.onchange('medication_id')
    def _onchange_medication_id(self):
        if self.medication_id:
            if self.medication_id.default_dose:
                self.dose = self.medication_id.default_dose
            if self.medication_id.default_dose_unit_id:
                self.dose_unit_id = self.medication_id.default_dose_unit_id
            if self.medication_id.default_route_id:
                self.route_id = self.medication_id.default_route_id
            if self.medication_id.default_frequency_id:
                self.frequency_id = self.medication_id.default_frequency_id


class PrescriptionTemplateCategory(models.Model):
    _name = 'clinic.prescription.template.category'
    _description = 'Prescription Template Category'
    _order = 'sequence, name'
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'complete_name'
    
    name = fields.Char(
        string='Category Name',
        required=True
    )
    
    complete_name = fields.Char(
        string='Complete Name',
        compute='_compute_complete_name',
        store=True
    )
    
    code = fields.Char(
        string='Code'
    )
    
    parent_id = fields.Many2one(
        'clinic.prescription.template.category',
        string='Parent Category',
        index=True,
        ondelete='cascade'
    )
    
    parent_path = fields.Char(
        index=True
    )
    
    child_ids = fields.One2many(
        'clinic.prescription.template.category',
        'parent_id',
        string='Child Categories'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    template_ids = fields.One2many(
        'clinic.prescription.template',
        'category_id',
        string='Templates'
    )
    
    template_count = fields.Integer(
        string='Template Count',
        compute='_compute_template_count'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = f"{category.parent_id.complete_name} / {category.name}"
            else:
                category.complete_name = category.name
    
    @api.depends('template_ids')
    def _compute_template_count(self):
        for category in self:
            category.template_count = len(category.template_ids)
    
    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError(_('You cannot create recursive categories.'))