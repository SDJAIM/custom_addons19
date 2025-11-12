# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, date, timedelta
from odoo.exceptions import ValidationError, UserError


class TreatmentPlan(models.Model):
    _name = 'clinic.treatment.plan'
    _description = 'Treatment Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'create_date desc'
    
    # ========================
    # Basic Information
    # ========================
    name = fields.Char(
        string='Plan Name',
        required=True,
        tracking=True,
        help='Descriptive name for the treatment plan'
    )
    
    plan_number = fields.Char(
        string='Plan Number',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New')
    )
    
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        tracking=True,
        ondelete='restrict'
    )
    
    doctor_id = fields.Many2one(
        'clinic.staff',
        string='Primary Doctor',
        required=True,
        tracking=True,
        domain="[('staff_type', 'in', ['doctor', 'dentist']), ('state', '=', 'active')]"
    )
    
    template_id = fields.Many2one(
        'clinic.treatment.template',
        string='Based on Template',
        help='Treatment template used as basis'
    )
    
    # ========================
    # Plan Details
    # ========================
    diagnosis = fields.Text(
        string='Diagnosis',
        required=True,
        help='Primary diagnosis for this treatment plan'
    )
    
    objectives = fields.Text(
        string='Treatment Objectives',
        help='Goals to achieve with this treatment'
    )
    
    start_date = fields.Date(
        string='Start Date',
        default=fields.Date.today,
        tracking=True
    )
    
    end_date = fields.Date(
        string='Expected End Date',
        tracking=True
    )
    
    actual_end_date = fields.Date(
        string='Actual End Date',
        tracking=True
    )
    
    duration_days = fields.Integer(
        string='Duration (Days)',
        compute='_compute_duration',
        store=True
    )
    
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string='Priority', default='medium', tracking=True)
    
    # ========================
    # Treatment Lines
    # ========================
    line_ids = fields.One2many(
        'clinic.treatment.plan.line',
        'plan_id',
        string='Treatment Steps'
    )
    
    procedure_count = fields.Integer(
        string='Procedures',
        compute='_compute_counts'
    )
    
    # ========================
    # State Management
    # ========================
    state = fields.Selection([
        ('draft', 'Draft'),
        ('proposed', 'Proposed'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    # ========================
    # Progress Tracking
    # ========================
    progress = fields.Float(
        string='Progress (%)',
        compute='_compute_progress',
        store=True,
        aggregator='avg'
    )
    
    completed_procedures = fields.Integer(
        string='Completed',
        compute='_compute_counts'
    )
    
    total_procedures = fields.Integer(
        string='Total',
        compute='_compute_counts'
    )
    
    # ========================
    # Financial
    # ========================
    estimated_cost = fields.Float(
        string='Estimated Cost',
        compute='_compute_costs',
        store=True
    )
    
    actual_cost = fields.Float(
        string='Actual Cost',
        compute='_compute_costs',
        store=True
    )
    
    insurance_coverage = fields.Float(
        string='Insurance Coverage',
        help='Estimated insurance coverage amount'
    )
    
    patient_cost = fields.Float(
        string='Patient Cost',
        compute='_compute_patient_cost',
        store=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # ========================
    # Consent & Documentation
    # ========================
    requires_consent = fields.Boolean(
        string='Requires Consent',
        default=True
    )
    
    consent_given = fields.Boolean(
        string='Consent Given',
        tracking=True
    )
    
    consent_date = fields.Datetime(
        string='Consent Date'
    )
    
    consent_form_id = fields.Many2one(
        'clinic.treatment.consent',
        string='Consent Form'
    )
    
    # ========================
    # Clinical Notes
    # ========================
    clinical_note_ids = fields.One2many(
        'clinic.clinical.note',
        'treatment_plan_id',
        string='Clinical Notes'
    )
    
    note_count = fields.Integer(
        string='Notes',
        compute='_compute_counts'
    )
    
    # ========================
    # Related Records
    # ========================
    appointment_ids = fields.One2many(
        'clinic.appointment',
        compute='_compute_appointments',
        string='Related Appointments'
    )
    
    appointment_count = fields.Integer(
        string='Appointments',
        compute='_compute_counts'
    )
    
    # ========================
    # Additional Information
    # ========================
    complications = fields.Text(
        string='Complications',
        help='Any complications during treatment'
    )
    
    outcome = fields.Text(
        string='Treatment Outcome',
        help='Final outcome of the treatment'
    )
    
    success_rate = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor')
    ], string='Success Rate')
    
    notes = fields.Text(
        string='Internal Notes'
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    # ========================
    # Computed Fields
    # ========================
    @api.model
    def create(self, vals):
        if vals.get('plan_number', _('New')) == _('New'):
            vals['plan_number'] = self.env['ir.sequence'].next_by_code('clinic.treatment.plan') or _('New')
        
        # If template is used, copy procedures
        if vals.get('template_id'):
            plan = super().create(vals)
            plan._apply_template()
            return plan
        
        return super().create(vals)
    
    @api.depends('name', 'plan_number', 'patient_id')
    def _compute_display_name(self):
        for record in self:
            if record.patient_id:
                record.display_name = f"[{record.plan_number}] {record.name} - {record.patient_id.name}"
            else:
                record.display_name = f"[{record.plan_number}] {record.name}"
    
    @api.depends('start_date', 'end_date', 'actual_end_date')
    def _compute_duration(self):
        for record in self:
            if record.actual_end_date and record.start_date:
                delta = record.actual_end_date - record.start_date
                record.duration_days = delta.days
            elif record.end_date and record.start_date:
                delta = record.end_date - record.start_date
                record.duration_days = delta.days
            else:
                record.duration_days = 0
    
    @api.depends('line_ids', 'line_ids.state')
    def _compute_progress(self):
        for record in self:
            if record.line_ids:
                total = len(record.line_ids)
                completed = len(record.line_ids.filtered(lambda l: l.state == 'done'))
                record.progress = (completed / total) * 100 if total > 0 else 0
            else:
                record.progress = 0
    
    @api.depends('line_ids', 'clinical_note_ids')
    def _compute_counts(self):
        for record in self:
            record.procedure_count = len(record.line_ids)
            record.total_procedures = len(record.line_ids)
            record.completed_procedures = len(record.line_ids.filtered(lambda l: l.state == 'done'))
            record.note_count = len(record.clinical_note_ids)
            
            # Compute appointment count
            record.appointment_count = self.env['clinic.appointment'].search_count([
                ('patient_id', '=', record.patient_id.id),
                ('start', '>=', record.start_date),
                '|',
                ('stop', '<=', record.end_date) if record.end_date else ('id', '>', 0),
                ('stop', '<=', record.actual_end_date) if record.actual_end_date else ('id', '>', 0)
            ])
    
    @api.depends('line_ids.estimated_cost', 'line_ids.actual_cost')
    def _compute_costs(self):
        for record in self:
            record.estimated_cost = sum(record.line_ids.mapped('estimated_cost'))
            record.actual_cost = sum(record.line_ids.mapped('actual_cost'))
    
    @api.depends('estimated_cost', 'insurance_coverage')
    def _compute_patient_cost(self):
        for record in self:
            record.patient_cost = max(0, record.estimated_cost - record.insurance_coverage)
    
    def _compute_appointments(self):
        for record in self:
            record.appointment_ids = self.env['clinic.appointment'].search([
                ('patient_id', '=', record.patient_id.id),
                ('start', '>=', record.start_date),
                '|',
                ('stop', '<=', record.end_date) if record.end_date else ('id', '>', 0),
                ('stop', '<=', record.actual_end_date) if record.actual_end_date else ('id', '>', 0)
            ])
    
    # ========================
    # Business Methods
    # ========================
    def _apply_template(self):
        """Apply template procedures to the plan"""
        self.ensure_one()
        if not self.template_id:
            return
        
        for template_line in self.template_id.line_ids:
            self.env['clinic.treatment.plan.line'].create({
                'plan_id': self.id,
                'procedure_id': template_line.procedure_id.id,
                'sequence': template_line.sequence,
                'estimated_cost': template_line.estimated_cost,
                'notes': template_line.notes,
                'state': 'planned'
            })
    
    def action_propose(self):
        """Submit plan for patient approval"""
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only draft plans can be proposed.'))
            
            if not record.line_ids:
                raise UserError(_('Please add at least one procedure to the plan.'))
            
            record.state = 'proposed'
    
    def action_approve(self):
        """Approve the treatment plan"""
        for record in self:
            if record.state != 'proposed':
                raise UserError(_('Only proposed plans can be approved.'))
            
            if record.requires_consent and not record.consent_given:
                raise UserError(_('Patient consent is required before approval.'))
            
            record.state = 'approved'
    
    def action_start(self):
        """Start the treatment plan"""
        for record in self:
            if record.state != 'approved':
                raise UserError(_('Only approved plans can be started.'))
            
            record.state = 'in_progress'
            
            # Mark first procedure as ready
            first_line = record.line_ids.filtered(lambda l: l.state == 'planned')
            if first_line:
                first_line[0].state = 'ready'
    
    def action_hold(self):
        """Put plan on hold"""
        for record in self:
            if record.state != 'in_progress':
                raise UserError(_('Only in-progress plans can be put on hold.'))
            
            record.state = 'on_hold'
    
    def action_resume(self):
        """Resume plan from hold"""
        for record in self:
            if record.state != 'on_hold':
                raise UserError(_('Only on-hold plans can be resumed.'))
            
            record.state = 'in_progress'
    
    def action_complete(self):
        """Complete the treatment plan"""
        for record in self:
            if record.state != 'in_progress':
                raise UserError(_('Only in-progress plans can be completed.'))
            
            # Check if all procedures are done
            if any(line.state != 'done' for line in record.line_ids):
                raise UserError(_('All procedures must be completed before completing the plan.'))
            
            record.write({
                'state': 'completed',
                'actual_end_date': fields.Date.today(),
                'progress': 100
            })
    
    def action_cancel(self):
        """Cancel the treatment plan"""
        for record in self:
            if record.state in ['completed']:
                raise UserError(_('Completed plans cannot be cancelled.'))
            
            record.state = 'cancelled'
    
    def action_give_consent(self):
        """Record patient consent"""
        self.ensure_one()
        self.write({
            'consent_given': True,
            'consent_date': fields.Datetime.now()
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Patient consent recorded successfully.'),
                'type': 'success',
            }
        }
    
    def action_view_clinical_notes(self):
        """View related clinical notes"""
        self.ensure_one()
        return {
            'name': _('Clinical Notes'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.clinical.note',
            'view_mode': 'tree,form',
            'domain': [('treatment_plan_id', '=', self.id)],
            'context': {
                'default_treatment_plan_id': self.id,
                'default_patient_id': self.patient_id.id,
                'default_doctor_id': self.doctor_id.id,
            }
        }
    
    def action_print_plan(self):
        """Print treatment plan"""
        self.ensure_one()

        # Check if custom report exists
        report = self.env.ref('clinic_treatment.report_treatment_plan', raise_if_not_found=False)

        if report:
            return report.report_action(self)
        else:
            # If no custom report, use standard method
            return {
                'type': 'ir.actions.report',
                'report_name': 'clinic_treatment.treatment_plan_report',
                'report_type': 'qweb-pdf',
                'data': None,
                'context': self.env.context,
                'res_ids': self.ids,
            }