# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, date
from odoo.exceptions import ValidationError


class TreatmentPlanLine(models.Model):
    _name = 'clinic.treatment.plan.line'
    _description = 'Treatment Plan Line'
    _order = 'plan_id, sequence, id'
    
    plan_id = fields.Many2one(
        'clinic.treatment.plan',
        string='Treatment Plan',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of execution'
    )
    
    procedure_id = fields.Many2one(
        'clinic.treatment.procedure',
        string='Procedure',
        required=True
    )
    
    procedure_code = fields.Char(
        related='procedure_id.code',
        string='Code'
    )
    
    description = fields.Text(
        string='Description',
        help='Additional description or modifications'
    )
    
    # Tooth/Area specific (for dental)
    # NOTE: Uncommented as clinic.tooth is in clinic_dental_chart module
    # which may not be installed. This field should be added dynamically
    # when clinic_dental_chart is installed
    # tooth_ids = fields.Many2many(
    #     'clinic.tooth',
    #     string='Teeth',
    #     help='Specific teeth for this procedure'
    # )
    
    body_area = fields.Char(
        string='Body Area',
        help='Specific body area for medical procedures'
    )
    
    # Scheduling
    planned_date = fields.Date(
        string='Planned Date'
    )
    
    actual_date = fields.Date(
        string='Actual Date'
    )
    
    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Appointment',
        help='Linked appointment for this procedure'
    )
    
    # Staff
    assigned_staff_id = fields.Many2one(
        'clinic.staff',
        string='Assigned To',
        domain="[('state', '=', 'active')]"
    )
    
    performed_by_id = fields.Many2one(
        'clinic.staff',
        string='Performed By'
    )
    
    # State
    state = fields.Selection([
        ('planned', 'Planned'),
        ('ready', 'Ready'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed')
    ], string='Status', default='planned')
    
    # Financial
    estimated_cost = fields.Float(
        string='Estimated Cost'
    )
    
    actual_cost = fields.Float(
        string='Actual Cost'
    )
    
    insurance_coverage = fields.Float(
        string='Insurance Coverage'
    )
    
    patient_cost = fields.Float(
        string='Patient Cost',
        compute='_compute_patient_cost',
        store=True
    )
    
    # Results
    result = fields.Text(
        string='Result/Outcome'
    )
    
    complications = fields.Text(
        string='Complications'
    )
    
    success = fields.Boolean(
        string='Successful',
        default=True
    )
    
    # Documents
    before_images = fields.Many2many(
        'ir.attachment',
        'treatment_line_before_images_rel',
        'line_id',
        'attachment_id',
        string='Before Images'
    )
    
    after_images = fields.Many2many(
        'ir.attachment',
        'treatment_line_after_images_rel',
        'line_id',
        'attachment_id',
        string='After Images'
    )
    
    notes = fields.Text(
        string='Notes'
    )
    
    # Related fields
    patient_id = fields.Many2one(
        related='plan_id.patient_id',
        string='Patient',
        store=True
    )
    
    plan_state = fields.Selection(
        related='plan_id.state',
        string='Plan Status'
    )
    
    @api.depends('estimated_cost', 'insurance_coverage')
    def _compute_patient_cost(self):
        for record in self:
            record.patient_cost = max(0, record.estimated_cost - record.insurance_coverage)
    
    @api.constrains('actual_cost')
    def _check_actual_cost(self):
        for record in self:
            if record.actual_cost < 0:
                raise ValidationError(_("Actual cost cannot be negative!"))
    
    def action_start(self):
        """Start the procedure"""
        for record in self:
            if record.state != 'ready':
                raise ValidationError(_('Only ready procedures can be started.'))
            
            record.write({
                'state': 'in_progress',
                'actual_date': fields.Date.today() if not record.actual_date else record.actual_date
            })
    
    def action_complete(self):
        """Complete the procedure"""
        for record in self:
            if record.state != 'in_progress':
                raise ValidationError(_('Only in-progress procedures can be completed.'))
            
            record.write({
                'state': 'done',
                'actual_date': fields.Date.today() if not record.actual_date else record.actual_date
            })
            
            # Mark next procedure as ready
            next_line = record.plan_id.line_ids.filtered(
                lambda l: l.sequence > record.sequence and l.state == 'planned'
            )
            if next_line:
                next_line[0].state = 'ready'
    
    def action_cancel(self):
        """Cancel the procedure"""
        for record in self:
            if record.state == 'done':
                raise ValidationError(_('Completed procedures cannot be cancelled.'))
            
            record.state = 'cancelled'
    
    def action_fail(self):
        """Mark procedure as failed"""
        for record in self:
            if record.state != 'in_progress':
                raise ValidationError(_('Only in-progress procedures can be marked as failed.'))
            
            record.write({
                'state': 'failed',
                'success': False
            })
    
    def action_schedule(self):
        """Open appointment scheduling wizard"""
        self.ensure_one()
        return {
            'name': _('Schedule Procedure'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.appointment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_staff_id': self.assigned_staff_id.id if self.assigned_staff_id else False,
                'default_notes': f"Procedure: {self.procedure_id.name}",
                'treatment_line_id': self.id
            }
        }