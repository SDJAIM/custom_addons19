# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ClinicRoom(models.Model):
    """
    Medical facility rooms/consultation rooms as Odoo resources
    This allows native calendar integration and availability management
    """
    _name = 'clinic.room'
    _description = 'Medical Room/Facility'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'branch_id, room_type, name'

    # Link to resource.resource for calendar management
    resource_id = fields.Many2one(
        'resource.resource',
        string='Resource',
        ondelete='cascade',
        required=True,
        help='Resource for calendar scheduling'
    )

    name = fields.Char(
        string='Room Name',
        related='resource_id.name',
        store=True,
        readonly=False,
        required=True
    )

    code = fields.Char(
        string='Room Code',
        required=True,
        index=True,
        help='Unique identifier for the room'
    )

    branch_id = fields.Many2one(
        'clinic.branch',
        string='Branch',
        required=True,
        tracking=True,
        index=True
    )

    room_type = fields.Selection([
        ('consultation', 'Consultation Room'),
        ('procedure', 'Procedure Room'),
        ('surgery', 'Surgery Room'),
        ('emergency', 'Emergency Room'),
        ('laboratory', 'Laboratory'),
        ('radiology', 'Radiology Room'),
        ('dental', 'Dental Suite'),
        ('recovery', 'Recovery Room'),
        ('waiting', 'Waiting Room'),
        ('other', 'Other')
    ], string='Room Type', required=True, default='consultation', tracking=True)

    # Capacity and Features
    capacity = fields.Integer(
        string='Capacity',
        default=1,
        help='Number of people the room can accommodate'
    )

    floor = fields.Char(
        string='Floor/Level',
        help='Building floor or level'
    )

    is_sterile = fields.Boolean(
        string='Sterile Room',
        help='Requires special sterilization protocols'
    )

    has_oxygen = fields.Boolean(
        string='Oxygen Supply',
        help='Room has medical oxygen supply'
    )

    has_suction = fields.Boolean(
        string='Suction Available',
        help='Room has suction equipment'
    )

    has_monitoring = fields.Boolean(
        string='Patient Monitoring',
        help='Room has patient monitoring equipment'
    )

    # Equipment
    equipment_ids = fields.Many2many(
        'clinic.room.equipment',
        'clinic_room_equipment_rel',
        'room_id',
        'equipment_id',
        string='Equipment',
        help='Medical equipment in this room'
    )

    # Calendar and Availability
    calendar_id = fields.Many2one(
        'resource.calendar',
        string='Working Time',
        related='resource_id.calendar_id',
        readonly=False,
        help='Working hours for this room'
    )

    active = fields.Boolean(
        string='Active',
        related='resource_id.active',
        store=True,
        readonly=False,
        default=True
    )

    # Status Management
    status = fields.Selection([
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('maintenance', 'Under Maintenance'),
        ('cleaning', 'Being Cleaned'),
        ('reserved', 'Reserved'),
        ('out_of_service', 'Out of Service')
    ], string='Current Status', default='available', tracking=True)

    # Cleaning and Maintenance
    last_cleaned = fields.Datetime(
        string='Last Cleaned',
        tracking=True
    )

    cleaning_frequency_hours = fields.Float(
        string='Cleaning Frequency (hours)',
        default=4.0,
        help='How often the room should be cleaned'
    )

    next_maintenance = fields.Date(
        string='Next Maintenance',
        tracking=True
    )

    # Usage Statistics
    appointment_count = fields.Integer(
        string='Appointments',
        compute='_compute_appointment_count'
    )

    utilization_rate = fields.Float(
        string='Utilization Rate (%)',
        compute='_compute_utilization_rate',
        help='Percentage of time room is used'
    )

    # Specializations
    specialization_ids = fields.Many2many(
        'clinic.staff.specialization',
        string='Suitable For',
        help='Medical specializations this room is equipped for'
    )

    # Notes
    description = fields.Text(
        string='Description'
    )

    notes = fields.Text(
        string='Internal Notes'
    )

    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='branch_id.company_id',
        store=True
    )

    @api.constrains('code', 'branch_id')
    def _check_code_branch_unique(self):
        for record in self:
            domain = [('code', '=', record.code), ('id', '!=', record.id)]
            if record.branch_id:
                domain.append(('branch_id', '=', record.branch_id.id))
            else:
                domain.append(('branch_id', '=', False))
            if self.search_count(domain) > 0:
                raise ValidationError(_('Room code must be unique per branch!'))

    @api.model
    def create(self, vals):
        """Create resource automatically when creating room"""
        if not vals.get('resource_id'):
            # Create resource for this room
            resource_vals = {
                'name': vals.get('name', 'New Room'),
                'resource_type': 'material',
                'calendar_id': vals.get('calendar_id') or self.env.company.resource_calendar_id.id,
                'active': vals.get('active', True),
            }
            resource = self.env['resource.resource'].create(resource_vals)
            vals['resource_id'] = resource.id

        room = super().create(vals)

        # Update resource with branch info (custom field if added to resource)
        if room.branch_id and hasattr(room.resource_id, 'branch_id'):
            room.resource_id.branch_id = room.branch_id.id

        return room

    @api.ondelete(at_uninstall=False)
    def _unlink_resource(self):
        """Delete resource when room is deleted"""
        resources = self.mapped('resource_id')
        result = super()._unlink_resource()
        resources.unlink()
        return result

    def _compute_appointment_count(self):
        """Count appointments scheduled in this room"""
        Appointment = self.env['clinic.appointment']
        for room in self:
            room.appointment_count = Appointment.search_count([
                ('room_id', '=', room.resource_id.id)
            ])

    def _compute_utilization_rate(self):
        """Calculate room utilization rate"""
        for room in self:
            # This would calculate based on appointments vs available time
            # Simplified for now
            room.utilization_rate = 0.0

    @api.constrains('capacity')
    def _check_capacity(self):
        for room in self:
            if room.capacity < 1:
                raise ValidationError(_("Room capacity must be at least 1"))

    def action_set_available(self):
        """Set room as available"""
        self.ensure_one()
        self.status = 'available'
        self.last_cleaned = fields.Datetime.now()

    def action_set_maintenance(self):
        """Set room under maintenance"""
        self.ensure_one()
        self.status = 'maintenance'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Schedule Maintenance'),
            'res_model': 'maintenance.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_name': f'Maintenance for {self.name}',
                'default_equipment_id': self.equipment_ids[0].id if self.equipment_ids else False,
            }
        }

    def action_clean_room(self):
        """Mark room as cleaned"""
        self.ensure_one()
        self.write({
            'status': 'cleaning',
            'last_cleaned': fields.Datetime.now()
        })
        # Could trigger a timer to set back to available after cleaning time

    def action_view_appointments(self):
        """View appointments scheduled in this room"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Room Appointments'),
            'res_model': 'clinic.appointment',
            'view_mode': 'tree,calendar,form',
            'domain': [('room_id', '=', self.resource_id.id)],
            'context': {
                'default_room_id': self.resource_id.id,
                'default_branch_id': self.branch_id.id,
            }
        }

    def check_availability(self, start_datetime, end_datetime):
        """Check if room is available for given time period"""
        self.ensure_one()

        if self.status != 'available':
            return False

        # Check calendar working hours
        if self.calendar_id:
            work_intervals = self.calendar_id._work_intervals_batch(
                start_datetime,
                end_datetime,
                resources=self.resource_id
            )[self.resource_id.id]

            if not work_intervals:
                return False

        # Check for conflicting appointments
        # First check if appointment model has room_id field
        Appointment = self.env['clinic.appointment']
        if 'room_id' in Appointment._fields:
            appointments = Appointment.search([
                ('room_id', '=', self.id),  # Use self.id, not resource_id.id
                ('state', 'not in', ['cancelled', 'no_show']),
                '|',
                '&', ('start', '>=', start_datetime), ('start', '<', end_datetime),
                '&', ('stop', '>', start_datetime), ('stop', '<=', end_datetime)
            ])
        else:
            # If room_id doesn't exist in appointment, check through resource
            appointments = Appointment.search([
                ('location', 'ilike', self.name),  # Fallback to location field
                ('state', 'not in', ['cancelled', 'no_show']),
                '|',
                '&', ('start', '>=', start_datetime), ('start', '<', end_datetime),
                '&', ('stop', '>', start_datetime), ('stop', '<=', end_datetime)
            ])

        return not bool(appointments)

    @api.model
    def get_available_rooms(self, branch_id, start_datetime, end_datetime, room_type=None):
        """Get list of available rooms for given criteria"""
        domain = [
            ('branch_id', '=', branch_id),
            ('status', '=', 'available'),
            ('active', '=', True)
        ]

        if room_type:
            domain.append(('room_type', '=', room_type))

        rooms = self.search(domain)
        available_rooms = []

        for room in rooms:
            if room.check_availability(start_datetime, end_datetime):
                available_rooms.append(room)

        return available_rooms

    @api.model
    def _cron_check_cleaning_schedule(self):
        """Cron job to check if rooms need cleaning"""
        rooms = self.search([
            ('status', '=', 'available'),
            ('last_cleaned', '!=', False)
        ])

        for room in rooms:
            if room.last_cleaned:
                hours_since_cleaned = (fields.Datetime.now() - room.last_cleaned).total_seconds() / 3600
                if hours_since_cleaned >= room.cleaning_frequency_hours:
                    # Create activity for cleaning
                    room.activity_schedule(
                        'mail.mail_activity_data_todo',
                        summary=f'Room {room.name} needs cleaning',
                        date_deadline=fields.Date.today()
                    )

    def name_get(self):
        """Custom name display"""
        result = []
        for room in self:
            name = f"[{room.code}] {room.name}"
            if room.branch_id:
                name = f"{name} ({room.branch_id.code})"
            result.append((room.id, name))
        return result