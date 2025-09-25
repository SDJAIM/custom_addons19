# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, date, timedelta


class ClinicStaffAvailability(models.Model):
    _name = 'clinic.staff.availability'
    _description = 'Staff Availability Exception'
    _order = 'date desc'
    
    staff_id = fields.Many2one(
        'clinic.staff',
        string='Staff Member',
        required=True,
        ondelete='cascade'
    )
    
    date = fields.Date(
        string='Date',
        required=True
    )
    
    availability_type = fields.Selection([
        ('available', 'Available'),
        ('unavailable', 'Unavailable'),
        ('limited', 'Limited Availability')
    ], string='Type', required=True, default='unavailable')
    
    reason = fields.Selection([
        ('leave', 'Leave'),
        ('sick', 'Sick Leave'),
        ('emergency', 'Emergency'),
        ('training', 'Training'),
        ('conference', 'Conference'),
        ('extra_hours', 'Extra Hours'),
        ('other', 'Other')
    ], string='Reason')
    
    start_time = fields.Float(
        string='Start Time',
        help='For limited availability'
    )
    
    end_time = fields.Float(
        string='End Time',
        help='For limited availability'
    )
    
    branch_id = fields.Many2one(
        'clinic.branch',
        string='Branch',
        help='Specific branch for this availability'
    )
    
    notes = fields.Text(string='Notes')
    
    
    @api.constrains('date')
    def _check_date(self):
        for record in self:
            if record.date < date.today():
                raise ValidationError(_("Cannot set availability for past dates!"))
    
    @api.constrains('start_time', 'end_time', 'availability_type')
    def _check_times(self):
        for record in self:
            if record.availability_type == 'limited':
                if not record.start_time or not record.end_time:
                    raise ValidationError(_(
                        "Start and end times are required for limited availability!"
                    ))
                
                if record.end_time <= record.start_time:
                    raise ValidationError(_("End time must be after start time!"))
    
    @api.constrains('staff_id', 'date')
    def _check_duplicate(self):
        for record in self:
            duplicate = self.search([
                ('staff_id', '=', record.staff_id.id),
                ('date', '=', record.date),
                ('id', '!=', record.id)
            ])
            if duplicate:
                raise ValidationError(_(
                    "Availability exception already exists for this date!"
                ))
    
    
    def check_availability(self, check_date, start_time=None, end_time=None):
        """
        Check if staff is available on given date and time
        
        :param check_date: Date to check
        :param start_time: Start time (optional)
        :param end_time: End time (optional)
        :return: Boolean
        """
        self.ensure_one()
        
        # Find exception for this date
        exception = self.search([
            ('staff_id', '=', self.staff_id.id),
            ('date', '=', check_date)
        ], limit=1)
        
        if not exception:
            return True  # No exception, use regular schedule
        
        if exception.availability_type == 'unavailable':
            return False
        
        if exception.availability_type == 'available':
            return True
        
        if exception.availability_type == 'limited':
            if start_time and end_time:
                # Check if requested time is within limited availability
                return (start_time >= exception.start_time and 
                       end_time <= exception.end_time)
            return True  # If no specific time requested, consider available
        
        return True