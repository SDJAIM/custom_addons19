# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from psycopg2 import sql
from datetime import datetime, date, timedelta


class RevenueAnalytics(models.Model):
    _name = 'clinic.revenue.analytics'
    _description = 'Revenue Analytics'
    _auto = False  # This is a SQL view
    _order = 'date desc'

    # Date dimensions
    date = fields.Date(string='Date', readonly=True)
    week = fields.Char(string='Week', readonly=True)
    month = fields.Char(string='Month', readonly=True)
    quarter = fields.Char(string='Quarter', readonly=True)
    year = fields.Integer(string='Year', readonly=True)
    day_of_week = fields.Integer(string='Day of Week', readonly=True)
    is_weekend = fields.Boolean(string='Is Weekend', readonly=True)

    # Revenue metrics
    total_revenue = fields.Float(string='Total Revenue', readonly=True)
    service_revenue = fields.Float(string='Service Revenue', readonly=True)
    product_revenue = fields.Float(string='Product Revenue', readonly=True)
    insurance_revenue = fields.Float(string='Insurance Revenue', readonly=True)
    cash_revenue = fields.Float(string='Cash Revenue', readonly=True)

    # Invoice metrics
    invoice_count = fields.Integer(string='Invoice Count', readonly=True)
    avg_invoice_amount = fields.Float(string='Avg Invoice Amount', readonly=True)
    paid_invoices = fields.Integer(string='Paid Invoices', readonly=True)
    unpaid_invoices = fields.Integer(string='Unpaid Invoices', readonly=True)
    overdue_invoices = fields.Integer(string='Overdue Invoices', readonly=True)

    # Payment metrics
    payment_count = fields.Integer(string='Payment Count', readonly=True)
    total_payments = fields.Float(string='Total Payments', readonly=True)
    avg_payment_amount = fields.Float(string='Avg Payment Amount', readonly=True)
    payment_processing_time = fields.Float(string='Avg Processing Time (days)', readonly=True)

    # Service metrics
    service_count = fields.Integer(string='Services Performed', readonly=True)
    unique_services = fields.Integer(string='Unique Services', readonly=True)
    most_profitable_service = fields.Char(string='Most Profitable Service', readonly=True)

    # Department/Branch metrics
    branch_id = fields.Many2one('clinic.branch', string='Branch', readonly=True)
    department = fields.Char(string='Department', readonly=True)

    # Staff metrics
    doctor_count = fields.Integer(string='Active Doctors', readonly=True)
    revenue_per_doctor = fields.Float(string='Revenue per Doctor', readonly=True)

    # Patient metrics
    patient_count = fields.Integer(string='Patient Count', readonly=True)
    new_patient_count = fields.Integer(string='New Patients', readonly=True)
    returning_patient_count = fields.Integer(string='Returning Patients', readonly=True)
    revenue_per_patient = fields.Float(string='Revenue per Patient', readonly=True)

    # Claim metrics
    claim_count = fields.Integer(string='Insurance Claims', readonly=True)
    approved_claims = fields.Integer(string='Approved Claims', readonly=True)
    rejected_claims = fields.Integer(string='Rejected Claims', readonly=True)
    claim_approval_rate = fields.Float(string='Approval Rate %', readonly=True)

    @api.model
    def init(self):
        """Initialize the SQL view for revenue analytics"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH daily_revenue AS (
                    SELECT
                        DATE(am.invoice_date) AS date,
                        TO_CHAR(am.invoice_date, 'YYYY-WW') AS week,
                        TO_CHAR(am.invoice_date, 'YYYY-MM') AS month,
                        'Q' || TO_CHAR(am.invoice_date, 'Q') || ' ' || TO_CHAR(am.invoice_date, 'YYYY') AS quarter,
                        EXTRACT(YEAR FROM am.invoice_date) AS year,
                        EXTRACT(DOW FROM am.invoice_date) AS day_of_week,
                        CASE
                            WHEN EXTRACT(DOW FROM am.invoice_date) IN (0, 6) THEN TRUE
                            ELSE FALSE
                        END AS is_weekend,
                        ca.branch_id AS branch_id,
                        ca.department AS department,
                        COUNT(DISTINCT am.id) AS invoice_count,
                        SUM(am.amount_total) AS total_revenue,
                        AVG(am.amount_total) AS avg_invoice_amount,
                        COUNT(DISTINCT CASE WHEN am.payment_state = 'paid' THEN am.id END) AS paid_invoices,
                        COUNT(DISTINCT CASE WHEN am.payment_state != 'paid' THEN am.id END) AS unpaid_invoices,
                        COUNT(DISTINCT CASE WHEN am.payment_state != 'paid' AND am.invoice_date_due < CURRENT_DATE THEN am.id END) AS overdue_invoices,
                        COUNT(DISTINCT ca.patient_id) AS patient_count,
                        COUNT(DISTINCT ca.doctor_id) AS doctor_count,
                        SUM(CASE WHEN am.insurance_claim_id IS NOT NULL THEN am.amount_total ELSE 0 END) AS insurance_revenue,
                        SUM(CASE WHEN am.insurance_claim_id IS NULL THEN am.amount_total ELSE 0 END) AS cash_revenue
                    FROM account_move am
                    LEFT JOIN clinic_appointment ca ON ca.id = am.appointment_id
                    WHERE am.move_type = 'out_invoice'
                        AND am.state = 'posted'
                        AND am.invoice_date IS NOT NULL
                    GROUP BY
                        DATE(am.invoice_date),
                        TO_CHAR(am.invoice_date, 'YYYY-WW'),
                        TO_CHAR(am.invoice_date, 'YYYY-MM'),
                        quarter,
                        year,
                        day_of_week,
                        is_weekend,
                        ca.branch_id,
                        ca.department
                ),
                payment_metrics AS (
                    SELECT
                        DATE(ap.payment_date) AS date,
                        COUNT(*) AS payment_count,
                        SUM(ap.amount) AS total_payments,
                        AVG(ap.amount) AS avg_payment_amount,
                        AVG(DATE_PART('day', ap.payment_date - am.invoice_date)) AS payment_processing_time
                    FROM account_payment ap
                    JOIN account_move am ON am.id = ap.move_id
                    WHERE ap.payment_type = 'inbound'
                        AND ap.state = 'posted'
                    GROUP BY DATE(ap.payment_date)
                ),
                service_metrics AS (
                    SELECT
                        DATE(ca.appointment_date) AS date,
                        COUNT(DISTINCT asl.service_id) AS unique_services,
                        COUNT(asl.id) AS service_count,
                        SUM(asl.subtotal) AS service_revenue,
                        (
                            SELECT s.name
                            FROM clinic_appointment_service_line asl2
                            JOIN clinic_service s ON s.id = asl2.service_id
                            WHERE DATE(ca2.appointment_date) = DATE(ca.appointment_date)
                            GROUP BY s.id, s.name
                            ORDER BY SUM(asl2.subtotal) DESC
                            LIMIT 1
                        ) AS most_profitable_service
                    FROM clinic_appointment ca
                    JOIN clinic_appointment_service_line asl ON asl.appointment_id = ca.id
                    JOIN clinic_appointment ca2 ON ca2.id = asl.appointment_id
                    WHERE ca.state = 'done'
                    GROUP BY DATE(ca.appointment_date)
                ),
                claim_metrics AS (
                    SELECT
                        DATE(cic.submission_date) AS date,
                        COUNT(*) AS claim_count,
                        COUNT(CASE WHEN cic.state = 'approved' THEN 1 END) AS approved_claims,
                        COUNT(CASE WHEN cic.state = 'rejected' THEN 1 END) AS rejected_claims,
                        CASE
                            WHEN COUNT(*) > 0 THEN
                                (COUNT(CASE WHEN cic.state = 'approved' THEN 1 END) * 100.0 / COUNT(*))
                            ELSE 0
                        END AS claim_approval_rate
                    FROM clinic_insurance_claim cic
                    WHERE cic.submission_date IS NOT NULL
                    GROUP BY DATE(cic.submission_date)
                ),
                new_patients AS (
                    SELECT
                        DATE(p.create_date) AS date,
                        COUNT(*) AS new_patient_count
                    FROM clinic_patient p
                    GROUP BY DATE(p.create_date)
                )
                SELECT
                    row_number() OVER () AS id,
                    dr.date,
                    dr.week,
                    dr.month,
                    dr.quarter,
                    dr.year,
                    dr.day_of_week,
                    dr.is_weekend,
                    COALESCE(dr.total_revenue, 0) AS total_revenue,
                    COALESCE(sm.service_revenue, 0) AS service_revenue,
                    COALESCE(dr.total_revenue - COALESCE(sm.service_revenue, 0), 0) AS product_revenue,
                    COALESCE(dr.insurance_revenue, 0) AS insurance_revenue,
                    COALESCE(dr.cash_revenue, 0) AS cash_revenue,
                    COALESCE(dr.invoice_count, 0) AS invoice_count,
                    COALESCE(dr.avg_invoice_amount, 0) AS avg_invoice_amount,
                    COALESCE(dr.paid_invoices, 0) AS paid_invoices,
                    COALESCE(dr.unpaid_invoices, 0) AS unpaid_invoices,
                    COALESCE(dr.overdue_invoices, 0) AS overdue_invoices,
                    COALESCE(pm.payment_count, 0) AS payment_count,
                    COALESCE(pm.total_payments, 0) AS total_payments,
                    COALESCE(pm.avg_payment_amount, 0) AS avg_payment_amount,
                    COALESCE(pm.payment_processing_time, 0) AS payment_processing_time,
                    COALESCE(sm.service_count, 0) AS service_count,
                    COALESCE(sm.unique_services, 0) AS unique_services,
                    sm.most_profitable_service,
                    dr.branch_id,
                    dr.department,
                    COALESCE(dr.doctor_count, 0) AS doctor_count,
                    CASE
                        WHEN dr.doctor_count > 0 THEN dr.total_revenue / dr.doctor_count
                        ELSE 0
                    END AS revenue_per_doctor,
                    COALESCE(dr.patient_count, 0) AS patient_count,
                    COALESCE(np.new_patient_count, 0) AS new_patient_count,
                    COALESCE(dr.patient_count - COALESCE(np.new_patient_count, 0), 0) AS returning_patient_count,
                    CASE
                        WHEN dr.patient_count > 0 THEN dr.total_revenue / dr.patient_count
                        ELSE 0
                    END AS revenue_per_patient,
                    COALESCE(cm.claim_count, 0) AS claim_count,
                    COALESCE(cm.approved_claims, 0) AS approved_claims,
                    COALESCE(cm.rejected_claims, 0) AS rejected_claims,
                    COALESCE(cm.claim_approval_rate, 0) AS claim_approval_rate
                FROM daily_revenue dr
                LEFT JOIN payment_metrics pm ON pm.date = dr.date
                LEFT JOIN service_metrics sm ON sm.date = dr.date
                LEFT JOIN claim_metrics cm ON cm.date = dr.date
                LEFT JOIN new_patients np ON np.date = dr.date
            )
        """ % self._table)

    @api.model
    def get_revenue_summary(self, date_from=None, date_to=None, branch_id=None):
        """Get revenue summary for a date range"""
        domain = []
        if date_from:
            domain.append(('date', '>=', date_from))
        if date_to:
            domain.append(('date', '<=', date_to))
        if branch_id:
            domain.append(('branch_id', '=', branch_id))

        analytics = self.search(domain)

        if not analytics:
            return {
                'total_revenue': 0,
                'invoice_count': 0,
                'patient_count': 0,
                'avg_invoice_amount': 0,
            }

        return {
            'total_revenue': sum(analytics.mapped('total_revenue')),
            'service_revenue': sum(analytics.mapped('service_revenue')),
            'product_revenue': sum(analytics.mapped('product_revenue')),
            'insurance_revenue': sum(analytics.mapped('insurance_revenue')),
            'cash_revenue': sum(analytics.mapped('cash_revenue')),
            'invoice_count': sum(analytics.mapped('invoice_count')),
            'paid_invoices': sum(analytics.mapped('paid_invoices')),
            'unpaid_invoices': sum(analytics.mapped('unpaid_invoices')),
            'overdue_invoices': sum(analytics.mapped('overdue_invoices')),
            'patient_count': sum(analytics.mapped('patient_count')),
            'new_patient_count': sum(analytics.mapped('new_patient_count')),
            'service_count': sum(analytics.mapped('service_count')),
            'avg_invoice_amount': sum(analytics.mapped('total_revenue')) / sum(analytics.mapped('invoice_count')) if sum(analytics.mapped('invoice_count')) else 0,
            'payment_processing_time': sum(analytics.mapped('payment_processing_time')) / len(analytics) if analytics else 0,
            'claim_approval_rate': sum(analytics.mapped('approved_claims')) / sum(analytics.mapped('claim_count')) * 100 if sum(analytics.mapped('claim_count')) else 0,
        }

    @api.model
    def get_revenue_trend(self, period='month', limit=12):
        """Get revenue trend data for charts"""
        # Whitelist valid column names to prevent SQL injection
        valid_periods = {
            'day': 'date',
            'week': 'week',
            'month': 'month',
            'quarter': 'quarter',
            'year': 'year'
        }

        if period not in valid_periods:
            period = 'month'

        group_by = valid_periods[period]

        if period == 'day':
            date_format = '%b %d'
        elif period == 'week':
            date_format = 'Week %W'
        elif period == 'month':
            date_format = '%b %Y'
        elif period == 'quarter':
            date_format = 'Q%q %Y'
        else:
            date_format = '%Y'

        # Use SQL identifier to safely include column name
        query = """
            SELECT
                {} AS period,
                SUM(total_revenue) AS revenue,
                SUM(invoice_count) AS invoices,
                SUM(patient_count) AS patients
            FROM {}
            GROUP BY {}
            ORDER BY MIN(date) DESC
            LIMIT %s
        """.format(
            sql.Identifier(group_by).as_string(self.env.cr),
            sql.Identifier(self._table).as_string(self.env.cr),
            sql.Identifier(group_by).as_string(self.env.cr)
        )

        self.env.cr.execute(query, (limit,))

        results = self.env.cr.fetchall()
        return {
            'labels': [r[0] for r in reversed(results)],
            'revenue': [float(r[1] or 0) for r in reversed(results)],
            'invoices': [r[2] or 0 for r in reversed(results)],
            'patients': [r[3] or 0 for r in reversed(results)],
        }