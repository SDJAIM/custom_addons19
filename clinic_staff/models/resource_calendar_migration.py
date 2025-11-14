# -*- coding: utf-8 -*-
"""
TASK-F3-006: Resource Calendar Migration

Utilities for migrating from custom clinic.staff.schedule to Odoo's standard resource.calendar
and from clinic.staff.availability to resource.calendar.leaves

Benefits:
- Integration with hr.leave (vacations, sick leave)
- Global holidays support
- Better timezone handling
- Less custom code to maintain

This provides both migration tools and backward compatibility layer.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class ResourceCalendarMigration(models.TransientModel):
    """
    Wizard to migrate staff schedules to resource calendar
    """
    _name = 'clinic.staff.resource.migration'
    _description = 'Staff to Resource Calendar Migration Wizard'

    staff_ids = fields.Many2many(
        'clinic.staff',
        string='Staff to Migrate',
        help='Leave empty to migrate all staff'
    )

    migrate_schedules = fields.Boolean(
        string='Migrate Weekly Schedules',
        default=True,
        help='Convert clinic.staff.schedule to resource.calendar.attendance'
    )

    migrate_availability = fields.Boolean(
        string='Migrate Availability Exceptions',
        default=True,
        help='Convert clinic.staff.availability to resource.calendar.leaves'
    )

    keep_legacy_data = fields.Boolean(
        string='Keep Legacy Data',
        default=True,
        help='Keep original schedule/availability records for backup'
    )

    migration_log = fields.Text(
        string='Migration Log',
        readonly=True
    )

    def action_migrate(self):
        """Execute the migration"""
        self.ensure_one()

        log_lines = []
        staff_to_migrate = self.staff_ids or self.env['clinic.staff'].search([('active', '=', True)])

        log_lines.append(f"Starting migration for {len(staff_to_migrate)} staff members...")
        log_lines.append("=" * 80)

        for staff in staff_to_migrate:
            try:
                log_lines.append(f"\nProcessing: {staff.name} ({staff.staff_code})")

                # Create or get resource calendar
                calendar = self._get_or_create_calendar(staff)
                log_lines.append(f"  Calendar: {calendar.name}")

                # Migrate schedules
                if self.migrate_schedules:
                    schedule_count = self._migrate_staff_schedules(staff, calendar)
                    log_lines.append(f"  ✓ Migrated {schedule_count} schedule records")

                # Migrate availability exceptions
                if self.migrate_availability:
                    availability_count = self._migrate_staff_availability(staff, calendar)
                    log_lines.append(f"  ✓ Migrated {availability_count} availability exceptions")

                # Link calendar to staff
                staff.resource_calendar_id = calendar.id
                log_lines.append(f"  ✓ Linked calendar to staff")

            except Exception as e:
                log_lines.append(f"  ✗ ERROR: {str(e)}")
                _logger.error(f"Migration failed for staff {staff.name}: {e}", exc_info=True)

        log_lines.append("\n" + "=" * 80)
        log_lines.append("Migration completed!")

        self.migration_log = "\n".join(log_lines)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_or_create_calendar(self, staff):
        """Get existing calendar or create a new one"""
        if staff.resource_calendar_id:
            return staff.resource_calendar_id

        # Create new calendar
        calendar = self.env['resource.calendar'].create({
            'name': f"{staff.name}'s Working Hours",
            'company_id': staff.company_id.id or self.env.company.id,
            'tz': staff.user_id.tz or self.env.user.tz or 'UTC',
        })

        return calendar

    def _migrate_staff_schedules(self, staff, calendar):
        """
        Migrate clinic.staff.schedule to resource.calendar.attendance

        clinic.staff.schedule -> resource.calendar.attendance mapping:
        - day_of_week (0-6) -> dayofweek (0-6)
        - start_time (float) -> hour_from (float)
        - end_time (float) -> hour_to (float)
        - break handled as separate attendance record
        """
        schedules = self.env['clinic.staff.schedule'].search([
            ('staff_id', '=', staff.id),
            ('is_available', '=', True)
        ])

        day_name_map = {
            '0': 'Monday',
            '1': 'Tuesday',
            '2': 'Wednesday',
            '3': 'Thursday',
            '4': 'Friday',
            '5': 'Saturday',
            '6': 'Sunday'
        }

        count = 0
        for schedule in schedules:
            # Check if attendance already exists
            existing = self.env['resource.calendar.attendance'].search([
                ('calendar_id', '=', calendar.id),
                ('dayofweek', '=', schedule.day_of_week),
                ('hour_from', '=', schedule.start_time),
            ])

            if existing:
                _logger.info(f"Attendance already exists for {staff.name} on {day_name_map[schedule.day_of_week]}")
                continue

            # Create morning session (before break)
            if schedule.break_start and schedule.break_end:
                # Morning: start_time -> break_start
                self.env['resource.calendar.attendance'].create({
                    'calendar_id': calendar.id,
                    'dayofweek': schedule.day_of_week,
                    'hour_from': schedule.start_time,
                    'hour_to': schedule.break_start,
                    'name': f"{day_name_map[schedule.day_of_week]} Morning",
                    'day_period': 'morning',
                })

                # Afternoon: break_end -> end_time
                self.env['resource.calendar.attendance'].create({
                    'calendar_id': calendar.id,
                    'dayofweek': schedule.day_of_week,
                    'hour_from': schedule.break_end,
                    'hour_to': schedule.end_time,
                    'name': f"{day_name_map[schedule.day_of_week]} Afternoon",
                    'day_period': 'afternoon',
                })
                count += 2
            else:
                # Full day without break
                self.env['resource.calendar.attendance'].create({
                    'calendar_id': calendar.id,
                    'dayofweek': schedule.day_of_week,
                    'hour_from': schedule.start_time,
                    'hour_to': schedule.end_time,
                    'name': day_name_map[schedule.day_of_week],
                })
                count += 1

            # Optionally archive legacy schedule
            if not self.keep_legacy_data:
                schedule.active = False

        return count

    def _migrate_staff_availability(self, staff, calendar):
        """
        Migrate clinic.staff.availability to resource.calendar.leaves

        clinic.staff.availability -> resource.calendar.leaves mapping:
        - availability_type == 'unavailable' -> time_type = 'leave'
        - reason -> name
        - date -> date_from, date_to (full day)
        - limited availability -> partial day leave
        """
        availabilities = self.env['clinic.staff.availability'].search([
            ('staff_id', '=', staff.id),
            ('date', '>=', fields.Date.today())  # Only future/current
        ])

        count = 0
        for avail in availabilities:
            # Skip 'available' type (no leave needed)
            if avail.availability_type == 'available':
                continue

            # Check if leave already exists
            existing = self.env['resource.calendar.leaves'].search([
                ('calendar_id', '=', calendar.id),
                ('date_from', '<=', avail.date),
                ('date_to', '>=', avail.date),
            ])

            if existing:
                _logger.info(f"Leave already exists for {staff.name} on {avail.date}")
                continue

            # Convert to datetime
            if avail.availability_type == 'unavailable':
                # Full day unavailable
                date_from = datetime.combine(avail.date, datetime.min.time())
                date_to = datetime.combine(avail.date, datetime.max.time())
            else:  # limited
                # Partial day - unavailable outside limited hours
                # Create leave for before start_time
                if avail.start_time > 0:
                    date_from = datetime.combine(avail.date, datetime.min.time())
                    hours_from = int(avail.start_time)
                    minutes_from = int((avail.start_time - hours_from) * 60)
                    date_to = datetime.combine(avail.date, datetime.min.time().replace(
                        hour=hours_from,
                        minute=minutes_from
                    ))

                    self.env['resource.calendar.leaves'].create({
                        'name': f"Limited availability - Before {avail.start_time}h",
                        'calendar_id': calendar.id,
                        'date_from': date_from,
                        'date_to': date_to,
                        'resource_id': staff.resource_id.id if staff.resource_id else False,
                    })
                    count += 1

                # Create leave for after end_time
                if avail.end_time < 24:
                    hours_to = int(avail.end_time)
                    minutes_to = int((avail.end_time - hours_to) * 60)
                    date_from = datetime.combine(avail.date, datetime.min.time().replace(
                        hour=hours_to,
                        minute=minutes_to
                    ))
                    date_to = datetime.combine(avail.date, datetime.max.time())

                    self.env['resource.calendar.leaves'].create({
                        'name': f"Limited availability - After {avail.end_time}h",
                        'calendar_id': calendar.id,
                        'date_from': date_from,
                        'date_to': date_to,
                        'resource_id': staff.resource_id.id if staff.resource_id else False,
                    })
                    count += 1
                continue

            # Create full-day leave
            reason_map = {
                'leave': 'Leave',
                'sick': 'Sick Leave',
                'emergency': 'Emergency',
                'training': 'Training',
                'conference': 'Conference',
                'other': 'Other'
            }

            self.env['resource.calendar.leaves'].create({
                'name': reason_map.get(avail.reason, 'Unavailable'),
                'calendar_id': calendar.id,
                'date_from': date_from,
                'date_to': date_to,
                'resource_id': staff.resource_id.id if staff.resource_id else False,
            })
            count += 1

            # Optionally archive legacy availability
            if not self.keep_legacy_data:
                avail.active = False

        return count


class ClinicStaffResourceCalendar(models.Model):
    """
    Extend clinic.staff with resource calendar helper methods
    """
    _inherit = 'clinic.staff'

    use_resource_calendar = fields.Boolean(
        string='Use Resource Calendar',
        default=False,
        help='Use standard Odoo resource calendar instead of custom schedules'
    )

    legacy_schedule_count = fields.Integer(
        string='Legacy Schedules',
        compute='_compute_legacy_schedule_count'
    )

    @api.depends('resource_calendar_id')
    def _compute_legacy_schedule_count(self):
        """Count legacy schedule records"""
        for staff in self:
            staff.legacy_schedule_count = self.env['clinic.staff.schedule'].search_count([
                ('staff_id', '=', staff.id)
            ])

    def action_open_resource_calendar(self):
        """Open the resource calendar"""
        self.ensure_one()

        if not self.resource_calendar_id:
            # Create calendar if doesn't exist
            calendar = self.env['resource.calendar'].create({
                'name': f"{self.name}'s Working Hours",
                'company_id': self.company_id.id or self.env.company.id,
                'tz': self.user_id.tz or self.env.user.tz or 'UTC',
            })
            self.resource_calendar_id = calendar.id

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'resource.calendar',
            'res_id': self.resource_calendar_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_migrate_to_resource_calendar(self):
        """Launch migration wizard for this staff member"""
        self.ensure_one()

        wizard = self.env['clinic.staff.resource.migration'].create({
            'staff_ids': [(6, 0, self.ids)],
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.staff.resource.migration',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def get_work_intervals(self, start_dt, end_dt):
        """
        Get work intervals using resource calendar (TASK-F3-006)

        This replaces the custom schedule lookup with Odoo's standard method.

        Args:
            start_dt: Start datetime
            end_dt: End datetime

        Returns:
            List of (start, end, attendance) tuples
        """
        self.ensure_one()

        if not self.use_resource_calendar or not self.resource_calendar_id:
            # Fall back to legacy method
            return self._get_work_intervals_legacy(start_dt, end_dt)

        # Use Odoo's built-in resource calendar method
        intervals = self.resource_calendar_id._work_intervals_batch(
            start_dt,
            end_dt,
            resources=self.resource_id,
            tz=self.resource_calendar_id.tz
        )

        # Convert to list of tuples
        result = []
        for interval in intervals[self.resource_id.id if self.resource_id else False]:
            result.append((interval[0], interval[1], interval[2]))

        return result

    def _get_work_intervals_legacy(self, start_dt, end_dt):
        """
        Legacy method using clinic.staff.schedule

        Kept for backward compatibility during migration period
        """
        self.ensure_one()

        schedules = self.env['clinic.staff.schedule'].search([
            ('staff_id', '=', self.id),
            ('is_available', '=', True)
        ])

        intervals = []
        current_date = start_dt.date()

        while current_date <= end_dt.date():
            day_of_week = str(current_date.weekday())

            day_schedules = schedules.filtered(lambda s: s.day_of_week == day_of_week)

            for schedule in day_schedules:
                slots = schedule.get_available_slots(current_date)
                for slot in slots:
                    if start_dt <= slot['datetime'] <= end_dt:
                        intervals.append((
                            slot['datetime'],
                            slot['datetime'] + timedelta(hours=schedule.slot_duration),
                            schedule
                        ))

            current_date += timedelta(days=1)

        return intervals
