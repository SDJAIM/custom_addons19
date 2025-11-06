# -*- coding: utf-8 -*-

from odoo import models, api, _
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError
import pytz


class SlotEngine(models.AbstractModel):
    """
    Slot Generation Engine
    Generates available appointment slots based on:
    - Appointment rules (availability)
    - Staff working schedules
    - Existing appointments
    - Capacity limits
    - Buffer times
    - Timezone conversions

    Replicates Odoo Enterprise Appointments slot generation
    """
    _name = 'clinic.appointment.slot.engine'
    _description = 'Appointment Slot Generation Engine'

    @api.model
    def generate_slots(self, appointment_type_id, start_date, end_date, timezone='UTC', staff_id=None):
        """
        Generate available appointment slots

        Args:
            appointment_type_id (int): Appointment type ID
            start_date (date/datetime): Start date for slot generation
            end_date (date/datetime): End date for slot generation
            timezone (str): User/browser timezone
            staff_id (int, optional): Specific staff member (or auto-assign)

        Returns:
            list: List of slot dictionaries with start, end, staff_id, available
        """
        AppointmentType = self.env['clinic.appointment.type']
        AppointmentRule = self.env['clinic.appointment.rule']

        # Get appointment type
        appt_type = AppointmentType.browse(appointment_type_id)
        if not appt_type.exists():
            raise ValidationError(_('Invalid appointment type'))

        # Convert dates to datetime if needed
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)

        # Get staff list
        if staff_id:
            staff_list = self.env['hr.employee'].browse(staff_id)
        else:
            staff_list = appt_type.allowed_staff_ids

        if not staff_list:
            return []

        slots = []

        # Generate slots for each day in range
        current_date = start_date.date() if isinstance(start_date, datetime) else start_date
        end_date_only = end_date.date() if isinstance(end_date, datetime) else end_date

        while current_date <= end_date_only:
            # Generate slots for this day
            day_slots = self._generate_day_slots(
                appt_type,
                current_date,
                timezone,
                staff_list
            )
            slots.extend(day_slots)
            current_date += timedelta(days=1)

        return slots

    def _generate_day_slots(self, appt_type, check_date, user_timezone, staff_list):
        """
        Generate slots for a single day

        Args:
            appt_type: clinic.appointment.type record
            check_date: date object
            user_timezone: str (timezone name)
            staff_list: hr.employee recordset

        Returns:
            list: Slots for this day
        """
        AppointmentRule = self.env['clinic.appointment.rule']
        slots = []

        # Get rules for this appointment type
        rules = AppointmentRule.search([
            ('type_id', '=', appt_type.id),
            ('active', '=', True)
        ])

        # Get weekday
        weekday = str(check_date.weekday())

        # Filter rules for this weekday and date
        active_rules = rules.filtered(lambda r: r.weekday == weekday and r.is_rule_active_for_date(check_date))

        if not active_rules:
            return []

        # For each rule, generate time slots
        for rule in active_rules:
            # Determine which staff to use
            if rule.staff_id:
                rule_staff = rule.staff_id
            else:
                rule_staff = staff_list

            for staff in rule_staff:
                # Generate time slots within rule hours
                rule_slots = self._generate_time_slots(
                    appt_type,
                    check_date,
                    rule,
                    staff,
                    user_timezone
                )
                slots.extend(rule_slots)

        return slots

    def _generate_time_slots(self, appt_type, check_date, rule, staff, user_timezone):
        """
        Generate time slots for a specific rule and staff

        Args:
            appt_type: clinic.appointment.type record
            check_date: date object
            rule: clinic.appointment.rule record
            staff: hr.employee record
            user_timezone: str

        Returns:
            list: Time slots
        """
        slots = []

        # Get rule timezone
        rule_tz = pytz.timezone(rule.timezone)
        user_tz = pytz.timezone(user_timezone)

        # Convert rule hours to datetime
        hour_from_int = int(rule.hour_from)
        minute_from = int((rule.hour_from - hour_from_int) * 60)
        hour_to_int = int(rule.hour_to)
        minute_to = int((rule.hour_to - hour_to_int) * 60)

        # Create start and end times in rule timezone
        start_time = rule_tz.localize(datetime.combine(
            check_date,
            datetime.min.time().replace(hour=hour_from_int, minute=minute_from)
        ))

        end_time = rule_tz.localize(datetime.combine(
            check_date,
            datetime.min.time().replace(hour=hour_to_int, minute=minute_to)
        ))

        # Get slot duration (from appointment type)
        slot_duration_hours = appt_type.default_duration
        slot_duration_minutes = int(slot_duration_hours * 60)

        # Generate slots
        current_slot_start = start_time

        while current_slot_start + timedelta(minutes=slot_duration_minutes) <= end_time:
            current_slot_end = current_slot_start + timedelta(minutes=slot_duration_minutes)

            # Convert to UTC for storage
            slot_start_utc = current_slot_start.astimezone(pytz.UTC).replace(tzinfo=None)
            slot_end_utc = current_slot_end.astimezone(pytz.UTC).replace(tzinfo=None)

            # Check slot availability
            is_available = self._check_slot_availability(
                appt_type,
                slot_start_utc,
                slot_end_utc,
                staff
            )

            # Convert to user timezone for display
            slot_start_user = current_slot_start.astimezone(user_tz)
            slot_end_user = current_slot_end.astimezone(user_tz)

            slots.append({
                'start': slot_start_utc,  # UTC for DB
                'end': slot_end_utc,  # UTC for DB
                'start_display': slot_start_user.isoformat(),  # User TZ for display
                'end_display': slot_end_user.isoformat(),  # User TZ for display
                'staff_id': staff.id,
                'staff_name': staff.name,
                'available': is_available,
                'capacity': appt_type.capacity_per_slot,
                'booked': self._count_booked_appointments(slot_start_utc, slot_end_utc, staff) if not is_available else 0,
            })

            current_slot_start = current_slot_end

        return slots

    def _check_slot_availability(self, appt_type, slot_start_utc, slot_end_utc, staff):
        """
        Check if slot is available

        Args:
            appt_type: clinic.appointment.type record
            slot_start_utc: datetime (UTC)
            slot_end_utc: datetime (UTC)
            staff: hr.employee record

        Returns:
            bool: True if available
        """
        Appointment = self.env['clinic.appointment']

        # Add buffers
        buffer_before_minutes = int(appt_type.buffer_before * 60)
        buffer_after_minutes = int(appt_type.buffer_after * 60)

        check_start = slot_start_utc - timedelta(minutes=buffer_before_minutes)
        check_end = slot_end_utc + timedelta(minutes=buffer_after_minutes)

        # Count existing appointments in this slot (excluding cancelled/no_show)
        existing_count = Appointment.search_count([
            ('staff_id', '=', staff.id),
            ('state', 'not in', ['cancelled', 'no_show']),
            '|',
            '&', ('start', '>=', check_start), ('start', '<', check_end),
            '&', ('stop', '>', check_start), ('stop', '<=', check_end)
        ])

        # Check capacity
        return existing_count < appt_type.capacity_per_slot

    def _count_booked_appointments(self, slot_start_utc, slot_end_utc, staff):
        """Count booked appointments in slot"""
        Appointment = self.env['clinic.appointment']

        return Appointment.search_count([
            ('staff_id', '=', staff.id),
            ('state', 'not in', ['cancelled', 'no_show']),
            '|',
            '&', ('start', '>=', slot_start_utc), ('start', '<', slot_end_utc),
            '&', ('stop', '>', slot_start_utc), ('stop', '<=', slot_end_utc)
        ])

    @api.model
    def get_next_available_slot(self, appointment_type_id, timezone='UTC', staff_id=None):
        """
        Get the next available appointment slot

        Args:
            appointment_type_id (int): Appointment type ID
            timezone (str): User timezone
            staff_id (int, optional): Specific staff member

        Returns:
            dict: Next available slot or False
        """
        appt_type = self.env['clinic.appointment.type'].browse(appointment_type_id)

        # Calculate search range
        today = datetime.now().date()
        end_date = today + timedelta(days=appt_type.max_days_ahead)

        # Honor minimum notice
        min_notice_hours = appt_type.min_notice_hours
        start_datetime = datetime.now() + timedelta(hours=min_notice_hours)

        # Generate slots
        slots = self.generate_slots(
            appointment_type_id,
            start_datetime,
            end_date,
            timezone=timezone,
            staff_id=staff_id
        )

        # Find first available slot
        for slot in slots:
            if slot['available']:
                return slot

        return False

    @api.model
    def assign_staff_by_mode(self, appointment_type_id, slot_start, slot_end, assignment_mode=None):
        """
        Assign staff based on appointment type assignment mode

        Args:
            appointment_type_id: int
            slot_start: datetime
            slot_end: datetime
            assignment_mode: str (optional override)

        Returns:
            int: staff_id
        """
        appt_type = self.env['clinic.appointment.type'].browse(appointment_type_id)
        mode = assignment_mode or appt_type.assign_mode
        staff_list = appt_type.allowed_staff_ids

        if not staff_list:
            return False

        if mode == 'random':
            import random
            return random.choice(staff_list).id

        elif mode == 'round_robin':
            # Get last assigned staff for this type
            last_appt = self.env['clinic.appointment'].search([
                ('appointment_type_id', '=', appointment_type_id),
                ('staff_id', 'in', staff_list.ids)
            ], order='create_date desc', limit=1)

            if last_appt and last_appt.staff_id in staff_list:
                # Get next staff in list
                current_index = list(staff_list).index(last_appt.staff_id)
                next_index = (current_index + 1) % len(staff_list)
                return staff_list[next_index].id
            else:
                return staff_list[0].id

        elif mode == 'by_skill':
            # TODO: Implement skill-based assignment
            # For now, return staff with least appointments
            staff_with_counts = []
            for staff in staff_list:
                count = self.env['clinic.appointment'].search_count([
                    ('staff_id', '=', staff.id),
                    ('start', '>=', slot_start),
                    ('start', '<', slot_end)
                ])
                staff_with_counts.append((staff.id, count))

            staff_with_counts.sort(key=lambda x: x[1])
            return staff_with_counts[0][0]

        elif mode == 'customer_choice':
            # Return all available staff for customer to choose
            return staff_list.ids

        return staff_list[0].id
