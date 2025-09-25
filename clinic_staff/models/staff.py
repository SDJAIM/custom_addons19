# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import date, datetime, timedelta
from odoo.exceptions import ValidationError
import re


class ClinicStaff(models.Model):
    _name = 'clinic.staff'
    _description = 'Clinic Staff Member'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin', 'resource.mixin']
    _rec_name = 'display_name'
    _order = 'staff_type, name'
    
    # ========================
    # Basic Information
    # ========================
    staff_code = fields.Char(
        string='Staff Code',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'),
        help='Unique staff identifier'
    )
    
    name = fields.Char(
        string='Full Name',
        required=True,
        tracking=True
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    staff_type = fields.Selection([
        ('doctor', 'Doctor'),
        ('dentist', 'Dentist'),
        ('nurse', 'Nurse'),
        ('assistant', 'Assistant'),
        ('receptionist', 'Receptionist'),
        ('technician', 'Technician'),
        ('therapist', 'Therapist'),
        ('admin', 'Administrator')
    ], string='Staff Type', required=True, tracking=True)
    
    employee_id = fields.Many2one(
        'hr.employee',
        string='Related Employee',
        help='Link to HR employee record'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Related User',
        help='User account for system access'
    )
    
    # ========================
    # Professional Information
    # ========================
    specialization_ids = fields.Many2many(
        'clinic.staff.specialization',
        'staff_specialization_rel',
        'staff_id',
        'specialization_id',
        string='Specializations'
    )
    
    primary_specialization_id = fields.Many2one(
        'clinic.staff.specialization',
        string='Primary Specialization',
        domain="[('id', 'in', specialization_ids)]"
    )
    
    qualification = fields.Text(
        string='Qualifications',
        help='Educational qualifications and certifications'
    )
    
    license_number = fields.Char(
        string='License Number',
        help='Professional license number'
    )
    
    license_expiry = fields.Date(
        string='License Expiry Date',
        tracking=True
    )
    
    license_state = fields.Selection([
        ('valid', 'Valid'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired')
    ], string='License Status', compute='_compute_license_state', store=True)
    
    experience_years = fields.Integer(
        string='Years of Experience',
        help='Total years of professional experience'
    )
    
    join_date = fields.Date(
        string='Join Date',
        default=fields.Date.today,
        tracking=True
    )
    
    # ========================
    # Contact Information
    # ========================
    mobile = fields.Char(string='Mobile', required=True, tracking=True)
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email', required=True, tracking=True)
    
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    country_id = fields.Many2one('res.country', string='Country')
    zip = fields.Char(string='ZIP')
    
    # ========================
    # Work Information
    # ========================
    branch_ids = fields.Many2many(
        'clinic.branch',
        'staff_branch_rel',
        'staff_id',
        'branch_id',
        string='Working Branches'
    )
    
    primary_branch_id = fields.Many2one(
        'clinic.branch',
        string='Primary Branch',
        domain="[('id', 'in', branch_ids)]"
    )
    
    department_id = fields.Many2one(
        'hr.department',
        string='Department'
    )
    
    consultation_fee = fields.Float(
        string='Consultation Fee',
        help='Standard consultation fee'
    )
    
    follow_up_fee = fields.Float(
        string='Follow-up Fee',
        help='Fee for follow-up consultations'
    )
    
    emergency_fee = fields.Float(
        string='Emergency Fee',
        help='Fee for emergency consultations'
    )
    
    online_consultation_fee = fields.Float(
        string='Online Consultation Fee',
        help='Fee for telemedicine consultations'
    )
    
    # ========================
    # Availability & Schedule
    # ========================
    working_hours = fields.Selection([
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('on_call', 'On Call'),
        ('visiting', 'Visiting')
    ], string='Working Hours Type', default='full_time')

    # Resource fields from resource.mixin
    resource_calendar_id = fields.Many2one(
        'resource.calendar',
        string='Working Time',
        help='Working schedule for this staff member'
    )
    
    schedule_ids = fields.One2many(
        'clinic.staff.schedule',
        'staff_id',
        string='Weekly Schedule'
    )
    
    availability_ids = fields.One2many(
        'clinic.staff.availability',
        'staff_id',
        string='Availability Slots'
    )
    
    is_available_online = fields.Boolean(
        string='Available for Online Consultation',
        help='Staff member provides telemedicine services'
    )
    
    max_appointments_per_day = fields.Integer(
        string='Max Appointments/Day',
        default=20,
        help='Maximum number of appointments per day'
    )
    
    appointment_duration = fields.Float(
        string='Default Appointment Duration',
        default=0.5,
        help='Default duration in hours for appointments'
    )
    
    # ========================
    # Performance Metrics
    # ========================
    total_appointments = fields.Integer(
        string='Total Appointments',
        compute='_compute_appointment_metrics'
    )
    
    monthly_appointments = fields.Integer(
        string='This Month',
        compute='_compute_appointment_metrics'
    )
    
    average_rating = fields.Float(
        string='Average Rating',
        compute='_compute_rating',
        digits=(2, 1)
    )
    
    total_revenue = fields.Monetary(
        string='Total Revenue',
        compute='_compute_revenue',
        currency_field='currency_id'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # ========================
    # Status Fields
    # ========================
    active = fields.Boolean(string='Active', default=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('resigned', 'Resigned')
    ], string='Status', default='draft', tracking=True)
    
    color = fields.Integer(string='Color Index', default=0)
    
    # ========================
    # Additional Information
    # ========================
    biography = fields.Html(
        string='Biography',
        help='Professional biography for website/portal'
    )
    
    languages = fields.Char(
        string='Languages Spoken',
        help='Languages the staff member can communicate in'
    )
    
    achievements = fields.Text(
        string='Achievements & Awards'
    )
    
    research_interests = fields.Text(
        string='Research Interests'
    )
    
    publications = fields.Text(
        string='Publications'
    )
    
    notes = fields.Text(string='Internal Notes')
    
    # Documents
    resume = fields.Binary(string='Resume', attachment=True)
    certificates = fields.Binary(string='Certificates', attachment=True)
    
    # ========================
    # Constraints and Validations
    # ========================
    @api.constrains('staff_code')
    def _check_staff_code_unique(self):
        for record in self:
            if self.search_count([('staff_code', '=', record.staff_code), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_('Staff code must be unique!'))

    @api.constrains('email')
    def _check_email_unique(self):
        for record in self:
            if record.email and self.search_count([('email', '=', record.email), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_('Email address must be unique!'))

    @api.constrains('license_number')
    def _check_license_unique(self):
        for record in self:
            if record.license_number and self.search_count([('license_number', '=', record.license_number), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_('License number must be unique!'))
    
    @api.model
    def create(self, vals):
        if vals.get('staff_code', _('New')) == _('New'):
            # Generate code based on staff type
            staff_type = vals.get('staff_type', 'STF')
            prefix_map = {
                'doctor': 'DOC',
                'dentist': 'DEN',
                'nurse': 'NUR',
                'assistant': 'AST',
                'receptionist': 'RCP',
                'technician': 'TEC',
                'therapist': 'THR',
                'admin': 'ADM'
            }
            prefix = prefix_map.get(staff_type, 'STF')
            vals['staff_code'] = self.env['ir.sequence'].next_by_code(f'clinic.staff.{staff_type}') or \
                                 f"{prefix}{str(self.env['clinic.staff'].search_count([]) + 1).zfill(3)}"
        
        # Create user if email provided and no user_id
        if vals.get('email') and not vals.get('user_id'):
            user_vals = {
                'name': vals.get('name'),
                'login': vals.get('email'),
                'email': vals.get('email'),
                'groups_id': [(6, 0, self._get_default_groups(vals.get('staff_type')))]
            }
            user = self.env['res.users'].sudo().create(user_vals)
            vals['user_id'] = user.id
        
        return super().create(vals)
    
    def _get_default_groups(self, staff_type):
        """Get default groups based on staff type"""
        groups = [self.env.ref('base.group_user').id]
        
        # Add specific groups based on staff type
        if staff_type in ['doctor', 'dentist']:
            if self.env.ref('clinic_patient.group_clinic_patient_manager', False):
                groups.append(self.env.ref('clinic_patient.group_clinic_patient_manager').id)
        elif staff_type in ['nurse', 'assistant']:
            if self.env.ref('clinic_patient.group_clinic_patient_user', False):
                groups.append(self.env.ref('clinic_patient.group_clinic_patient_user').id)
        
        return groups
    
    @api.depends('name', 'staff_code', 'staff_type')
    def _compute_display_name(self):
        for record in self:
            type_label = dict(self._fields['staff_type'].selection).get(record.staff_type, '')
            record.display_name = f"[{record.staff_code}] {type_label} {record.name}"
    
    @api.depends('license_expiry')
    def _compute_license_state(self):
        today = date.today()
        warning_days = 60  # Warn 60 days before expiry
        
        for record in self:
            if not record.license_expiry:
                record.license_state = False
            elif record.license_expiry < today:
                record.license_state = 'expired'
            elif record.license_expiry <= today + timedelta(days=warning_days):
                record.license_state = 'expiring'
            else:
                record.license_state = 'valid'
    
    def _compute_appointment_metrics(self):
        """Compute appointment statistics"""
        for record in self:
            # Will be implemented when appointment module is ready
            record.total_appointments = 0
            record.monthly_appointments = 0
    
    def _compute_rating(self):
        """Compute average rating from patient feedback"""
        for record in self:
            # Will be implemented with review/rating system
            record.average_rating = 4.5  # Default placeholder
    
    def _compute_revenue(self):
        """Compute total revenue generated"""
        for record in self:
            # Will be implemented with finance module
            record.total_revenue = 0.0
    
    @api.constrains('email')
    def _check_email(self):
        for record in self:
            if record.email and not re.match(r"[^@]+@[^@]+\.[^@]+", record.email):
                raise ValidationError(_("Invalid email address format!"))
    
    @api.constrains('consultation_fee', 'follow_up_fee', 'emergency_fee', 'online_consultation_fee')
    def _check_fees(self):
        for record in self:
            fees = [record.consultation_fee, record.follow_up_fee, 
                   record.emergency_fee, record.online_consultation_fee]
            if any(fee < 0 for fee in fees if fee):
                raise ValidationError(_("Fees cannot be negative!"))
    
    @api.constrains('max_appointments_per_day')
    def _check_max_appointments(self):
        for record in self:
            if record.max_appointments_per_day < 1:
                raise ValidationError(_("Maximum appointments per day must be at least 1!"))
    
    # ========================
    # Business Methods
    # ========================
    def action_activate(self):
        """Activate staff member"""
        self.ensure_one()
        self.state = 'active'
        
    def action_deactivate(self):
        """Deactivate staff member"""
        self.ensure_one()
        self.state = 'suspended'
    
    def action_set_on_leave(self):
        """Mark staff as on leave"""
        self.ensure_one()
        self.state = 'on_leave'
    
    def action_view_appointments(self):
        """View staff appointments"""
        self.ensure_one()
        return {
            'name': _('Appointments'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.appointment',
            'view_mode': 'tree,form,calendar',
            'domain': [('staff_id', '=', self.id)],
            'context': {'default_staff_id': self.id},
        }
    
    def action_view_schedule(self):
        """View staff schedule"""
        self.ensure_one()
        return {
            'name': _('Schedule'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.staff.schedule',
            'view_mode': 'tree,form',
            'domain': [('staff_id', '=', self.id)],
            'context': {'default_staff_id': self.id},
        }
    
    def calculate_schedule(self, date_from, date_to, branch_id=None):
        """
        Calculate staff schedule for a date range

        :param date_from: Start date
        :param date_to: End date
        :param branch_id: Optional branch filter
        :return: List of scheduled working days with times
        """
        self.ensure_one()

        from datetime import datetime, timedelta

        schedule_list = []
        current_date = date_from if isinstance(date_from, datetime.date) else datetime.strptime(date_from, '%Y-%m-%d').date()
        end_date = date_to if isinstance(date_to, datetime.date) else datetime.strptime(date_to, '%Y-%m-%d').date()

        while current_date <= end_date:
            # Get day of week (0=Monday, 6=Sunday)
            day_of_week = str(current_date.weekday())

            # Find schedule for this day
            domain = [
                ('staff_id', '=', self.id),
                ('day_of_week', '=', day_of_week),
                ('is_available', '=', True)
            ]

            if branch_id:
                domain.append(('branch_id', '=', branch_id))

            schedules = self.env['clinic.staff.schedule'].search(domain)

            for schedule in schedules:
                # Check for specific availability override
                availability = self.env['clinic.staff.availability'].search([
                    ('staff_id', '=', self.id),
                    ('date', '=', current_date)
                ], limit=1)

                # Skip if marked as unavailable
                if availability and availability.availability_type == 'unavailable':
                    continue

                schedule_info = {
                    'date': current_date,
                    'day': dict(schedule._fields['day_of_week'].selection)[day_of_week],
                    'branch_id': schedule.branch_id.id,
                    'branch_name': schedule.branch_id.name,
                    'start_time': schedule.start_time,
                    'end_time': schedule.end_time,
                    'break_start': schedule.break_start,
                    'break_end': schedule.break_end,
                    'slot_duration': schedule.slot_duration,
                    'rooms': schedule.room_ids.mapped('name'),
                    'is_available': True
                }

                # Override times if special availability
                if availability and availability.availability_type in ['half_day', 'custom']:
                    if availability.custom_start_time:
                        schedule_info['start_time'] = availability.custom_start_time
                    if availability.custom_end_time:
                        schedule_info['end_time'] = availability.custom_end_time

                schedule_list.append(schedule_info)

            current_date += timedelta(days=1)

        return schedule_list

    def get_available_slots(self, date_from, date_to, duration=0.5, branch_id=None):
        """
        Get available time slots for appointments

        :param date_from: Start date
        :param date_to: End date
        :param duration: Appointment duration in hours
        :param branch_id: Filter by branch
        :return: List of available slots
        """
        self.ensure_one()

        from datetime import datetime, timedelta

        # Get schedule for date range
        schedule = self.calculate_schedule(date_from, date_to, branch_id)

        if not schedule:
            return []

        available_slots = []

        for day_schedule in schedule:
            date = day_schedule['date']
            slots = []

            # Calculate slots for this day
            current_time = day_schedule['start_time']
            end_time = day_schedule['end_time']
            break_start = day_schedule.get('break_start')
            break_end = day_schedule.get('break_end')

            while current_time + duration <= end_time:
                # Skip break time
                if break_start and break_end:
                    if current_time < break_end and current_time + duration > break_start:
                        current_time = break_end
                        continue

                # Check if slot is already booked
                slot_start = datetime.combine(date, datetime.min.time()) + timedelta(hours=current_time)
                slot_end = slot_start + timedelta(hours=duration)

                # Check existing appointments
                appointments = self.env['clinic.appointment'].search([
                    ('staff_id', '=', self.id),
                    ('start', '<', slot_end),
                    ('stop', '>', slot_start),
                    ('state', 'not in', ['cancelled', 'no_show'])
                ])

                if not appointments:
                    # Slot is available
                    start_hour = int(current_time)
                    start_min = int((current_time - start_hour) * 60)
                    end_hour = int(current_time + duration)
                    end_min = int(((current_time + duration) - end_hour) * 60)

                    slots.append({
                        'start': f"{start_hour:02d}:{start_min:02d}",
                        'end': f"{end_hour:02d}:{end_min:02d}",
                        'datetime': slot_start,
                        'available': True,
                        'branch_id': day_schedule['branch_id']
                    })

                current_time += duration

            if slots:
                available_slots.append({
                    'date': date,
                    'branch': day_schedule['branch_name'],
                    'slots': slots
                })

        return available_slots
    
    @api.model
    def check_license_expiry(self):
        """Cron job to check for expiring licenses"""
        expiring_licenses = self.search([
            ('license_state', '=', 'expiring'),
            ('active', '=', True)
        ])
        
        for staff in expiring_licenses:
            # Create activity for license renewal
            staff.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=f'License Expiring Soon',
                note=f'Professional license expires on {staff.license_expiry}',
                date_deadline=staff.license_expiry
            )
    
    def send_credentials(self):
        """Send login credentials to staff member"""
        self.ensure_one()
        if not self.user_id:
            raise ValidationError(_("No user account exists for this staff member!"))
        
        # Reset password and send email
        self.user_id.action_reset_password()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Login credentials sent to staff member!'),
                'type': 'success',
            }
        }