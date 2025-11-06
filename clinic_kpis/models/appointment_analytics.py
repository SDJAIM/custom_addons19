# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from datetime import datetime, date, timedelta


class AppointmentAnalytics(models.Model):
    _name = 'clinic.appointment.analytics'
    _description = 'Appointment Analytics'
    _auto = False  # This is a SQL view
    _order = 'appointment_date desc'

    # Appointment fields
    appointment_id = fields.Many2one('clinic.appointment', string='Appointment', readonly=True)
    appointment_date = fields.Datetime(string='Appointment Date', readonly=True)
    appointment_day = fields.Date(string='Day', readonly=True)
    appointment_week = fields.Char(string='Week', readonly=True)
    appointment_month = fields.Char(string='Month', readonly=True)
    appointment_year = fields.Integer(string='Year', readonly=True)
    day_of_week = fields.Selection([
        ('0', 'Sunday'),
        ('1', 'Monday'),
        ('2', 'Tuesday'),
        ('3', 'Wednesday'),
        ('4', 'Thursday'),
        ('5', 'Friday'),
        ('6', 'Saturday')
    ], string='Day of Week', readonly=True)
    hour_of_day = fields.Integer(string='Hour', readonly=True)
    is_weekend = fields.Boolean(string='Is Weekend', readonly=True)

    # Patient fields
    patient_id = fields.Many2one('clinic.patient', string='Patient', readonly=True)
    patient_age = fields.Integer(string='Patient Age', readonly=True)
    patient_gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender', readonly=True)
    is_new_patient = fields.Boolean(string='New Patient', readonly=True)

    # Doctor fields
    doctor_id = fields.Many2one('clinic.staff', string='Doctor', readonly=True)
    doctor_specialty = fields.Char(string='Specialty', readonly=True)

    # Branch/Location
    branch_id = fields.Many2one('clinic.branch', string='Branch', readonly=True)
    room_id = fields.Many2one('clinic.room', string='Room', readonly=True)

    # Appointment details
    service_type = fields.Char(string='Service Type', readonly=True)
    appointment_type = fields.Selection([
        ('regular', 'Regular'),
        ('urgent', 'Urgent'),
        ('follow_up', 'Follow-up'),
        ('telemedicine', 'Telemedicine')
    ], string='Appointment Type', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('arrived', 'Arrived'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show')
    ], string='Status', readonly=True)

    # Duration and timing
    scheduled_duration = fields.Float(string='Scheduled Duration (hrs)', readonly=True)
    actual_duration = fields.Float(string='Actual Duration (hrs)', readonly=True)
    waiting_time = fields.Float(string='Waiting Time (hrs)', readonly=True)
    lead_time = fields.Integer(string='Lead Time (days)', readonly=True)

    # Financial
    total_amount = fields.Float(string='Total Amount', readonly=True)
    insurance_amount = fields.Float(string='Insurance Amount', readonly=True)
    patient_amount = fields.Float(string='Patient Amount', readonly=True)
    is_paid = fields.Boolean(string='Is Paid', readonly=True)

    # Services
    service_count = fields.Integer(string='Service Count', readonly=True)
    has_lab_tests = fields.Boolean(string='Has Lab Tests', readonly=True)
    has_prescriptions = fields.Boolean(string='Has Prescriptions', readonly=True)
    has_procedures = fields.Boolean(string='Has Procedures', readonly=True)

    # Cancellation/No-show analysis
    cancellation_reason = fields.Char(string='Cancellation Reason', readonly=True)
    days_before_cancelled = fields.Integer(string='Days Before Cancelled', readonly=True)
    is_rescheduled = fields.Boolean(string='Was Rescheduled', readonly=True)

    # Utilization
    utilization_rate = fields.Float(string='Utilization Rate %', readonly=True)
    overbooking = fields.Boolean(string='Overbooked Slot', readonly=True)

    @api.model
    def init(self):
        """Initialize the SQL view for appointment analytics

        NOTE: Uses only fields that exist in clinic.appointment:
        - start (from calendar.event via _inherits)
        - duration (from calendar.event via _inherits)
        - consultation_start_time, consultation_end_time (actual consultation times)
        - waiting_time (in minutes, converted to hours)
        - parent_appointment_id (for rescheduling tracking)
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    a.id AS appointment_id,
                    ce.start AS appointment_date,
                    DATE(ce.start) AS appointment_day,
                    TO_CHAR(ce.start, 'YYYY-WW') AS appointment_week,
                    TO_CHAR(ce.start, 'YYYY-MM') AS appointment_month,
                    EXTRACT(YEAR FROM ce.start) AS appointment_year,
                    EXTRACT(DOW FROM ce.start)::text AS day_of_week,
                    EXTRACT(HOUR FROM ce.start) AS hour_of_day,
                    CASE
                        WHEN EXTRACT(DOW FROM ce.start) IN (0, 6) THEN TRUE
                        ELSE FALSE
                    END AS is_weekend,
                    a.patient_id AS patient_id,
                    DATE_PART('year', AGE(p.date_of_birth)) AS patient_age,
                    p.gender AS patient_gender,
                    CASE
                        WHEN ce.start = (
                            SELECT MIN(ce2.start)
                            FROM clinic_appointment a2
                            JOIN calendar_event ce2 ON ce2.id = a2.calendar_event_id
                            WHERE a2.patient_id = a.patient_id AND a2.state != 'cancelled'
                        ) THEN TRUE
                        ELSE FALSE
                    END AS is_new_patient,
                    a.staff_id AS doctor_id,
                    s.primary_specialization_id AS doctor_specialty,
                    a.branch_id AS branch_id,
                    a.room_id AS room_id,
                    a.service_type AS service_type,
                    NULL::varchar AS appointment_type,
                    a.state AS state,
                    ce.duration AS scheduled_duration,
                    CASE
                        WHEN a.consultation_end_time IS NOT NULL AND a.consultation_start_time IS NOT NULL THEN
                            EXTRACT(EPOCH FROM (a.consultation_end_time - a.consultation_start_time)) / 3600
                        ELSE ce.duration
                    END AS actual_duration,
                    (a.waiting_time / 60.0) AS waiting_time,
                    DATE_PART('day', ce.start - a.create_date) AS lead_time,
                    0::numeric AS total_amount,
                    0::numeric AS insurance_amount,
                    0::numeric AS patient_amount,
                    FALSE AS is_paid,
                    0 AS service_count,
                    FALSE AS has_lab_tests,
                    (
                        SELECT COUNT(*) > 0
                        FROM clinic_prescription pr
                        WHERE pr.appointment_id = a.id
                    ) AS has_prescriptions,
                    FALSE AS has_procedures,
                    NULL::varchar AS cancellation_reason,
                    NULL::integer AS days_before_cancelled,
                    CASE
                        WHEN a.parent_appointment_id IS NOT NULL THEN TRUE
                        ELSE FALSE
                    END AS is_rescheduled,
                    CASE
                        WHEN ce.duration > 0 AND a.state = 'done' THEN
                            (CASE
                                WHEN a.consultation_end_time IS NOT NULL AND a.consultation_start_time IS NOT NULL THEN
                                    EXTRACT(EPOCH FROM (a.consultation_end_time - a.consultation_start_time)) / 3600
                                ELSE ce.duration
                            END / ce.duration) * 100
                        ELSE 0
                    END AS utilization_rate,
                    CASE
                        WHEN (
                            SELECT COUNT(*)
                            FROM clinic_appointment ca2
                            JOIN calendar_event ce3 ON ce3.id = ca2.calendar_event_id
                            WHERE ca2.staff_id = a.staff_id
                                AND ce3.start::date = ce.start::date
                                AND ce3.start::time >= ce.start::time
                                AND ce3.start::time < (ce.start + (ce.duration || ' hours')::interval)::time
                                AND ca2.id != a.id
                                AND ca2.state NOT IN ('cancelled', 'no_show')
                        ) > 0 THEN TRUE
                        ELSE FALSE
                    END AS overbooking
                FROM clinic_appointment a
                JOIN calendar_event ce ON ce.id = a.calendar_event_id
                LEFT JOIN clinic_patient p ON p.id = a.patient_id
                LEFT JOIN clinic_staff s ON s.id = a.staff_id
            )
        """ % self._table)

    @api.model
    def get_appointment_statistics(self, date_from=None, date_to=None, doctor_id=None, branch_id=None):
        """Get appointment statistics for a period"""
        domain = []
        if date_from:
            domain.append(('appointment_date', '>=', date_from))
        if date_to:
            domain.append(('appointment_date', '<=', date_to))
        if doctor_id:
            domain.append(('doctor_id', '=', doctor_id))
        if branch_id:
            domain.append(('branch_id', '=', branch_id))

        analytics = self.search(domain)

        if not analytics:
            return self._get_empty_statistics()

        total = len(analytics)
        completed = len(analytics.filtered(lambda a: a.state == 'done'))
        cancelled = len(analytics.filtered(lambda a: a.state == 'cancelled'))
        no_shows = len(analytics.filtered(lambda a: a.state == 'no_show'))

        return {
            'total_appointments': total,
            'completed_appointments': completed,
            'cancelled_appointments': cancelled,
            'no_show_appointments': no_shows,
            'completion_rate': (completed / total * 100) if total else 0,
            'cancellation_rate': (cancelled / total * 100) if total else 0,
            'no_show_rate': (no_shows / total * 100) if total else 0,
            'avg_waiting_time': sum(analytics.mapped('waiting_time')) / len(analytics.filtered('waiting_time')) if analytics.filtered('waiting_time') else 0,
            'avg_duration': sum(analytics.mapped('actual_duration')) / len(analytics.filtered('actual_duration')) if analytics.filtered('actual_duration') else 0,
            'avg_lead_time': sum(analytics.mapped('lead_time')) / total if total else 0,
            'total_revenue': sum(analytics.mapped('total_amount')),
            'avg_revenue_per_appointment': sum(analytics.mapped('total_amount')) / total if total else 0,
            'new_patient_count': len(analytics.filtered('is_new_patient')),
            'service_count': sum(analytics.mapped('service_count')),
            'utilization_rate': sum(analytics.mapped('utilization_rate')) / total if total else 0,
            'overbooking_count': len(analytics.filtered('overbooking')),
            'peak_hours': self._get_peak_hours(analytics),
            'busiest_days': self._get_busiest_days(analytics),
        }

    def _get_empty_statistics(self):
        """Return empty statistics structure"""
        return {
            'total_appointments': 0,
            'completed_appointments': 0,
            'cancelled_appointments': 0,
            'no_show_appointments': 0,
            'completion_rate': 0,
            'cancellation_rate': 0,
            'no_show_rate': 0,
            'avg_waiting_time': 0,
            'avg_duration': 0,
            'avg_lead_time': 0,
            'total_revenue': 0,
            'avg_revenue_per_appointment': 0,
            'new_patient_count': 0,
            'service_count': 0,
            'utilization_rate': 0,
            'overbooking_count': 0,
            'peak_hours': [],
            'busiest_days': [],
        }

    def _get_peak_hours(self, analytics):
        """Get peak appointment hours"""
        hour_counts = {}
        for record in analytics:
            hour = record.hour_of_day
            if hour not in hour_counts:
                hour_counts[hour] = 0
            hour_counts[hour] += 1

        sorted_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        return [{'hour': f"{h:02d}:00", 'count': c} for h, c in sorted_hours]

    def _get_busiest_days(self, analytics):
        """Get busiest days of the week"""
        day_names = {
            '0': 'Sunday',
            '1': 'Monday',
            '2': 'Tuesday',
            '3': 'Wednesday',
            '4': 'Thursday',
            '5': 'Friday',
            '6': 'Saturday'
        }

        day_counts = {}
        for record in analytics:
            day = record.day_of_week
            if day not in day_counts:
                day_counts[day] = 0
            day_counts[day] += 1

        sorted_days = sorted(day_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        return [{'day': day_names.get(d, 'Unknown'), 'count': c} for d, c in sorted_days]

    @api.model
    def get_appointment_heatmap(self, date_from=None, date_to=None):
        """Get appointment heatmap data for visualization"""
        domain = []
        if date_from:
            domain.append(('appointment_date', '>=', date_from))
        if date_to:
            domain.append(('appointment_date', '<=', date_to))

        analytics = self.search(domain)

        # Create heatmap data structure
        heatmap_data = {}
        for record in analytics:
            day = record.day_of_week
            hour = record.hour_of_day
            key = f"{day}-{hour}"
            if key not in heatmap_data:
                heatmap_data[key] = 0
            heatmap_data[key] += 1

        # Convert to format suitable for frontend
        result = []
        for day in range(7):
            for hour in range(24):
                key = f"{day}-{hour}"
                result.append({
                    'day': day,
                    'hour': hour,
                    'count': heatmap_data.get(key, 0)
                })

        return result