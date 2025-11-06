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
        """Initialize the SQL view for revenue analytics

        TODO: This is a minimal placeholder view.
        Many fields reference non-existent tables/columns and need to be corrected.
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        # Minimal empty view - TODO: Implement proper analytics when field structure is confirmed
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    1 AS id,
                    CURRENT_DATE AS date,
                    NULL::varchar AS week,
                    NULL::varchar AS month,
                    NULL::varchar AS quarter,
                    2025 AS year,
                    1 AS day_of_week,
                    FALSE AS is_weekend,
                    0::numeric AS total_revenue,
                    0::numeric AS service_revenue,
                    0::numeric AS product_revenue,
                    0::numeric AS insurance_revenue,
                    0::numeric AS cash_revenue,
                    0 AS invoice_count,
                    0::numeric AS avg_invoice_amount,
                    0 AS paid_invoices,
                    0 AS unpaid_invoices,
                    0 AS overdue_invoices,
                    0 AS payment_count,
                    0::numeric AS total_payments,
                    0::numeric AS avg_payment_amount,
                    0::numeric AS payment_processing_time,
                    0 AS service_count,
                    0 AS unique_services,
                    NULL::varchar AS most_profitable_service,
                    NULL::integer AS branch_id,
                    NULL::varchar AS department,
                    0 AS doctor_count,
                    0::numeric AS revenue_per_doctor,
                    0 AS patient_count,
                    0 AS new_patient_count,
                    0 AS returning_patient_count,
                    0::numeric AS revenue_per_patient,
                    0 AS claim_count,
                    0 AS approved_claims,
                    0 AS rejected_claims,
                    0::numeric AS claim_approval_rate
                WHERE FALSE
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