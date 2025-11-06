# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta, date
from odoo.exceptions import ValidationError


class ClinicAppointmentSlot(models.Model):
    _name = 'clinic.appointment.slot'
    _description = 'Appointment Slot'
    _order = 'date, start_time'
    _rec_name = 'display_name'
    
    date = fields.Date(
        string='Date',
        required=True,
        index=True
    )
    
    start_time = fields.Float(
        string='Start Time',
        required=True,
        help='Start time in 24-hour format'
    )
    
    end_time = fields.Float(
        string='End Time',
        required=True,
        help='End time in 24-hour format'
    )
    
    staff_id = fields.Many2one(
        'clinic.staff',
        string='Staff Member',
        required=True,
        index=True
    )
    
    branch_id = fields.Many2one(
        'clinic.branch',
        string='Branch',
        required=True
    )
    
    room_id = fields.Many2one(
        'clinic.room',
        string='Room',
        domain="[('branch_id', '=', branch_id)]"
    )
    
    status = fields.Selection([
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('blocked', 'Blocked'),
        ('tentative', 'Tentative')
    ], string='Status', default='available', required=True)
    
    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Appointment',
        ondelete='set null'
    )
    
    appointment_type_ids = fields.Many2many(
        'clinic.appointment.type',
        string='Allowed Types',
        help='Types of appointments allowed in this slot'
    )
    
    max_patients = fields.Integer(
        string='Max Patients',
        default=1,
        help='Maximum patients for group appointments'
    )
    
    booked_count = fields.Integer(
        string='Booked',
        compute='_compute_booked_count'
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    slot_duration = fields.Float(
        string='Duration',
        compute='_compute_duration',
        store=True
    )
    
    @api.depends('date', 'start_time', 'staff_id')
    def _compute_display_name(self):
        for record in self:
            if record.date and record.staff_id:
                time_str = self._float_to_time_str(record.start_time)
                record.display_name = f"{record.staff_id.name} - {record.date} {time_str}"
            else:
                record.display_name = "Slot"
    
    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for record in self:
            record.slot_duration = record.end_time - record.start_time
    
    def _compute_booked_count(self):
        for record in self:
            if record.appointment_id:
                record.booked_count = 1
            else:
                record.booked_count = 0
    
    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for record in self:
            if record.end_time <= record.start_time:
                raise ValidationError(_("End time must be after start time!"))
    
    @api.constrains('date', 'start_time', 'end_time', 'staff_id')
    def _check_overlap(self):
        for record in self:
            overlapping = self.search([
                ('date', '=', record.date),
                ('staff_id', '=', record.staff_id.id),
                ('id', '!=', record.id),
                '|',
                '&', ('start_time', '>=', record.start_time), ('start_time', '<', record.end_time),
                '&', ('end_time', '>', record.start_time), ('end_time', '<=', record.end_time)
            ])
            
            if overlapping:
                raise ValidationError(_("This slot overlaps with another slot!"))
    
    def _float_to_time_str(self, float_time):
        """Convert float time to string format"""
        hours = int(float_time)
        minutes = int((float_time - hours) * 60)
        return f"{hours:02d}:{minutes:02d}"
    
    def book_slot(self, appointment_id):
        """Book this slot for an appointment"""
        self.ensure_one()
        
        if self.status != 'available':
            raise ValidationError(_("This slot is not available!"))
        
        self.write({
            'status': 'booked',
            'appointment_id': appointment_id
        })
    
    def release_slot(self):
        """Release a booked slot"""
        self.ensure_one()
        
        self.write({
            'status': 'available',
            'appointment_id': False
        })
    
    def block_slot(self, reason=None):
        """Block a slot from booking"""
        self.ensure_one()
        
        self.write({
            'status': 'blocked'
        })
    
    @api.model
    def generate_slots(self, staff_id, date_from, date_to, branch_id=None):
        """
        Generate appointment slots based on staff schedule
        
        :param staff_id: Staff member ID
        :param date_from: Start date
        :param date_to: End date
        :param branch_id: Optional branch filter
        :return: Created slots
        """
        staff = self.env['clinic.staff'].browse(staff_id)
        if not staff:
            return []
        
        created_slots = []
        current_date = date_from
        
        while current_date <= date_to:
            # Get day of week (0=Monday, 6=Sunday)
            day_of_week = str(current_date.weekday())
            
            # Find schedule for this day
            schedules = self.env['clinic.staff.schedule'].search([
                ('staff_id', '=', staff_id),
                ('day_of_week', '=', day_of_week),
                ('is_available', '=', True)
            ])
            
            if branch_id:
                schedules = schedules.filtered(lambda s: s.branch_id.id == branch_id)
            
            for schedule in schedules:
                # Check if staff has availability exception for this date
                availability = self.env['clinic.staff.availability'].search([
                    ('staff_id', '=', staff_id),
                    ('date', '=', current_date)
                ], limit=1)
                
                if availability and availability.availability_type == 'unavailable':
                    continue
                
                # Generate slots for this schedule
                current_time = schedule.start_time
                
                while current_time + schedule.slot_duration <= schedule.end_time:
                    # Skip break time
                    if schedule.break_start and schedule.break_end:
                        if current_time < schedule.break_end and current_time + schedule.slot_duration > schedule.break_start:
                            current_time = schedule.break_end
                            continue
                    
                    # Check if slot already exists
                    existing = self.search([
                        ('date', '=', current_date),
                        ('staff_id', '=', staff_id),
                        ('start_time', '=', current_time),
                        ('branch_id', '=', schedule.branch_id.id)
                    ])
                    
                    if not existing:
                        # Create slot
                        slot = self.create({
                            'date': current_date,
                            'start_time': current_time,
                            'end_time': current_time + schedule.slot_duration,
                            'staff_id': staff_id,
                            'branch_id': schedule.branch_id.id,
                            'room_id': schedule.room_ids[0].id if schedule.room_ids else False,
                            'status': 'available'
                        })
                        created_slots.append(slot)
                    
                    current_time += schedule.slot_duration
            
            current_date += timedelta(days=1)
        
        return created_slots
    
    @api.model
    def get_available_slots(self, staff_id=None, date=None, appointment_type_id=None, branch_id=None):
        """
        Get available slots with filters
        
        :param staff_id: Optional staff filter
        :param date: Optional date filter
        :param appointment_type_id: Optional appointment type filter
        :param branch_id: Optional branch filter
        :return: Available slots
        """
        domain = [('status', '=', 'available')]
        
        if staff_id:
            domain.append(('staff_id', '=', staff_id))
        
        if date:
            domain.append(('date', '=', date))
        
        if branch_id:
            domain.append(('branch_id', '=', branch_id))
        
        if appointment_type_id:
            domain.append(('appointment_type_ids', 'in', appointment_type_id))
        
        return self.search(domain, order='date, start_time')
    
    @api.model
    def auto_generate_weekly_slots(self):
        """Cron job to generate slots for next week"""
        date_from = date.today() + timedelta(days=7)
        date_to = date_from + timedelta(days=6)
        
        # Generate for all active staff
        staff_members = self.env['clinic.staff'].search([('state', '=', 'active')])
        
        for staff in staff_members:
            self.generate_slots(staff.id, date_from, date_to)