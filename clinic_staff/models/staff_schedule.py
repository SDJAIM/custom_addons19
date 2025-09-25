# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, time, timedelta


class ClinicStaffSchedule(models.Model):
    _name = 'clinic.staff.schedule'
    _description = 'Staff Weekly Schedule'
    _order = 'staff_id, day_of_week, start_time'
    _rec_name = 'display_name'
    
    staff_id = fields.Many2one(
        'clinic.staff',
        string='Staff Member',
        required=True,
        ondelete='cascade'
    )
    
    branch_id = fields.Many2one(
        'clinic.branch',
        string='Branch',
        required=True,
        domain="[('id', 'in', parent.branch_ids)]"
    )
    
    day_of_week = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday')
    ], string='Day of Week', required=True)
    
    start_time = fields.Float(
        string='Start Time',
        required=True,
        help='Start time in 24-hour format (e.g., 9.5 for 9:30 AM)'
    )
    
    end_time = fields.Float(
        string='End Time',
        required=True,
        help='End time in 24-hour format (e.g., 17.5 for 5:30 PM)'
    )
    
    break_start = fields.Float(
        string='Break Start',
        help='Break start time'
    )
    
    break_end = fields.Float(
        string='Break End',
        help='Break end time'
    )
    
    is_available = fields.Boolean(
        string='Available',
        default=True,
        help='Staff is available on this day'
    )
    
    slot_duration = fields.Float(
        string='Slot Duration',
        default=0.5,
        help='Duration of each appointment slot in hours'
    )
    
    max_appointments = fields.Integer(
        string='Max Appointments',
        compute='_compute_max_appointments',
        store=True,
        help='Maximum appointments for this day'
    )
    
    room_ids = fields.Many2many(
        'clinic.room',
        'staff_schedule_room_rel',
        'schedule_id',
        'room_id',
        string='Assigned Rooms'
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    @api.depends('staff_id', 'day_of_week', 'branch_id')
    def _compute_display_name(self):
        days = dict(self._fields['day_of_week'].selection)
        for record in self:
            day = days.get(record.day_of_week, '')
            record.display_name = f"{record.staff_id.name} - {day} @ {record.branch_id.name}"
    
    @api.depends('start_time', 'end_time', 'break_start', 'break_end', 'slot_duration')
    def _compute_max_appointments(self):
        for record in self:
            if record.start_time and record.end_time and record.slot_duration:
                total_hours = record.end_time - record.start_time
                
                # Subtract break time if exists
                if record.break_start and record.break_end:
                    break_hours = record.break_end - record.break_start
                    total_hours -= break_hours
                
                record.max_appointments = int(total_hours / record.slot_duration)
            else:
                record.max_appointments = 0
    
    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for record in self:
            if record.end_time <= record.start_time:
                raise ValidationError(_("End time must be after start time!"))
            
            if record.start_time < 0 or record.start_time >= 24:
                raise ValidationError(_("Start time must be between 0:00 and 23:59!"))
            
            if record.end_time < 0 or record.end_time > 24:
                raise ValidationError(_("End time must be between 0:00 and 24:00!"))
    
    @api.constrains('break_start', 'break_end', 'start_time', 'end_time')
    def _check_break_times(self):
        for record in self:
            if record.break_start or record.break_end:
                if not (record.break_start and record.break_end):
                    raise ValidationError(_("Both break start and end times must be set!"))
                
                if record.break_end <= record.break_start:
                    raise ValidationError(_("Break end time must be after break start time!"))
                
                if record.break_start < record.start_time or record.break_end > record.end_time:
                    raise ValidationError(_("Break time must be within working hours!"))
    
    @api.constrains('staff_id', 'day_of_week', 'branch_id')
    def _check_duplicate_schedule(self):
        for record in self:
            duplicate = self.search([
                ('staff_id', '=', record.staff_id.id),
                ('day_of_week', '=', record.day_of_week),
                ('branch_id', '=', record.branch_id.id),
                ('id', '!=', record.id)
            ])
            if duplicate:
                raise ValidationError(_(
                    "Schedule already exists for this staff member on this day at this branch!"
                ))
    
    def get_available_slots(self, date):
        """
        Get available time slots for a specific date
        
        :param date: Date to check
        :return: List of available time slots
        """
        self.ensure_one()
        
        if not self.is_available:
            return []
        
        slots = []
        current_time = self.start_time
        
        while current_time + self.slot_duration <= self.end_time:
            # Skip break time
            if self.break_start and self.break_end:
                if current_time < self.break_end and current_time + self.slot_duration > self.break_start:
                    current_time = self.break_end
                    continue
            
            # Convert to time string
            hours = int(current_time)
            minutes = int((current_time - hours) * 60)
            start_str = f"{hours:02d}:{minutes:02d}"
            
            end_time = current_time + self.slot_duration
            end_hours = int(end_time)
            end_minutes = int((end_time - end_hours) * 60)
            end_str = f"{end_hours:02d}:{end_minutes:02d}"
            
            slots.append({
                'start': start_str,
                'end': end_str,
                'datetime': datetime.combine(date, time(hours, minutes))
            })
            
            current_time += self.slot_duration
        
        return slots
    
    def apply_to_all_branches(self):
        """Apply this schedule to all branches where staff works"""
        self.ensure_one()
        
        for branch in self.staff_id.branch_ids:
            if branch.id != self.branch_id.id:
                # Check if schedule exists
                existing = self.search([
                    ('staff_id', '=', self.staff_id.id),
                    ('day_of_week', '=', self.day_of_week),
                    ('branch_id', '=', branch.id)
                ])
                
                if not existing:
                    self.copy({
                        'branch_id': branch.id
                    })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Schedule applied to all branches!'),
                'type': 'success',
            }
        }