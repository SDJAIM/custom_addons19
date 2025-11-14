# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class AppointmentDashboard(models.Model):
    """
    Advanced Analytics Dashboard Data Provider (TASK-F3-004)

    Provides aggregated data for the OWL dashboard component
    """
    _name = 'clinic.appointment.dashboard'
    _description = 'Appointment Dashboard Data'

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None, branch_id=None, staff_id=None):
        """
        Get comprehensive dashboard data with filters

        Args:
            date_from (str): Start date (YYYY-MM-DD)
            date_to (str): End date (YYYY-MM-DD)
            branch_id (int): Branch filter
            staff_id (int): Staff filter

        Returns:
            dict: Dashboard data with KPIs, charts, and metrics
        """
        # Default date range: last 30 days
        if not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')

        # Build domain
        domain = [
            ('start', '>=', date_from),
            ('start', '<=', date_to),
        ]

        if branch_id:
            domain.append(('branch_id', '=', branch_id))
        if staff_id:
            domain.append(('staff_id', '=', staff_id))

        # Get appointments
        appointments = self.env['clinic.appointment'].search(domain)

        return {
            'kpis': self._compute_kpis(appointments, date_from, date_to),
            'appointments_by_status': self._get_appointments_by_status(appointments),
            'appointments_by_type': self._get_appointments_by_type(appointments),
            'appointments_timeline': self._get_appointments_timeline(appointments, date_from, date_to),
            'top_staff': self._get_top_staff(appointments),
            'top_services': self._get_top_services(appointments),
            'hourly_distribution': self._get_hourly_distribution(appointments),
            'branch_performance': self._get_branch_performance(date_from, date_to),
            'patient_metrics': self._get_patient_metrics(appointments),
            'revenue_data': self._get_revenue_data(appointments),
            'slot_performance': self._get_slot_performance_metrics(days=30),  # TASK-F1-012
        }

    def _compute_kpis(self, appointments, date_from, date_to):
        """Compute main KPIs"""
        total = len(appointments)
        completed = len(appointments.filtered(lambda a: a.state == 'completed'))
        cancelled = len(appointments.filtered(lambda a: a.state == 'cancelled'))
        no_show = len(appointments.filtered(lambda a: a.state == 'no_show'))

        # Completion rate
        completion_rate = (completed / total * 100) if total > 0 else 0

        # Cancellation rate
        cancellation_rate = (cancelled / total * 100) if total > 0 else 0

        # No-show rate
        no_show_rate = (no_show / total * 100) if total > 0 else 0

        # Unique patients
        unique_patients = len(set(appointments.mapped('patient_id.id')))

        # Average per day
        days = (datetime.strptime(date_to, '%Y-%m-%d') - datetime.strptime(date_from, '%Y-%m-%d')).days + 1
        avg_per_day = total / days if days > 0 else 0

        # Compare with previous period
        prev_domain = [
            ('start', '>=', (datetime.strptime(date_from, '%Y-%m-%d') - timedelta(days=days)).strftime('%Y-%m-%d')),
            ('start', '<', date_from),
        ]
        prev_total = self.env['clinic.appointment'].search_count(prev_domain)
        growth = ((total - prev_total) / prev_total * 100) if prev_total > 0 else 0

        return {
            'total_appointments': total,
            'completed': completed,
            'cancelled': cancelled,
            'no_show': no_show,
            'completion_rate': round(completion_rate, 1),
            'cancellation_rate': round(cancellation_rate, 1),
            'no_show_rate': round(no_show_rate, 1),
            'unique_patients': unique_patients,
            'avg_per_day': round(avg_per_day, 1),
            'growth_percentage': round(growth, 1),
        }

    def _get_appointments_by_status(self, appointments):
        """Get appointments grouped by status"""
        status_count = {}
        for appointment in appointments:
            state = appointment.state or 'draft'
            status_count[state] = status_count.get(state, 0) + 1

        return [
            {'status': status, 'count': count}
            for status, count in status_count.items()
        ]

    def _get_appointments_by_type(self, appointments):
        """Get appointments grouped by type"""
        type_count = {}
        for appointment in appointments:
            appt_type = appointment.appointment_type_id.name if appointment.appointment_type_id else 'N/A'
            type_count[appt_type] = type_count.get(appt_type, 0) + 1

        return sorted(
            [{'type': appt_type, 'count': count} for appt_type, count in type_count.items()],
            key=lambda x: x['count'],
            reverse=True
        )[:10]  # Top 10

    def _get_appointments_timeline(self, appointments, date_from, date_to):
        """Get appointments timeline (daily)"""
        timeline = {}

        # Initialize all dates with 0
        current_date = datetime.strptime(date_from, '%Y-%m-%d')
        end_date = datetime.strptime(date_to, '%Y-%m-%d')

        while current_date <= end_date:
            timeline[current_date.strftime('%Y-%m-%d')] = 0
            current_date += timedelta(days=1)

        # Count appointments per day
        for appointment in appointments:
            if appointment.start:
                date_key = appointment.start.strftime('%Y-%m-%d')
                if date_key in timeline:
                    timeline[date_key] += 1

        return [
            {'date': date, 'count': count}
            for date, count in sorted(timeline.items())
        ]

    def _get_top_staff(self, appointments):
        """Get top performing staff"""
        staff_count = {}
        for appointment in appointments:
            if appointment.staff_id:
                staff_id = appointment.staff_id.id
                staff_name = appointment.staff_id.name
                if staff_id not in staff_count:
                    staff_count[staff_id] = {'name': staff_name, 'count': 0, 'completed': 0}
                staff_count[staff_id]['count'] += 1
                if appointment.state == 'completed':
                    staff_count[staff_id]['completed'] += 1

        # Calculate completion rate and sort
        result = []
        for staff_id, data in staff_count.items():
            completion_rate = (data['completed'] / data['count'] * 100) if data['count'] > 0 else 0
            result.append({
                'staff_id': staff_id,
                'name': data['name'],
                'appointments': data['count'],
                'completed': data['completed'],
                'completion_rate': round(completion_rate, 1)
            })

        return sorted(result, key=lambda x: x['appointments'], reverse=True)[:10]

    def _get_top_services(self, appointments):
        """Get top services"""
        service_count = {}
        for appointment in appointments:
            service = appointment.service_type or 'other'
            service_count[service] = service_count.get(service, 0) + 1

        return [
            {'service': service, 'count': count}
            for service, count in sorted(service_count.items(), key=lambda x: x[1], reverse=True)
        ]

    def _get_hourly_distribution(self, appointments):
        """Get appointment distribution by hour"""
        hourly = {}
        for hour in range(24):
            hourly[hour] = 0

        for appointment in appointments:
            if appointment.start:
                hour = appointment.start.hour
                hourly[hour] += 1

        return [
            {'hour': f"{hour:02d}:00", 'count': count}
            for hour, count in sorted(hourly.items())
            if count > 0  # Only show hours with appointments
        ]

    def _get_branch_performance(self, date_from, date_to):
        """Get performance by branch"""
        branches = self.env['clinic.branch'].search([])
        result = []

        for branch in branches:
            appointments = self.env['clinic.appointment'].search([
                ('branch_id', '=', branch.id),
                ('start', '>=', date_from),
                ('start', '<=', date_to),
            ])

            total = len(appointments)
            completed = len(appointments.filtered(lambda a: a.state == 'completed'))
            completion_rate = (completed / total * 100) if total > 0 else 0

            result.append({
                'branch_id': branch.id,
                'name': branch.name,
                'total': total,
                'completed': completed,
                'completion_rate': round(completion_rate, 1)
            })

        return sorted(result, key=lambda x: x['total'], reverse=True)

    def _get_patient_metrics(self, appointments):
        """Get patient-related metrics"""
        unique_patients = set(appointments.mapped('patient_id.id'))
        new_patients = 0
        returning_patients = 0

        for patient_id in unique_patients:
            patient_appointments = appointments.filtered(lambda a: a.patient_id.id == patient_id)
            if len(patient_appointments) == 1:
                new_patients += 1
            else:
                returning_patients += 1

        return {
            'total_patients': len(unique_patients),
            'new_patients': new_patients,
            'returning_patients': returning_patients,
            'avg_appointments_per_patient': round(len(appointments) / len(unique_patients), 1) if unique_patients else 0
        }

    def _get_revenue_data(self, appointments):
        """Get revenue-related data (placeholder)"""
        # This would integrate with accounting/finance module
        # For now, return placeholder data
        return {
            'total_revenue': 0.0,
            'avg_revenue_per_appointment': 0.0,
            'revenue_by_type': []
        }

    def _get_slot_performance_metrics(self, days=30):
        """
        Get slot engine performance metrics (TASK-F1-012)

        Args:
            days (int): Number of days to look back

        Returns:
            dict: Slot performance KPIs and trends
        """
        metrics_model = self.env['clinic.slot.metrics']

        # Get aggregated statistics
        stats = metrics_model.get_performance_stats(days=days)

        # Get trend data for charts
        trend = metrics_model.get_performance_trend(days=min(days, 7))

        # Alert if P95 exceeds 2 seconds threshold
        p95_alert = stats.get('p95_duration', 0) > 2.0

        return {
            'avg_duration': round(stats.get('avg_duration', 0), 3),
            'p95_duration': round(stats.get('p95_duration', 0), 3),
            'cache_hit_rate': round(stats.get('cache_hit_rate', 0), 1),
            'slow_query_count': stats.get('slow_query_count', 0),
            'slow_query_rate': round(stats.get('slow_query_rate', 0), 1),
            'total_requests': stats.get('total_requests', 0),
            'avg_slots_per_request': round(stats.get('avg_slots_per_request', 0), 0),
            'p95_alert': p95_alert,
            'trend': trend,
        }

    @api.model
    def get_filters_data(self):
        """Get data for dashboard filters"""
        branches = self.env['clinic.branch'].search([])
        staff = self.env['clinic.staff'].search([('state', '=', 'active')])

        return {
            'branches': [{'id': b.id, 'name': b.name} for b in branches],
            'staff': [{'id': s.id, 'name': s.name} for s in staff],
        }
