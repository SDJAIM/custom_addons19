# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import json
import logging

_logger = logging.getLogger(__name__)


class DentalChart(models.Model):
    _name = 'clinic.dental.chart'
    _description = 'Patient Dental Chart'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'patient_id'
    _order = 'create_date desc'
    
    # Basic Information
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        tracking=True,
        index=True,
        ondelete='restrict'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    
    # Chart Type
    chart_type = fields.Selection([
        ('adult', 'Adult (Permanent)'),
        ('child', 'Child (Primary)'),
        ('mixed', 'Mixed Dentition'),
    ], string='Chart Type', default='adult', required=True, tracking=True)
    
    notation_system = fields.Selection([
        ('universal', 'Universal Numbering'),
        ('palmer', 'Palmer Notation'),
        ('fdi', 'FDI Two-Digit'),
    ], string='Notation System', default='universal', required=True)
    
    # Teeth
    tooth_ids = fields.One2many(
        'clinic.tooth',
        'chart_id',
        string='Teeth'
    )
    
    # Chart Data (JSON for OWL component)
    chart_data = fields.Text(
        string='Chart Data',
        default='{}',
        help='JSON data for tooth states and procedures'
    )
    
    # Summary Fields
    missing_teeth_count = fields.Integer(
        string='Missing Teeth',
        compute='_compute_teeth_summary',
        store=True
    )
    
    decayed_teeth_count = fields.Integer(
        string='Decayed Teeth',
        compute='_compute_teeth_summary',
        store=True
    )
    
    filled_teeth_count = fields.Integer(
        string='Filled Teeth',
        compute='_compute_teeth_summary',
        store=True
    )
    
    crowned_teeth_count = fields.Integer(
        string='Crowned Teeth',
        compute='_compute_teeth_summary',
        store=True
    )
    
    # DMFT Index (Decayed, Missing, Filled Teeth)
    dmft_score = fields.Integer(
        string='DMFT Score',
        compute='_compute_dmft_score',
        store=True,
        help='Decayed, Missing, and Filled Teeth index'
    )
    
    # Related Records
    appointment_ids = fields.One2many(
        'clinic.appointment',
        compute='_compute_appointments',
        string='Appointments'
    )
    
    treatment_ids = fields.One2many(
        'clinic.treatment.line',
        compute='_compute_treatments',
        string='Treatments'
    )
    
    # Last Update
    last_update = fields.Datetime(
        string='Last Updated',
        tracking=True,
        default=fields.Datetime.now
    )
    
    last_exam_date = fields.Date(
        string='Last Examination',
        tracking=True
    )
    
    next_exam_date = fields.Date(
        string='Next Examination',
        tracking=True
    )
    
    # Periodontal Status
    has_periodontal_disease = fields.Boolean(
        string='Periodontal Disease',
        default=False,
        tracking=True
    )
    
    periodontal_chart_id = fields.Many2one(
        'clinic.periodontal.chart',
        string='Periodontal Chart'
    )
    
    # Notes
    clinical_notes = fields.Text(
        string='Clinical Notes'
    )
    
    # X-rays
    xray_ids = fields.One2many(
        'ir.attachment',
        compute='_compute_xrays',
        string='X-rays'
    )
    
    xray_count = fields.Integer(
        string='X-rays',
        compute='_compute_xrays'
    )
    
    @api.depends('tooth_ids.state')
    def _compute_teeth_summary(self):
        for chart in self:
            teeth = chart.tooth_ids
            chart.missing_teeth_count = len(teeth.filtered(lambda t: t.state == 'missing'))
            chart.decayed_teeth_count = len(teeth.filtered(lambda t: t.state == 'decayed'))
            chart.filled_teeth_count = len(teeth.filtered(lambda t: t.state == 'filled'))
            chart.crowned_teeth_count = len(teeth.filtered(lambda t: t.state == 'crown'))
    
    @api.depends('missing_teeth_count', 'decayed_teeth_count', 'filled_teeth_count')
    def _compute_dmft_score(self):
        for chart in self:
            chart.dmft_score = (
                chart.missing_teeth_count + 
                chart.decayed_teeth_count + 
                chart.filled_teeth_count
            )
    
    def _compute_appointments(self):
        for chart in self:
            chart.appointment_ids = self.env['clinic.appointment'].search([
                ('patient_id', '=', chart.patient_id.id),
                ('service_type', 'in', ['dental', 'dental_emergency'])
            ])
    
    def _compute_treatments(self):
        for chart in self:
            chart.treatment_ids = self.env['clinic.treatment.line'].search([
                ('patient_id', '=', chart.patient_id.id),
                ('tooth_ids', '!=', False)
            ])
    
    def _compute_xrays(self):
        for chart in self:
            attachments = self.env['ir.attachment'].search([
                ('res_model', '=', 'clinic.dental.chart'),
                ('res_id', '=', chart.id),
                ('name', 'ilike', 'xray')
            ])
            chart.xray_ids = attachments
            chart.xray_count = len(attachments)
    
    @api.model
    def create(self, vals):
        chart = super().create(vals)
        
        # Initialize teeth based on chart type
        chart._initialize_teeth()
        
        return chart
    
    def _initialize_teeth(self):
        """Initialize teeth based on chart type"""
        self.ensure_one()
        
        if self.chart_type == 'adult':
            tooth_numbers = list(range(1, 33))  # 32 permanent teeth
        elif self.chart_type == 'child':
            # Primary teeth (A-T in universal notation)
            tooth_numbers = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
                           'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T']
        else:  # mixed
            # Both primary and permanent teeth
            tooth_numbers = list(range(1, 33)) + ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
                                                 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T']
        
        for number in tooth_numbers:
            self.env['clinic.tooth'].create({
                'chart_id': self.id,
                'tooth_number': str(number),
                'is_primary': isinstance(number, str),
                'state': 'healthy',
            })
        
        # Initialize chart data for OWL component
        self._update_chart_data()
    
    def _update_chart_data(self):
        """Update JSON chart data for OWL component"""
        self.ensure_one()
        
        data = {
            'notation': self.notation_system,
            'type': self.chart_type,
            'teeth': {}
        }
        
        for tooth in self.tooth_ids:
            data['teeth'][tooth.tooth_number] = {
                'state': tooth.state,
                'conditions': tooth.condition_ids.mapped('code'),
                'procedures': tooth.procedure_ids.mapped('name'),
                'notes': tooth.notes or '',
                'surfaces': tooth._get_surface_data(),
            }
        
        self.chart_data = json.dumps(data)
    
    def action_update_tooth(self, tooth_number, updates):
        """Update tooth from OWL component"""
        self.ensure_one()
        
        tooth = self.tooth_ids.filtered(lambda t: t.tooth_number == str(tooth_number))
        if not tooth:
            raise UserError(_("Tooth %s not found") % tooth_number)
        
        # Update tooth fields
        if 'state' in updates:
            tooth.state = updates['state']
        
        if 'notes' in updates:
            tooth.notes = updates['notes']
        
        if 'procedure_id' in updates:
            # Add procedure to tooth
            tooth.procedure_ids = [(4, updates['procedure_id'])]
        
        # Create history entry
        self.env['clinic.tooth.history'].create({
            'tooth_id': tooth.id,
            'date': fields.Date.today(),
            'action': updates.get('action', 'update'),
            'description': updates.get('description', 'Manual update'),
            'user_id': self.env.user.id,
        })
        
        # Update chart data
        self._update_chart_data()
        self.last_update = fields.Datetime.now()
        
        return True
    
    def action_apply_procedure(self):
        """Open wizard to apply procedure to teeth"""
        self.ensure_one()
        
        return {
            'name': _('Apply Dental Procedure'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.dental.procedure.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_chart_id': self.id,
                'default_patient_id': self.patient_id.id,
            }
        }
    
    def action_view_history(self):
        """View tooth history"""
        self.ensure_one()
        
        return {
            'name': _('Tooth History'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.tooth.history',
            'view_mode': 'tree,form',
            'domain': [('tooth_id.chart_id', '=', self.id)],
            'context': {'create': False}
        }
    
    def action_print_chart(self):
        """Print dental chart"""
        self.ensure_one()
        
        return self.env.ref('clinic_dental_chart.action_report_dental_chart').report_action(self)
    
    def action_view_xrays(self):
        """
        View and manage X-ray images for this dental chart.

        Opens a view displaying all X-ray attachments with options to
        upload new X-rays, view existing ones, and annotate images.
        X-rays are filtered by attachment name containing 'xray'.

        Returns:
            dict: Action dictionary for opening the X-ray management view
        """
        self.ensure_one()
        
        return {
            'name': _('X-rays'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'kanban,form',
            'domain': [
                ('res_model', '=', 'clinic.dental.chart'),
                ('res_id', '=', self.id),
            ],
            'context': {
                'default_res_model': 'clinic.dental.chart',
                'default_res_id': self.id,
            }
        }
    
    def action_periodontal_chart(self):
        """Open or create periodontal chart"""
        self.ensure_one()
        
        if not self.periodontal_chart_id:
            # Create periodontal chart
            perio_chart = self.env['clinic.periodontal.chart'].create({
                'patient_id': self.patient_id.id,
                'dental_chart_id': self.id,
            })
            self.periodontal_chart_id = perio_chart
        
        return {
            'name': _('Periodontal Chart'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.periodontal.chart',
            'res_id': self.periodontal_chart_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    @api.model
    def get_chart_data(self, patient_id):
        """API method to get chart data for OWL component"""
        chart = self.search([
            ('patient_id', '=', patient_id),
            ('active', '=', True)
        ], limit=1)
        
        if not chart:
            # Create new chart if doesn't exist
            chart = self.create({
                'patient_id': patient_id,
                'chart_type': 'adult',
            })
        
        return json.loads(chart.chart_data or '{}')
    
    def name_get(self):
        result = []
        for chart in self:
            name = f"{chart.patient_id.name} - Dental Chart"
            if chart.chart_type != 'adult':
                name += f" ({chart.chart_type.title()})"
            result.append((chart.id, name))
        return result