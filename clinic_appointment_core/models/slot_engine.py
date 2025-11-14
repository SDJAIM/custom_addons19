# -*- coding: utf-8 -*-

from odoo import models, api, tools, _
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError
import pytz
import time  # TASK-F1-012: Performance metrics


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
    @tools.ormcache('appointment_type_id', 'start_date_str', 'end_date_str', 'timezone', 'staff_id')
    def _generate_slots_cached(self, appointment_type_id, start_date_str, end_date_str, timezone='UTC', staff_id=None):
        """
        ⚡ CACHED version of generate_slots (5 minute TTL)

        Args:
            appointment_type_id (int): Appointment type ID
            start_date_str (str): Start date as ISO string
            end_date_str (str): End date as ISO string
            timezone (str): User/browser timezone
            staff_id (int, optional): Specific staff member ID

        Returns:
            list: List of slot dictionaries
        """
        # Convert string dates back to datetime
        start_date = datetime.fromisoformat(start_date_str).date()
        end_date = datetime.fromisoformat(end_date_str).date()

        return self._generate_slots_internal(appointment_type_id, start_date, end_date, timezone, staff_id)

    @api.model
    def _invalidate_slot_cache(self):
        """
        ⚠️ CRITICAL: Invalidate slot cache (P0-003)

        This method MUST be called when any of these models change:
        - clinic.appointment (create/write/unlink)
        - clinic.staff.availability (write/unlink)
        - clinic.appointment.rule (write/unlink)
        - clinic.appointment.type (write of duration/buffers)
        - clinic.room (if used as resource)

        Multi-worker note: ormcache is in-process. In multi-worker deployments,
        there will be slight temporary inconsistency (acceptable for slots).
        """
        self.env['clinic.appointment.slot.engine']._generate_slots_cached.clear_cache(
            self.env['clinic.appointment.slot.engine']
        )

    @api.model
    def generate_slots(self, appointment_type_id, start_date, end_date, timezone='UTC', staff_id=None):
        """
        Generate available appointment slots

        This method normalizes inputs and calls the cached version for performance.
        TASK-F1-012: Logs performance metrics for monitoring.

        Args:
            appointment_type_id (int): Appointment type ID
            start_date (date/datetime/str): Start date for slot generation
            end_date (date/datetime/str): End date for slot generation
            timezone (str): User/browser timezone
            staff_id (int, optional): Specific staff member (or auto-assign)

        Returns:
            list: List of slot dictionaries with start, end, staff_id, available
        """
        # TASK-F1-012: Start performance timer
        start_time = time.time()

        # Normalize dates to ISO strings (for cache key)
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)

        start_date_str = start_date.date().isoformat() if isinstance(start_date, datetime) else start_date.isoformat()
        end_date_str = end_date.date().isoformat() if isinstance(end_date, datetime) else end_date.isoformat()

        # Convert to date objects for metrics
        start_date_obj = start_date.date() if isinstance(start_date, datetime) else start_date
        end_date_obj = end_date.date() if isinstance(end_date, datetime) else end_date

        # Check if this will be a cache hit (before calling cached method)
        # We can detect this by checking if the cache has the entry
        cache_key = (appointment_type_id, start_date_str, end_date_str, timezone, staff_id)
        cache_hit = hasattr(self._generate_slots_cached, 'lookup') and \
                    self._generate_slots_cached.lookup(self, *cache_key) is not None

        # Call cached version
        slots = self._generate_slots_cached(appointment_type_id, start_date_str, end_date_str, timezone, staff_id)

        # TASK-F1-012: Log performance metrics
        duration = time.time() - start_time

        try:
            self.env['clinic.slot.metrics'].sudo().create({
                'appointment_type_id': appointment_type_id,
                'staff_id': staff_id,
                'start_date': start_date_obj,
                'end_date': end_date_obj,
                'slots_generated': len(slots) if slots else 0,
                'duration_seconds': duration,
                'cache_hit': cache_hit,
                'timezone': timezone,
            })
        except Exception as e:
            # Don't fail slot generation if metrics logging fails
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning("Failed to log slot metrics: %s", str(e))

        return slots

    @api.model
    def _generate_slots_internal(self, appointment_type_id, start_date, end_date, timezone='UTC', staff_id=None):
        """
        Internal method for slot generation (called by cached wrapper)

        Args:
            appointment_type_id (int): Appointment type ID
            start_date (date): Start date
            end_date (date): End date
            timezone (str): User/browser timezone
            staff_id (int, optional): Specific staff member

        Returns:
            list: List of slot dictionaries
        """
        AppointmentType = self.env['clinic.appointment.type']

        # Get appointment type
        appt_type = AppointmentType.browse(appointment_type_id)
        if not appt_type.exists():
            raise ValidationError(_('Invalid appointment type'))

        # Get staff list
        if staff_id:
            staff_list = self.env['hr.employee'].browse(staff_id)
        else:
            staff_list = appt_type.allowed_staff_ids

        if not staff_list:
            return []

        # ⚡ PERFORMANCE OPTIMIZATION: Pre-load ALL appointments in range (1 query instead of N)
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        all_appointments = self.env['clinic.appointment'].search([
            ('staff_id', 'in', staff_list.ids),
            ('state', 'not in', ['cancelled', 'no_show']),
            ('start', '<', end_datetime),
            ('stop', '>', start_datetime)
        ])

        # Group appointments by staff_id (in memory) for fast lookup
        appts_by_staff = {}
        for appt in all_appointments:
            appts_by_staff.setdefault(appt.staff_id.id, []).append(appt)

        slots = []

        # Generate slots for each day in range
        current_date = start_date
        while current_date <= end_date:
            # Generate slots for this day (passing pre-loaded appointments)
            day_slots = self._generate_day_slots(
                appt_type,
                current_date,
                timezone,
                staff_list,
                appts_by_staff  # Pass pre-loaded appointments
            )
            slots.extend(day_slots)
            current_date += timedelta(days=1)

        return slots

    def _generate_day_slots(self, appt_type, check_date, user_timezone, staff_list, appts_by_staff=None):
        """
        Generate slots for a single day

        Args:
            appt_type: clinic.appointment.type record
            check_date: date object
            user_timezone: str (timezone name)
            staff_list: hr.employee recordset
            appts_by_staff: dict - Pre-loaded appointments grouped by staff_id (optional)

        Returns:
            list: Slots for this day
        """
        AppointmentRule = self.env['clinic.appointment.rule']
        slots = []

        # Initialize appts_by_staff if not provided (backward compatibility)
        if appts_by_staff is None:
            appts_by_staff = {}

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
                # Generate time slots within rule hours (passing pre-loaded appointments)
                rule_slots = self._generate_time_slots(
                    appt_type,
                    check_date,
                    rule,
                    staff,
                    user_timezone,
                    appts_by_staff  # Pass pre-loaded appointments
                )
                slots.extend(rule_slots)

        return slots

    def _generate_time_slots(self, appt_type, check_date, rule, staff, user_timezone, appts_by_staff=None):
        """
        Generate time slots for a specific rule and staff

        Args:
            appt_type: clinic.appointment.type record
            check_date: date object
            rule: clinic.appointment.rule record
            staff: hr.employee record
            user_timezone: str
            appts_by_staff: dict - Pre-loaded appointments grouped by staff_id (optional)

        Returns:
            list: Time slots
        """
        slots = []

        # Initialize appts_by_staff if not provided (backward compatibility)
        if appts_by_staff is None:
            appts_by_staff = {}

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

            # Check slot availability (using pre-loaded appointments)
            is_available, booked_count = self._check_slot_availability(
                appt_type,
                slot_start_utc,
                slot_end_utc,
                staff,
                appts_by_staff  # Pass pre-loaded appointments
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
                'booked': booked_count,
            })

            current_slot_start = current_slot_end

        return slots

    def _check_slot_availability(self, appt_type, slot_start_utc, slot_end_utc, staff, appts_by_staff=None):
        """
        Check if slot is available

        ⚡ PERFORMANCE: Uses pre-loaded appointments instead of database queries

        Args:
            appt_type: clinic.appointment.type record
            slot_start_utc: datetime (UTC)
            slot_end_utc: datetime (UTC)
            staff: hr.employee record
            appts_by_staff: dict - Pre-loaded appointments grouped by staff_id (optional)

        Returns:
            tuple: (is_available: bool, booked_count: int)
        """
        # Add buffers
        buffer_before_minutes = int(appt_type.buffer_before * 60)
        buffer_after_minutes = int(appt_type.buffer_after * 60)

        check_start = slot_start_utc - timedelta(minutes=buffer_before_minutes)
        check_end = slot_end_utc + timedelta(minutes=buffer_after_minutes)

        # Get pre-loaded appointments for this staff (or fallback to query)
        if appts_by_staff is not None and staff.id in appts_by_staff:
            # ⚡ FAST PATH: Use pre-loaded appointments (NO database query)
            staff_appointments = appts_by_staff[staff.id]

            # Count overlapping appointments in memory
            overlapping_count = 0
            for appt in staff_appointments:
                # Check if appointment overlaps with slot (considering buffers)
                if self._appointments_overlap(appt, check_start, check_end):
                    overlapping_count += 1

            existing_count = overlapping_count
        else:
            # 🐌 SLOW PATH: Fallback to database query (backward compatibility)
            Appointment = self.env['clinic.appointment']
            existing_count = Appointment.search_count([
                ('staff_id', '=', staff.id),
                ('state', 'not in', ['cancelled', 'no_show']),
                '|',
                '&', ('start', '>=', check_start), ('start', '<', check_end),
                '&', ('stop', '>', check_start), ('stop', '<=', check_end)
            ])

        # Check capacity
        is_available = existing_count < appt_type.capacity_per_slot
        return is_available, existing_count

    def _appointments_overlap(self, appointment, check_start, check_end):
        """
        Check if appointment overlaps with time range

        Args:
            appointment: clinic.appointment record
            check_start: datetime
            check_end: datetime

        Returns:
            bool: True if overlaps
        """
        # Appointment overlaps if:
        # - Appointment starts within range, OR
        # - Appointment ends within range, OR
        # - Appointment completely contains the range
        return (
            (appointment.start >= check_start and appointment.start < check_end) or
            (appointment.stop > check_start and appointment.stop <= check_end) or
            (appointment.start <= check_start and appointment.stop >= check_end)
        )

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
            # Assign to staff with least appointments in time slot
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

    def _filter_staff_by_language(self, staff_list, preferred_lang):
        """
        Filter staff by language capability (TASK-F2-003)

        Args:
            staff_list: clinic.staff recordset - Staff members to filter
            preferred_lang: str - Language code (e.g., 'en_US', 'es_ES')

        Returns:
            clinic.staff recordset - Filtered staff who speak the preferred language
        """
        if not preferred_lang:
            return staff_list

        # Filter staff who speak the preferred language
        filtered_staff = staff_list.filtered(
            lambda s: preferred_lang in s.language_ids.mapped('code')
        )

        # If no staff speaks the preferred language, return all staff
        # (better to show all options than show nothing)
        return filtered_staff if filtered_staff else staff_list
