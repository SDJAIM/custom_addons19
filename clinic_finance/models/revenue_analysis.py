# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from datetime import datetime, date, timedelta


class RevenueAnalysis(models.Model):
    _name = 'clinic.revenue.analysis'
    _description = 'Revenue Analysis'
    _auto = False
    _order = 'date desc'

    # Date fields
    date = fields.Date(string='Date', readonly=True)
    year = fields.Integer(string='Year', readonly=True)
    month = fields.Integer(string='Month', readonly=True)
    quarter = fields.Integer(string='Quarter', readonly=True)
    week = fields.Integer(string='Week', readonly=True)

    # Branch and Department
    branch_id = fields.Many2one('clinic.branch', string='Branch', readonly=True)
    department = fields.Char(string='Department', readonly=True)

    # Doctor/Staff
    doctor_id = fields.Many2one('clinic.staff', string='Doctor', readonly=True)
    doctor_specialty = fields.Char(string='Specialty', readonly=True)

    # Patient
    patient_id = fields.Many2one('clinic.patient', string='Patient', readonly=True)
    patient_type = fields.Selection([
        ('new', 'New'),
        ('returning', 'Returning'),
        ('vip', 'VIP')
    ], string='Patient Type', readonly=True)

    # Service
    service_id = fields.Many2one('clinic.service', string='Service', readonly=True)
    service_category = fields.Char(string='Service Category', readonly=True)

    # Financial Metrics
    gross_revenue = fields.Float(string='Gross Revenue', readonly=True)
    discount_amount = fields.Float(string='Discount', readonly=True)
    net_revenue = fields.Float(string='Net Revenue', readonly=True)
    insurance_revenue = fields.Float(string='Insurance Revenue', readonly=True)
    cash_revenue = fields.Float(string='Cash Revenue', readonly=True)

    # Cost Analysis
    cost = fields.Float(string='Cost', readonly=True)
    profit = fields.Float(string='Profit', readonly=True)
    profit_margin = fields.Float(string='Profit Margin %', readonly=True)

    # Payment
    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue')
    ], string='Payment Status', readonly=True)

    days_to_payment = fields.Integer(string='Days to Payment', readonly=True)

    # Appointment
    appointment_id = fields.Many2one('clinic.appointment', string='Appointment', readonly=True)
    appointment_type = fields.Char(string='Appointment Type', readonly=True)

    @api.model
    def init(self):
        """Create the SQL view for revenue analysis"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    DATE(am.invoice_date) AS date,
                    EXTRACT(YEAR FROM am.invoice_date) AS year,
                    EXTRACT(MONTH FROM am.invoice_date) AS month,
                    EXTRACT(QUARTER FROM am.invoice_date) AS quarter,
                    EXTRACT(WEEK FROM am.invoice_date) AS week,
                    ca.branch_id AS branch_id,
                    ca.department AS department,
                    ca.doctor_id AS doctor_id,
                    s.specialization_id AS doctor_specialty,
                    ca.patient_id AS patient_id,
                    CASE
                        WHEN p.create_date >= NOW() - INTERVAL '30 days' THEN 'new'
                        WHEN (
                            SELECT COUNT(*)
                            FROM clinic_appointment
                            WHERE patient_id = ca.patient_id
                        ) > 10 THEN 'vip'
                        ELSE 'returning'
                    END AS patient_type,
                    asl.service_id AS service_id,
                    cs.category AS service_category,
                    asl.subtotal AS gross_revenue,
                    asl.discount AS discount_amount,
                    asl.subtotal - COALESCE(asl.discount, 0) AS net_revenue,
                    COALESCE(asl.insurance_coverage, 0) AS insurance_revenue,
                    COALESCE(asl.patient_share, 0) AS cash_revenue,
                    COALESCE(asl.cost, 0) AS cost,
                    (asl.subtotal - COALESCE(asl.discount, 0) - COALESCE(asl.cost, 0)) AS profit,
                    CASE
                        WHEN asl.subtotal > 0 THEN
                            ((asl.subtotal - COALESCE(asl.discount, 0) - COALESCE(asl.cost, 0)) / asl.subtotal) * 100
                        ELSE 0
                    END AS profit_margin,
                    CASE
                        WHEN am.payment_state = 'paid' THEN 'paid'
                        WHEN am.payment_state = 'partial' THEN 'partial'
                        WHEN am.payment_state != 'paid' AND am.invoice_date_due < CURRENT_DATE THEN 'overdue'
                        ELSE 'not_paid'
                    END AS payment_state,
                    CASE
                        WHEN am.payment_state = 'paid' AND am.invoice_payment_date IS NOT NULL THEN
                            DATE_PART('day', am.invoice_payment_date - am.invoice_date)
                        ELSE NULL
                    END AS days_to_payment,
                    ca.id AS appointment_id,
                    ca.appointment_type AS appointment_type
                FROM account_move am
                LEFT JOIN clinic_appointment ca ON ca.id = am.appointment_id
                LEFT JOIN clinic_appointment_service_line asl ON asl.appointment_id = ca.id
                LEFT JOIN clinic_service cs ON cs.id = asl.service_id
                LEFT JOIN clinic_patient p ON p.id = ca.patient_id
                LEFT JOIN clinic_staff s ON s.id = ca.doctor_id
                WHERE am.move_type = 'out_invoice'
                    AND am.state = 'posted'
                    AND am.invoice_date IS NOT NULL
            )
        """ % self._table)

    @api.model
    def get_revenue_by_period(self, date_from, date_to, groupby='month'):
        """Get revenue analysis grouped by period"""
        group_field = {
            'day': 'date',
            'week': 'week',
            'month': 'month',
            'quarter': 'quarter',
            'year': 'year'
        }.get(groupby, 'month')

        domain = []
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))

        records = self.search(domain)

        # Group by period
        result = {}
        for record in records:
            period_key = getattr(record, group_field)
            if period_key not in result:
                result[period_key] = {
                    'gross_revenue': 0,
                    'net_revenue': 0,
                    'insurance_revenue': 0,
                    'cash_revenue': 0,
                    'profit': 0,
                    'count': 0
                }

            result[period_key]['gross_revenue'] += record.gross_revenue
            result[period_key]['net_revenue'] += record.net_revenue
            result[period_key]['insurance_revenue'] += record.insurance_revenue
            result[period_key]['cash_revenue'] += record.cash_revenue
            result[period_key]['profit'] += record.profit
            result[period_key]['count'] += 1

        return result

    @api.model
    def get_revenue_by_service(self, date_from=None, date_to=None, limit=10):
        """Get top revenue generating services using ORM"""
        domain = [('service_id', '!=', False)]
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))

        # Read all records matching the domain
        records = self.search_read(
            domain,
            ['service_id', 'net_revenue', 'profit', 'profit_margin']
        )

        # Group by service using Python
        service_data = {}
        for record in records:
            service_id = record['service_id'][0] if record['service_id'] else None
            if not service_id:
                continue

            if service_id not in service_data:
                service_data[service_id] = {
                    'service_id': service_id,
                    'service_name': record['service_id'][1] if record['service_id'] else '',
                    'total_revenue': 0.0,
                    'total_profit': 0.0,
                    'service_count': 0,
                    'profit_margins': []
                }

            service_data[service_id]['total_revenue'] += record.get('net_revenue', 0.0) or 0.0
            service_data[service_id]['total_profit'] += record.get('profit', 0.0) or 0.0
            service_data[service_id]['service_count'] += 1
            if record.get('profit_margin'):
                service_data[service_id]['profit_margins'].append(record['profit_margin'])

        # Calculate average margin and prepare results
        results = []
        for service_id, data in service_data.items():
            avg_margin = sum(data['profit_margins']) / len(data['profit_margins']) if data['profit_margins'] else 0.0
            results.append((
                data['service_id'],
                data['service_name'],
                data['total_revenue'],
                data['total_profit'],
                data['service_count'],
                avg_margin
            ))

        # Sort by total revenue and limit
        results.sort(key=lambda x: x[2], reverse=True)
        return results[:limit]

    @api.model
    def get_revenue_by_doctor(self, date_from=None, date_to=None):
        """Get revenue analysis by doctor"""
        domain = []
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))

        records = self.search(domain)

        # Group by doctor
        result = {}
        for record in records:
            if record.doctor_id:
                doctor_key = record.doctor_id.id
                if doctor_key not in result:
                    result[doctor_key] = {
                        'doctor_name': record.doctor_id.name,
                        'specialty': record.doctor_specialty,
                        'revenue': 0,
                        'profit': 0,
                        'patient_count': set(),
                        'appointment_count': 0
                    }

                result[doctor_key]['revenue'] += record.net_revenue
                result[doctor_key]['profit'] += record.profit
                result[doctor_key]['patient_count'].add(record.patient_id.id)
                result[doctor_key]['appointment_count'] += 1

        # Convert patient count sets to counts
        for doctor_data in result.values():
            doctor_data['patient_count'] = len(doctor_data['patient_count'])

        return result

    @api.model
    def get_payment_analysis(self, date_from=None, date_to=None):
        """Get payment status analysis"""
        domain = []
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))

        records = self.search(domain)

        analysis = {
            'total_invoiced': sum(records.mapped('net_revenue')),
            'total_paid': sum(records.filtered(lambda r: r.payment_state == 'paid').mapped('net_revenue')),
            'total_partial': sum(records.filtered(lambda r: r.payment_state == 'partial').mapped('net_revenue')),
            'total_unpaid': sum(records.filtered(lambda r: r.payment_state == 'not_paid').mapped('net_revenue')),
            'total_overdue': sum(records.filtered(lambda r: r.payment_state == 'overdue').mapped('net_revenue')),
            'avg_days_to_payment': sum(records.filtered('days_to_payment').mapped('days_to_payment')) / len(records.filtered('days_to_payment')) if records.filtered('days_to_payment') else 0,
            'payment_states': {
                'paid': len(records.filtered(lambda r: r.payment_state == 'paid')),
                'partial': len(records.filtered(lambda r: r.payment_state == 'partial')),
                'not_paid': len(records.filtered(lambda r: r.payment_state == 'not_paid')),
                'overdue': len(records.filtered(lambda r: r.payment_state == 'overdue')),
            }
        }

        return analysis