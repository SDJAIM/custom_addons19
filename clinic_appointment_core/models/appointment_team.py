# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AppointmentTeam(models.Model):
    """
    Team model for organizing appointment staff (TASK-F2-001)

    Allows grouping staff members into teams with shared calendars,
    capacity management, and team-based assignment.
    """
    _name = 'clinic.appointment.team'
    _description = 'Appointment Team'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    # ========================
    # Basic Information
    # ========================
    name = fields.Char(
        string='Team Name',
        required=True,
        tracking=True,
        help='Name of the appointment team'
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Used to order teams in views'
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )

    description = fields.Text(
        string='Description',
        help='Team description and purpose'
    )

    # ========================
    # Team Structure
    # ========================
    leader_id = fields.Many2one(
        'clinic.staff',
        string='Team Leader',
        tracking=True,
        help='Staff member responsible for this team'
    )

    member_ids = fields.Many2many(
        'clinic.staff',
        'clinic_appointment_team_staff_rel',
        'team_id',
        'staff_id',
        string='Team Members',
        tracking=True,
        help='Staff members who belong to this team'
    )

    member_count = fields.Integer(
        string='Members',
        compute='_compute_member_count',
        store=True
    )

    # ========================
    # Capacity Management
    # ========================
    capacity = fields.Integer(
        string='Daily Capacity',
        default=10,
        required=True,
        help='Maximum number of appointments per day for this team'
    )

    capacity_mode = fields.Selection([
        ('shared', 'Shared (Team total)'),
        ('individual', 'Individual (Per member)')
    ], string='Capacity Mode', default='shared', required=True,
       help='Shared: Total team capacity | Individual: Capacity per member')

    # ========================
    # Assignment Configuration
    # ========================
    assignment_mode = fields.Selection([
        ('round_robin', 'Round Robin'),
        ('load_balanced', 'Load Balanced'),
        ('manual', 'Manual Assignment')
    ], string='Assignment Mode', default='round_robin',
       help='How appointments are assigned to team members')

    # ========================
    # Calendar Configuration
    # ========================
    calendar_view_id = fields.Many2one(
        'ir.ui.view',
        string='Custom Calendar View',
        domain=[('type', '=', 'calendar')],
        help='Optional custom calendar view for this team'
    )

    color = fields.Integer(
        string='Color Index',
        help='Color used in calendar views'
    )

    # ========================
    # Multi-company
    # ========================
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )

    # ========================
    # Statistics (Computed)
    # ========================
    appointment_count = fields.Integer(
        string='Appointments',
        compute='_compute_appointment_count',
        help='Number of appointments assigned to this team'
    )

    # ========================
    # Computed Methods
    # ========================
    @api.depends('member_ids')
    def _compute_member_count(self):
        """Calculate number of team members"""
        for team in self:
            team.member_count = len(team.member_ids)

    def _compute_appointment_count(self):
        """Calculate number of appointments for this team"""
        for team in self:
            # Count appointments assigned to team members
            team.appointment_count = self.env['clinic.appointment'].search_count([
                ('staff_id', 'in', team.member_ids.ids),
                ('state', 'not in', ['cancelled', 'no_show'])
            ])

    # ========================
    # Constraints
    # ========================
    @api.constrains('capacity')
    def _check_capacity(self):
        """Validate capacity is positive"""
        for team in self:
            if team.capacity <= 0:
                raise ValidationError(
                    _('Team capacity must be greater than zero.\n\nTeam: %s') % team.name
                )

    @api.constrains('leader_id', 'member_ids')
    def _check_leader_in_members(self):
        """Ensure team leader is also a team member"""
        for team in self:
            if team.leader_id and team.leader_id not in team.member_ids:
                raise ValidationError(
                    _('Team leader must be included in team members.\n\n'
                      'Team: %s\nLeader: %s') % (team.name, team.leader_id.name)
                )

    # ========================
    # Business Methods
    # ========================
    def action_view_appointments(self):
        """Open appointments for this team"""
        self.ensure_one()
        return {
            'name': _('Team Appointments: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.appointment',
            'view_mode': 'calendar,tree,form',
            'domain': [('staff_id', 'in', self.member_ids.ids)],
            'context': {
                'default_team_id': self.id,
                'search_default_group_by_staff': 1
            }
        }

    def get_available_member(self, date):
        """
        Get next available team member based on assignment mode

        Args:
            date: datetime - Appointment date

        Returns:
            clinic.staff: Available staff member
        """
        self.ensure_one()

        if not self.member_ids:
            raise ValidationError(
                _('Team "%s" has no members assigned') % self.name
            )

        if self.assignment_mode == 'round_robin':
            return self._get_member_round_robin()
        elif self.assignment_mode == 'load_balanced':
            return self._get_member_load_balanced(date)
        else:
            # Manual assignment - return first member as default
            return self.member_ids[0]

    def _get_member_round_robin(self):
        """Simple round-robin assignment"""
        # Get last assigned member
        last_appointment = self.env['clinic.appointment'].search([
            ('staff_id', 'in', self.member_ids.ids)
        ], order='create_date desc', limit=1)

        if not last_appointment:
            return self.member_ids[0]

        # Find next member in sequence
        current_index = self.member_ids.ids.index(last_appointment.staff_id.id)
        next_index = (current_index + 1) % len(self.member_ids)
        return self.member_ids[next_index]

    def _get_member_load_balanced(self, date):
        """Load-balanced assignment (member with least appointments)"""
        member_loads = []
        for member in self.member_ids:
            count = self.env['clinic.appointment'].search_count([
                ('staff_id', '=', member.id),
                ('start', '>=', date.replace(hour=0, minute=0, second=0)),
                ('start', '<', date.replace(hour=23, minute=59, second=59)),
                ('state', 'not in', ['cancelled', 'no_show'])
            ])
            member_loads.append((member, count))

        # Return member with least appointments
        return min(member_loads, key=lambda x: x[1])[0]
