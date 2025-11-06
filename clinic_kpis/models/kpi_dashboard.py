# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from datetime import datetime, timedelta, date
import json
import logging

_logger = logging.getLogger(__name__)


class KPIDashboard(models.Model):
    _name = 'clinic.kpi.dashboard'
    _description = 'KPI Dashboard'
    _order = 'create_date desc'
    
    name = fields.Char(
        string='Dashboard Name',
        required=True
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user
    )
    
    is_default = fields.Boolean(
        string='Default Dashboard',
        default=False
    )
    
    # KPI Widgets Configuration
    show_appointments_today = fields.Boolean(
        string='Today\'s Appointments',
        default=True
    )
    
    show_revenue_mtd = fields.Boolean(
        string='Revenue MTD',
        default=True
    )
    
    show_new_patients = fields.Boolean(
        string='New Patients',
        default=True
    )
    
    show_no_show_rate = fields.Boolean(
        string='No-Show Rate',
        default=True
    )
    
    show_avg_wait_time = fields.Boolean(
        string='Average Wait Time',
        default=True
    )
    
    show_claim_status = fields.Boolean(
        string='Claims Status',
        default=True
    )
    
    show_top_procedures = fields.Boolean(
        string='Top Procedures',
        default=True
    )
    
    show_staff_utilization = fields.Boolean(
        string='Staff Utilization',
        default=True
    )
    
    # Refresh Settings
    auto_refresh = fields.Boolean(
        string='Auto Refresh',
        default=True
    )
    
    refresh_interval = fields.Integer(
        string='Refresh Interval (seconds)',
        default=300  # 5 minutes
    )
    
    last_refresh = fields.Datetime(
        string='Last Refresh',
        readonly=True
    )
    
    @api.model
    def get_dashboard_data(self, dashboard_id=None):
        """Get all dashboard KPI data"""
        if dashboard_id:
            dashboard = self.browse(dashboard_id)
        else:
            dashboard = self.search([
                ('user_id', '=', self.env.user.id),
                ('is_default', '=', True)
            ], limit=1) or self.search([
                ('user_id', '=', self.env.user.id)
            ], limit=1)
        
        if not dashboard:
            # Create default dashboard
            dashboard = self.create({
                'name': 'My Dashboard',
                'is_default': True
            })
        
        data = {
            'dashboard_id': dashboard.id,
            'dashboard_name': dashboard.name,
            'last_refresh': fields.Datetime.now(),
            'kpis': {}
        }
        
        # Collect KPI data based on configuration
        if dashboard.show_appointments_today:
            data['kpis']['appointments_today'] = self._get_appointments_today()
        
        if dashboard.show_revenue_mtd:
            data['kpis']['revenue_mtd'] = self._get_revenue_mtd()
        
        if dashboard.show_new_patients:
            data['kpis']['new_patients'] = self._get_new_patients()
        
        if dashboard.show_no_show_rate:
            data['kpis']['no_show_rate'] = self._get_no_show_rate()
        
        if dashboard.show_avg_wait_time:
            data['kpis']['avg_wait_time'] = self._get_avg_wait_time()
        
        if dashboard.show_claim_status:
            data['kpis']['claim_status'] = self._get_claim_status()
        
        if dashboard.show_top_procedures:
            data['kpis']['top_procedures'] = self._get_top_procedures()
        
        if dashboard.show_staff_utilization:
            data['kpis']['staff_utilization'] = self._get_staff_utilization()
        
        # Update last refresh
        dashboard.last_refresh = fields.Datetime.now()
        
        return data
    
    @tools.ormcache('self.id', 'fields.Date.today()')
    def _get_appointments_today(self):
        """Get today's appointments statistics - cached per day"""
        today = fields.Date.today()
        appointments = self.env['clinic.appointment'].search([
            ('start', '>=', today.strftime('%Y-%m-%d 00:00:00')),
            ('start', '<=', today.strftime('%Y-%m-%d 23:59:59'))
        ])
        
        return {
            'title': _("Today's Appointments"),
            'value': len(appointments),
            'details': {
                'confirmed': len(appointments.filtered(lambda a: a.state == 'confirmed')),
                'arrived': len(appointments.filtered(lambda a: a.state == 'arrived')),
                'in_progress': len(appointments.filtered(lambda a: a.state == 'in_progress')),
                'done': len(appointments.filtered(lambda a: a.state == 'done')),
                'no_show': len(appointments.filtered(lambda a: a.state == 'no_show')),
            },
            'icon': 'fa-calendar',
            'color': 'primary',
            'trend': self._calculate_trend('appointments', len(appointments))
        }
    
    def _get_revenue_mtd(self):
        """Get month-to-date revenue"""
        start_date = date.today().replace(day=1)
        invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', start_date),
            ('appointment_id', '!=', False)
        ])
        
        total_revenue = sum(invoices.mapped('amount_total'))
        
        return {
            'title': _('Revenue MTD'),
            'value': total_revenue,
            'formatted_value': f"${total_revenue:,.2f}",
            'details': {
                'invoices': len(invoices),
                'avg_invoice': total_revenue / len(invoices) if invoices else 0,
            },
            'icon': 'fa-dollar-sign',
            'color': 'success',
            'trend': self._calculate_trend('revenue', total_revenue)
        }
    
    def _get_new_patients(self):
        """Get new patients this month"""
        start_date = date.today().replace(day=1)
        new_patients = self.env['clinic.patient'].search([
            ('create_date', '>=', start_date.strftime('%Y-%m-%d'))
        ])
        
        return {
            'title': _('New Patients'),
            'value': len(new_patients),
            'period': _('This Month'),
            'icon': 'fa-user-plus',
            'color': 'info',
            'trend': self._calculate_trend('new_patients', len(new_patients))
        }
    
    def _get_no_show_rate(self):
        """Calculate no-show rate for the month"""
        start_date = date.today().replace(day=1)
        appointments = self.env['clinic.appointment'].search([
            ('start', '>=', start_date.strftime('%Y-%m-%d')),
            ('start', '<=', fields.Date.today().strftime('%Y-%m-%d')),
            ('state', 'in', ['done', 'no_show'])
        ])
        
        total = len(appointments)
        no_shows = len(appointments.filtered(lambda a: a.state == 'no_show'))
        rate = (no_shows / total * 100) if total > 0 else 0
        
        return {
            'title': _('No-Show Rate'),
            'value': f"{rate:.1f}%",
            'details': {
                'no_shows': no_shows,
                'total': total,
            },
            'icon': 'fa-user-times',
            'color': 'warning' if rate > 10 else 'success',
            'threshold_warning': rate > 10,
        }
    
    def _get_avg_wait_time(self):
        """Calculate average wait time for today

        Note: waiting_time field needs to be added to clinic.appointment model
        or this KPI should be disabled until the field exists.
        For now, returning placeholder data.
        """
        today = fields.Date.today()
        appointments = self.env['clinic.appointment'].search([
            ('start', '>=', today.strftime('%Y-%m-%d 00:00:00')),
            ('start', '<=', today.strftime('%Y-%m-%d 23:59:59'))
        ])

        # TODO: Implement waiting_time field or calculate from check-in time
        # For now, return N/A since waiting_time field doesn't exist
        avg_wait_minutes = 0

        return {
            'title': _('Avg Wait Time'),
            'value': 'N/A' if not appointments else f"0 min",
            'icon': 'fa-clock',
            'color': 'secondary',
            'threshold_warning': False,
            'note': 'Waiting time tracking not yet implemented'
        }
    
    def _get_claim_status(self):
        """Get insurance claim status summary"""
        claims = self.env['clinic.insurance.claim'].search([
            ('create_date', '>=', (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))
        ])
        
        return {
            'title': _('Claims Status'),
            'total': len(claims),
            'details': {
                'submitted': len(claims.filtered(lambda c: c.state == 'submitted')),
                'approved': len(claims.filtered(lambda c: c.state == 'approved')),
                'paid': len(claims.filtered(lambda c: c.state == 'paid')),
                'rejected': len(claims.filtered(lambda c: c.state == 'rejected')),
            },
            'icon': 'fa-file-invoice',
            'color': 'primary',
        }
    
    def _get_top_procedures(self):
        """Get top 5 procedures this month"""
        start_date = date.today().replace(day=1)
        
        # SQL query for performance
        self.env.cr.execute("""
            SELECT
                s.name as procedure_name,
                COUNT(*) as count,
                SUM(asl.subtotal) as revenue
            FROM clinic_appointment_service_line asl
            JOIN clinic_service s ON asl.service_id = s.id
            JOIN clinic_appointment a ON asl.appointment_id = a.id
            JOIN calendar_event ce ON ce.id = a.calendar_event_id
            WHERE ce.start >= %s
                AND a.state = 'done'
            GROUP BY s.id, s.name
            ORDER BY count DESC
            LIMIT 5
        """, (start_date,))
        
        procedures = self.env.cr.fetchall()
        
        return {
            'title': _('Top Procedures'),
            'procedures': [
                {
                    'name': p[0],
                    'count': p[1],
                    'revenue': p[2] or 0
                } for p in procedures
            ],
            'icon': 'fa-procedures',
            'color': 'info',
        }
    
    def _get_staff_utilization(self):
        """Calculate staff utilization rate"""
        today = fields.Date.today()
        staff_members = self.env['clinic.staff'].search([
            ('is_practitioner', '=', True),
            ('active', '=', True)
        ])
        
        utilization_data = []
        for staff in staff_members:
            # Get today's appointments
            appointments = self.env['clinic.appointment'].search([
                ('staff_id', '=', staff.id),
                ('start', '>=', today.strftime('%Y-%m-%d 00:00:00')),
                ('start', '<=', today.strftime('%Y-%m-%d 23:59:59')),
                ('state', 'in', ['confirmed', 'arrived', 'in_progress', 'done'])
            ])
            
            # Calculate utilization (assuming 8 hour work day)
            total_hours = sum(appointments.mapped('duration'))
            utilization = (total_hours / 8) * 100 if total_hours else 0
            
            utilization_data.append({
                'name': staff.name,
                'utilization': min(utilization, 100),
                'appointments': len(appointments),
                'hours': total_hours
            })
        
        return {
            'title': _('Staff Utilization'),
            'staff': sorted(utilization_data, key=lambda x: x['utilization'], reverse=True)[:5],
            'icon': 'fa-user-md',
            'color': 'success',
        }
    
    def _calculate_trend(self, metric, current_value):
        """Calculate trend compared to previous period"""
        # This would compare with previous period
        # For now, return sample data
        return {
            'direction': 'up',  # up, down, stable
            'percentage': 12.5,
            'previous_value': current_value * 0.875
        }
    
    @api.model
    def get_appointment_timeline(self):
        """Get appointment timeline for today"""
        today = fields.Date.today()
        appointments = self.env['clinic.appointment'].search([
            ('start', '>=', today.strftime('%Y-%m-%d 00:00:00')),
            ('start', '<=', today.strftime('%Y-%m-%d 23:59:59'))
        ], order='start')

        timeline = []
        for appointment in appointments:
            timeline.append({
                'time': appointment.start.strftime('%H:%M'),
                'patient': appointment.patient_id.name,
                'doctor': appointment.staff_id.name if appointment.staff_id else 'TBD',
                'service': appointment.service_type,
                'state': appointment.state,
                'state_color': self._get_state_color(appointment.state),
            })

        return timeline
    
    def _get_state_color(self, state):
        """Get color for appointment state"""
        colors = {
            'draft': 'secondary',
            'confirmed': 'info',
            'arrived': 'primary',
            'in_progress': 'warning',
            'done': 'success',
            'no_show': 'danger',
            'cancelled': 'dark',
        }
        return colors.get(state, 'secondary')
    
    @api.model
    def get_revenue_chart_data(self, period='month'):
        """Get revenue chart data"""
        if period == 'week':
            days = 7
        elif period == 'month':
            days = 30
        elif period == 'year':
            days = 365
        else:
            days = 30
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Get daily revenue
        self.env.cr.execute("""
            SELECT 
                DATE(invoice_date) as date,
                SUM(amount_total) as revenue
            FROM account_move
            WHERE move_type = 'out_invoice'
                AND state = 'posted'
                AND invoice_date >= %s
                AND invoice_date <= %s
                AND appointment_id IS NOT NULL
            GROUP BY DATE(invoice_date)
            ORDER BY date
        """, (start_date, end_date))
        
        data = self.env.cr.fetchall()
        
        return {
            'labels': [d[0].strftime('%b %d') for d in data],
            'datasets': [{
                'label': 'Revenue',
                'data': [float(d[1]) for d in data],
                'borderColor': 'rgb(75, 192, 192)',
                'tension': 0.1
            }]
        }
    
    @api.model
    def send_daily_report(self):
        """Send daily KPI report via email"""
        users = self.env['res.users'].search([
            ('groups_id', 'in', self.env.ref('clinic_kpis.group_clinic_kpi_manager').id)
        ])
        
        for user in users:
            dashboard_data = self.get_dashboard_data()
            
            # Prepare email
            template = self.env.ref('clinic_kpis.email_daily_kpi_report', raise_if_not_found=False)
            if template:
                template.with_context(kpi_data=dashboard_data).send_mail(
                    user.partner_id.id,
                    force_send=True
                )