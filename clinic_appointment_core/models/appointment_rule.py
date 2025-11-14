# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import datetime, time

class AppointmentRule(models.Model):
    """
    Appointment Availability Rules
    Defines when staff are available for appointments
    """
    _name = 'clinic.appointment.rule'
    _description = 'Appointment Availability Rule'
    _order = 'type_id, sequence, weekday'

    # BASIC INFORMATION
    name = fields.Char(string='Rule Name', required=True, translate=True)
    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer(string='Sequence', default=10)
    
    # APPOINTMENT TYPE
    type_id = fields.Many2one(
        'clinic.appointment.type',
        string='Appointment Type',
        required=True,
        ondelete='cascade'
    )
    
    # STAFF (Optional - if not set, applies to all allowed staff)
    staff_id = fields.Many2one(
        'hr.employee',
        string='Staff Member',
        help='Leave empty to apply to all staff of this appointment type'
    )
    
    # TIMEZONE
    timezone = fields.Selection(
        selection='_tz_get',
        string='Timezone',
        required=True,
        default=lambda self: self.env.context.get('tz') or self.env.user.tz or 'UTC',
        help='Timezone for this availability rule'
    )
    
    # WEEKDAY
    weekday = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday'),
    ], string='Weekday', required=True)
    
    # TIME RANGE
    hour_from = fields.Float(
        string='From',
        required=True,
        help='Start hour (0-23.99)'
    )
    hour_to = fields.Float(
        string='To',
        required=True,
        help='End hour (0-23.99)'
    )
    
    # DATE RANGE (Optional - for temporary rules)
    date_from = fields.Date(
        string='Start Date',
        help='Leave empty for permanent rule'
    )
    date_to = fields.Date(
        string='End Date',
        help='Leave empty for permanent rule'
    )
    
    # EXCLUSIONS (Specific dates to exclude)
    exclusion_dates = fields.Char(
        string='Exclusion Dates',
        help='Comma-separated dates in YYYY-MM-DD format (e.g., 2025-12-25,2025-12-31)'
    )
    
    @api.model
    def _tz_get(self):
        """Get timezone list"""
        return [(tz, tz) for tz in sorted(self.env['res.partner']._fields['tz'].selection)]
    
    @api.constrains('hour_from', 'hour_to')
    def _check_hours(self):
        """Validate hour range"""
        for rule in self:
            if not (0 <= rule.hour_from < 24):
                raise ValidationError(_('Start hour must be between 0 and 23.99'))
            if not (0 <= rule.hour_to <= 24):
                raise ValidationError(_('End hour must be between 0 and 24'))
            if rule.hour_from >= rule.hour_to:
                raise ValidationError(_('Start hour must be less than end hour'))
    
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        """Validate date range"""
        for rule in self:
            if rule.date_from and rule.date_to:
                if rule.date_from > rule.date_to:
                    raise ValidationError(_('Start date must be before end date'))
    
    def is_date_excluded(self, check_date):
        """Check if a date is in exclusion list"""
        self.ensure_one()
        if not self.exclusion_dates:
            return False
        
        excluded_dates = [d.strip() for d in self.exclusion_dates.split(',') if d.strip()]
        check_date_str = check_date.strftime('%Y-%m-%d') if isinstance(check_date, datetime) else str(check_date)
        return check_date_str in excluded_dates
    
    def is_rule_active_for_date(self, check_date):
        """Check if rule is active for a specific date"""
        self.ensure_one()

        # Check if date is in valid range
        if self.date_from and check_date < self.date_from:
            return False
        if self.date_to and check_date > self.date_to:
            return False

        # Check exclusions
        if self.is_date_excluded(check_date):
            return False

        # Check weekday
        weekday_num = str(check_date.weekday())
        if self.weekday != weekday_num:
            return False

        return True

    def write(self, vals):
        """Update rule and invalidate slot cache"""
        result = super().write(vals)

        # ⚡ CACHE INVALIDATION (P0-003): Clear slot engine cache when rule is modified
        self.env['clinic.appointment.slot.engine']._invalidate_slot_cache()

        return result

    def unlink(self):
        """Delete rule and invalidate slot cache"""
        # ⚡ CACHE INVALIDATION (P0-003): Clear slot engine cache before deletion
        self.env['clinic.appointment.slot.engine']._invalidate_slot_cache()

        return super().unlink()
