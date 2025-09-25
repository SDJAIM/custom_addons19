# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class Frequency(models.Model):
    _name = 'clinic.frequency'
    _description = 'Medication Frequency'
    _order = 'times_per_day, name'
    
    name = fields.Char(
        string='Frequency Name',
        required=True,
        translate=True,
        help='e.g., Twice Daily, Every 6 Hours'
    )
    
    code = fields.Char(
        string='Code',
        required=True,
        help='e.g., BID, TID, QID, PRN'
    )
    
    latin_abbreviation = fields.Char(
        string='Latin Abbreviation',
        help='e.g., bis in die (BID)'
    )
    
    times_per_day = fields.Float(
        string='Times Per Day',
        required=True,
        help='Number of doses per day'
    )
    
    hours_between = fields.Float(
        string='Hours Between Doses',
        compute='_compute_hours_between',
        store=True
    )
    
    frequency_type = fields.Selection([
        ('regular', 'Regular Intervals'),
        ('specific', 'Specific Times'),
        ('as_needed', 'As Needed'),
        ('custom', 'Custom'),
    ], string='Type', default='regular', required=True)
    
    # Specific timing fields
    morning = fields.Boolean(string='Morning', default=False)
    noon = fields.Boolean(string='Noon', default=False)
    evening = fields.Boolean(string='Evening', default=False)
    bedtime = fields.Boolean(string='Bedtime', default=False)
    
    # Custom timing
    custom_times = fields.Text(
        string='Custom Times',
        help='Specific times (e.g., 8:00, 14:00, 20:00)'
    )
    
    with_meals = fields.Boolean(
        string='With Meals',
        default=False
    )
    
    before_meals = fields.Boolean(
        string='Before Meals',
        default=False
    )
    
    after_meals = fields.Boolean(
        string='After Meals',
        default=False
    )
    
    description = fields.Text(
        string='Description',
        translate=True
    )
    
    instructions = fields.Text(
        string='Patient Instructions',
        translate=True,
        help='Default instructions for this frequency'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    _sql_constraints = [
        ('unique_code', 'UNIQUE(code)', 'Frequency code must be unique!'),
    ]
    
    @api.depends('times_per_day')
    def _compute_hours_between(self):
        for freq in self:
            if freq.times_per_day > 0:
                freq.hours_between = 24.0 / freq.times_per_day
            else:
                freq.hours_between = 0.0
    
    def name_get(self):
        result = []
        for freq in self:
            name = f"{freq.name} ({freq.code})"
            result.append((freq.id, name))
        return result
    
    def get_administration_times(self):
        """Generate list of administration times"""
        self.ensure_one()
        
        times = []
        
        if self.frequency_type == 'specific':
            if self.morning:
                times.append('08:00')
            if self.noon:
                times.append('12:00')
            if self.evening:
                times.append('18:00')
            if self.bedtime:
                times.append('22:00')
        elif self.frequency_type == 'custom' and self.custom_times:
            times = [t.strip() for t in self.custom_times.split(',')]
        elif self.frequency_type == 'regular':
            # Generate evenly spaced times
            if self.times_per_day == 1:
                times = ['08:00']
            elif self.times_per_day == 2:
                times = ['08:00', '20:00']
            elif self.times_per_day == 3:
                times = ['08:00', '14:00', '20:00']
            elif self.times_per_day == 4:
                times = ['08:00', '12:00', '16:00', '20:00']
            else:
                # Generate based on hours between
                hour = 8  # Start at 8 AM
                for i in range(int(self.times_per_day)):
                    times.append(f"{hour:02d}:00")
                    hour = (hour + int(self.hours_between)) % 24
        
        return times
    
    def get_display_text(self):
        """Get human-readable frequency text"""
        self.ensure_one()
        
        text = self.name
        
        if self.with_meals:
            text += " with meals"
        elif self.before_meals:
            text += " before meals"
        elif self.after_meals:
            text += " after meals"
        
        if self.frequency_type == 'as_needed':
            text += " as needed"
        
        return text