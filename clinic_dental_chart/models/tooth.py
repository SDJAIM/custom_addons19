# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Tooth(models.Model):
    _name = 'clinic.tooth'
    _description = 'Individual Tooth'
    _order = 'chart_id, sequence'
    _rec_name = 'display_name'
    
    # Basic Information
    chart_id = fields.Many2one(
        'clinic.dental.chart',
        string='Dental Chart',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        related='chart_id.patient_id',
        store=True,
        readonly=True
    )
    
    tooth_number = fields.Char(
        string='Tooth Number',
        required=True,
        help='Universal numbering (1-32 for adult, A-T for child)'
    )
    
    tooth_name = fields.Char(
        string='Tooth Name',
        compute='_compute_tooth_name',
        store=True
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        compute='_compute_sequence',
        store=True
    )
    
    # Tooth Type
    is_primary = fields.Boolean(
        string='Primary Tooth',
        default=False,
        help='Is this a primary (baby) tooth?'
    )
    
    tooth_type = fields.Selection([
        ('incisor', 'Incisor'),
        ('canine', 'Canine'),
        ('premolar', 'Premolar'),
        ('molar', 'Molar'),
    ], string='Tooth Type', compute='_compute_tooth_type', store=True)
    
    quadrant = fields.Selection([
        ('ur', 'Upper Right'),
        ('ul', 'Upper Left'),
        ('lr', 'Lower Right'),
        ('ll', 'Lower Left'),
    ], string='Quadrant', compute='_compute_quadrant', store=True)
    
    # State
    state = fields.Selection([
        ('healthy', 'Healthy'),
        ('decayed', 'Decayed'),
        ('filled', 'Filled'),
        ('crown', 'Crown'),
        ('bridge', 'Bridge'),
        ('implant', 'Implant'),
        ('root_canal', 'Root Canal'),
        ('missing', 'Missing'),
        ('impacted', 'Impacted'),
        ('fractured', 'Fractured'),
    ], string='State', default='healthy', required=True, tracking=True)
    
    # Surfaces
    surface_mesial = fields.Selection([
        ('healthy', 'Healthy'),
        ('decayed', 'Decayed'),
        ('filled', 'Filled'),
        ('fracture', 'Fractured'),
    ], string='Mesial Surface', default='healthy')
    
    surface_distal = fields.Selection([
        ('healthy', 'Healthy'),
        ('decayed', 'Decayed'),
        ('filled', 'Filled'),
        ('fracture', 'Fractured'),
    ], string='Distal Surface', default='healthy')
    
    surface_occlusal = fields.Selection([
        ('healthy', 'Healthy'),
        ('decayed', 'Decayed'),
        ('filled', 'Filled'),
        ('fracture', 'Fractured'),
    ], string='Occlusal Surface', default='healthy')
    
    surface_buccal = fields.Selection([
        ('healthy', 'Healthy'),
        ('decayed', 'Decayed'),
        ('filled', 'Filled'),
        ('fracture', 'Fractured'),
    ], string='Buccal Surface', default='healthy')
    
    surface_lingual = fields.Selection([
        ('healthy', 'Healthy'),
        ('decayed', 'Decayed'),
        ('filled', 'Filled'),
        ('fracture', 'Fractured'),
    ], string='Lingual Surface', default='healthy')
    
    # Conditions
    condition_ids = fields.Many2many(
        'clinic.tooth.condition',
        string='Conditions'
    )
    
    # Procedures
    procedure_ids = fields.Many2many(
        'clinic.dental.procedure',
        string='Procedures Performed'
    )
    
    planned_procedure_ids = fields.Many2many(
        'clinic.dental.procedure',
        'tooth_planned_procedure_rel',
        string='Planned Procedures'
    )
    
    # Mobility
    mobility = fields.Selection([
        ('0', 'No Mobility'),
        ('1', 'Grade 1 (<1mm)'),
        ('2', 'Grade 2 (1-2mm)'),
        ('3', 'Grade 3 (>2mm)'),
    ], string='Mobility', default='0')
    
    # Periodontal
    pocket_depth = fields.Float(
        string='Pocket Depth (mm)',
        default=0.0
    )
    
    gingival_recession = fields.Float(
        string='Gingival Recession (mm)',
        default=0.0
    )
    
    bleeding_on_probing = fields.Boolean(
        string='Bleeding on Probing',
        default=False
    )
    
    # History
    history_ids = fields.One2many(
        'clinic.tooth.history',
        'tooth_id',
        string='History'
    )
    
    last_procedure_date = fields.Date(
        string='Last Procedure',
        compute='_compute_last_procedure',
        store=True
    )
    
    # X-rays
    xray_ids = fields.Many2many(
        'ir.attachment',
        string='X-rays'
    )
    
    # Notes
    notes = fields.Text(
        string='Clinical Notes'
    )
    
    # Color for visualization
    color = fields.Char(
        string='Display Color',
        compute='_compute_color',
        help='Color code for tooth visualization'
    )
    
    @api.depends('tooth_number')
    def _compute_tooth_name(self):
        tooth_names = {
            # Upper right
            '1': 'Upper Right Third Molar', '2': 'Upper Right Second Molar',
            '3': 'Upper Right First Molar', '4': 'Upper Right Second Premolar',
            '5': 'Upper Right First Premolar', '6': 'Upper Right Canine',
            '7': 'Upper Right Lateral Incisor', '8': 'Upper Right Central Incisor',
            # Upper left
            '9': 'Upper Left Central Incisor', '10': 'Upper Left Lateral Incisor',
            '11': 'Upper Left Canine', '12': 'Upper Left First Premolar',
            '13': 'Upper Left Second Premolar', '14': 'Upper Left First Molar',
            '15': 'Upper Left Second Molar', '16': 'Upper Left Third Molar',
            # Lower left
            '17': 'Lower Left Third Molar', '18': 'Lower Left Second Molar',
            '19': 'Lower Left First Molar', '20': 'Lower Left Second Premolar',
            '21': 'Lower Left First Premolar', '22': 'Lower Left Canine',
            '23': 'Lower Left Lateral Incisor', '24': 'Lower Left Central Incisor',
            # Lower right
            '25': 'Lower Right Central Incisor', '26': 'Lower Right Lateral Incisor',
            '27': 'Lower Right Canine', '28': 'Lower Right First Premolar',
            '29': 'Lower Right Second Premolar', '30': 'Lower Right First Molar',
            '31': 'Lower Right Second Molar', '32': 'Lower Right Third Molar',
            # Primary teeth
            'A': 'Upper Right Second Molar (Primary)', 'B': 'Upper Right First Molar (Primary)',
            'C': 'Upper Right Canine (Primary)', 'D': 'Upper Right Lateral Incisor (Primary)',
            'E': 'Upper Right Central Incisor (Primary)', 'F': 'Upper Left Central Incisor (Primary)',
            'G': 'Upper Left Lateral Incisor (Primary)', 'H': 'Upper Left Canine (Primary)',
            'I': 'Upper Left First Molar (Primary)', 'J': 'Upper Left Second Molar (Primary)',
            'K': 'Lower Left Second Molar (Primary)', 'L': 'Lower Left First Molar (Primary)',
            'M': 'Lower Left Canine (Primary)', 'N': 'Lower Left Lateral Incisor (Primary)',
            'O': 'Lower Left Central Incisor (Primary)', 'P': 'Lower Right Central Incisor (Primary)',
            'Q': 'Lower Right Lateral Incisor (Primary)', 'R': 'Lower Right Canine (Primary)',
            'S': 'Lower Right First Molar (Primary)', 'T': 'Lower Right Second Molar (Primary)',
        }
        
        for tooth in self:
            tooth.tooth_name = tooth_names.get(tooth.tooth_number, f'Tooth {tooth.tooth_number}')
    
    @api.depends('tooth_number', 'tooth_name')
    def _compute_display_name(self):
        for tooth in self:
            tooth.display_name = f"#{tooth.tooth_number} - {tooth.tooth_name}"
    
    @api.depends('tooth_number')
    def _compute_sequence(self):
        for tooth in self:
            try:
                tooth.sequence = int(tooth.tooth_number)
            except ValueError:
                # For primary teeth (letters), use ASCII value
                tooth.sequence = ord(tooth.tooth_number) if tooth.tooth_number else 0
    
    @api.depends('tooth_number', 'is_primary')
    def _compute_tooth_type(self):
        for tooth in self:
            if tooth.is_primary:
                # Primary teeth classification
                if tooth.tooth_number in ['D', 'E', 'F', 'G', 'N', 'O', 'P', 'Q']:
                    tooth.tooth_type = 'incisor'
                elif tooth.tooth_number in ['C', 'H', 'M', 'R']:
                    tooth.tooth_type = 'canine'
                else:
                    tooth.tooth_type = 'molar'
            else:
                # Permanent teeth classification
                try:
                    num = int(tooth.tooth_number)
                    if num in [7, 8, 9, 10, 23, 24, 25, 26]:
                        tooth.tooth_type = 'incisor'
                    elif num in [6, 11, 22, 27]:
                        tooth.tooth_type = 'canine'
                    elif num in [4, 5, 12, 13, 20, 21, 28, 29]:
                        tooth.tooth_type = 'premolar'
                    else:
                        tooth.tooth_type = 'molar'
                except ValueError:
                    tooth.tooth_type = False
    
    @api.depends('tooth_number')
    def _compute_quadrant(self):
        for tooth in self:
            if tooth.is_primary:
                if tooth.tooth_number in ['A', 'B', 'C', 'D', 'E']:
                    tooth.quadrant = 'ur'
                elif tooth.tooth_number in ['F', 'G', 'H', 'I', 'J']:
                    tooth.quadrant = 'ul'
                elif tooth.tooth_number in ['K', 'L', 'M', 'N', 'O']:
                    tooth.quadrant = 'll'
                else:
                    tooth.quadrant = 'lr'
            else:
                try:
                    num = int(tooth.tooth_number)
                    if 1 <= num <= 8:
                        tooth.quadrant = 'ur'
                    elif 9 <= num <= 16:
                        tooth.quadrant = 'ul'
                    elif 17 <= num <= 24:
                        tooth.quadrant = 'll'
                    else:
                        tooth.quadrant = 'lr'
                except ValueError:
                    tooth.quadrant = False
    
    @api.depends('history_ids.date')
    def _compute_last_procedure(self):
        for tooth in self:
            if tooth.history_ids:
                last_history = tooth.history_ids.sorted('date', reverse=True)[0]
                tooth.last_procedure_date = last_history.date
            else:
                tooth.last_procedure_date = False
    
    @api.depends('state')
    def _compute_color(self):
        color_map = {
            'healthy': '#4CAF50',      # Green
            'decayed': '#795548',       # Brown
            'filled': '#9E9E9E',        # Grey
            'crown': '#FFC107',         # Amber
            'bridge': '#FF9800',        # Orange
            'implant': '#607D8B',       # Blue Grey
            'root_canal': '#9C27B0',    # Purple
            'missing': '#FFFFFF',       # White (transparent)
            'impacted': '#F44336',      # Red
            'fractured': '#E91E63',     # Pink
        }
        
        for tooth in self:
            tooth.color = color_map.get(tooth.state, '#FFFFFF')
    
    def _get_surface_data(self):
        """Get surface data for OWL component"""
        self.ensure_one()
        
        return {
            'mesial': self.surface_mesial,
            'distal': self.surface_distal,
            'occlusal': self.surface_occlusal,
            'buccal': self.surface_buccal,
            'lingual': self.surface_lingual,
        }
    
    def action_add_procedure(self):
        """Add procedure to tooth"""
        self.ensure_one()
        
        return {
            'name': _('Add Procedure'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.tooth.procedure.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tooth_id': self.id,
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
            'domain': [('tooth_id', '=', self.id)],
            'context': {'default_tooth_id': self.id}
        }
    
    def action_attach_xray(self):
        """Attach X-ray to tooth"""
        self.ensure_one()
        
        return {
            'name': _('Attach X-ray'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'clinic.tooth',
                'default_res_id': self.id,
                'default_name': f'X-ray - Tooth {self.tooth_number}',
            }
        }
    
    def update_state(self, new_state, notes=''):
        """Update tooth state and create history"""
        self.ensure_one()
        
        old_state = self.state
        self.state = new_state
        
        if notes:
            self.notes = notes
        
        # Create history entry
        self.env['clinic.tooth.history'].create({
            'tooth_id': self.id,
            'date': fields.Date.today(),
            'action': 'state_change',
            'description': f'State changed from {old_state} to {new_state}',
            'old_state': old_state,
            'new_state': new_state,
            'user_id': self.env.user.id,
        })
        
        # Update parent chart data
        self.chart_id._update_chart_data()
        
        return True
    
    def name_get(self):
        return [(tooth.id, tooth.display_name) for tooth in self]