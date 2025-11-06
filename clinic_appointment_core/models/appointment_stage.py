# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class AppointmentStage(models.Model):
    """
    Appointment Stage (Pipeline Stages)
    Replicates Odoo Enterprise Appointments stages functionality
    """
    _name = 'clinic.appointment.stage'
    _description = 'Appointment Stage'
    _order = 'sequence, name'

    # BASIC INFORMATION
    name = fields.Char(string='Name', required=True, translate=True)
    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description', translate=True)
    
    # VISUAL
    fold = fields.Boolean(
        string='Folded in Kanban',
        help='This stage is folded in the kanban view when there are no records in that stage to display.'
    )
    
    # STAGE TYPE (Internal classification)
    stage_type = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('no_show', 'No Show'),
        ('cancelled', 'Cancelled'),
    ], string='Stage Type', required=True, default='draft',
       help='Internal stage type for business logic')
    
    # AUTOMATION
    mail_template_id = fields.Many2one(
        'mail.template',
        string='Email Template',
        domain=[('model', '=', 'clinic.appointment')],
        help='Email template to send when appointment reaches this stage'
    )
    
    send_email = fields.Boolean(
        string='Send Email',
        default=False,
        help='Automatically send email when appointment reaches this stage'
    )
    
    # STATISTICS
    appointment_count = fields.Integer(
        string='Appointments',
        compute='_compute_appointment_count'
    )
    
    @api.depends('name')
    def _compute_appointment_count(self):
        for stage in self:
            stage.appointment_count = self.env['clinic.appointment'].search_count([
                ('stage_id', '=', stage.id)
            ])
    
    def action_view_appointments(self):
        """View appointments in this stage"""
        self.ensure_one()
        return {
            'name': _('Appointments: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.appointment',
            'view_mode': 'tree,form,calendar',
            'domain': [('stage_id', '=', self.id)],
            'context': {'default_stage_id': self.id},
        }
