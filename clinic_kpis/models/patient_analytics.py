# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from datetime import datetime, timedelta


class PatientAnalytics(models.Model):
    _name = 'clinic.patient.analytics'
    _description = 'Patient Analytics'
    _auto = False  # This is a SQL view
    _order = 'registration_date desc'

    # Patient fields
    patient_id = fields.Many2one('clinic.patient', string='Patient', readonly=True)
    patient_name = fields.Char(string='Patient Name', readonly=True)
    patient_code = fields.Char(string='Patient Code', readonly=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender', readonly=True)
    age = fields.Integer(string='Age', readonly=True)
    age_group = fields.Selection([
        ('child', '0-12'),
        ('teen', '13-17'),
        ('young_adult', '18-35'),
        ('adult', '36-55'),
        ('senior', '56+')
    ], string='Age Group', readonly=True)

    # Registration & Activity
    registration_date = fields.Date(string='Registration Date', readonly=True)
    registration_month = fields.Char(string='Registration Month', readonly=True)
    registration_year = fields.Integer(string='Registration Year', readonly=True)
    first_visit_date = fields.Date(string='First Visit', readonly=True)
    last_visit_date = fields.Date(string='Last Visit', readonly=True)
    days_since_last_visit = fields.Integer(string='Days Since Last Visit', readonly=True)

    # Visit Statistics
    total_visits = fields.Integer(string='Total Visits', readonly=True)
    completed_visits = fields.Integer(string='Completed Visits', readonly=True)
    cancelled_visits = fields.Integer(string='Cancelled Visits', readonly=True)
    no_show_visits = fields.Integer(string='No Show Visits', readonly=True)

    # Financial Metrics
    total_revenue = fields.Float(string='Total Revenue', readonly=True)
    avg_revenue_per_visit = fields.Float(string='Avg Revenue/Visit', readonly=True)
    outstanding_balance = fields.Float(string='Outstanding Balance', readonly=True)
    insurance_coverage = fields.Boolean(string='Has Insurance', readonly=True)

    # Treatment Metrics
    total_procedures = fields.Integer(string='Total Procedures', readonly=True)
    total_prescriptions = fields.Integer(string='Total Prescriptions', readonly=True)
    chronic_conditions = fields.Integer(string='Chronic Conditions', readonly=True)

    # Patient Category
    patient_category = fields.Selection([
        ('new', 'New Patient'),
        ('regular', 'Regular Patient'),
        ('vip', 'VIP Patient'),
        ('inactive', 'Inactive Patient')
    ], string='Category', readonly=True)

    # Retention Metrics
    retention_rate = fields.Float(string='Retention Rate %', readonly=True)
    visit_frequency = fields.Selection([
        ('frequent', 'Frequent (Monthly)'),
        ('regular', 'Regular (Quarterly)'),
        ('occasional', 'Occasional (Yearly)'),
        ('inactive', 'Inactive')
    ], string='Visit Frequency', readonly=True)

    @api.model
    def init(self):
        """Initialize the SQL view for patient analytics

        TODO: This is a minimal placeholder view.
        Many fields reference non-existent tables/columns and need to be corrected.
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        # Minimal empty view - TODO: Implement proper analytics when field structure is confirmed
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    1 AS id,
                    NULL::integer AS patient_id,
                    NULL::varchar AS patient_name,
                    NULL::varchar AS patient_code,
                    NULL::varchar AS gender,
                    NULL::integer AS age,
                    NULL::varchar AS age_group,
                    CURRENT_DATE AS registration_date,
                    NULL::varchar AS registration_month,
                    NULL::integer AS registration_year,
                    NULL::date AS first_visit_date,
                    NULL::date AS last_visit_date,
                    NULL::integer AS days_since_last_visit,
                    0 AS total_visits,
                    0 AS completed_visits,
                    0 AS cancelled_visits,
                    0 AS no_show_visits,
                    0::numeric AS total_revenue,
                    0::numeric AS avg_revenue_per_visit,
                    0::numeric AS outstanding_balance,
                    FALSE AS insurance_coverage,
                    0 AS total_procedures,
                    0 AS total_prescriptions,
                    0 AS chronic_conditions,
                    NULL::varchar AS patient_category,
                    0::numeric AS retention_rate,
                    NULL::varchar AS visit_frequency
                WHERE FALSE
            )
        """ % self._table)

    @api.model
    def get_patient_statistics(self, patient_id=None):
        """Get detailed statistics for a specific patient or all patients"""
        domain = []
        if patient_id:
            domain.append(('patient_id', '=', patient_id))

        analytics = self.search(domain)

        if patient_id and analytics:
            # Return single patient statistics
            return {
                'patient_name': analytics.patient_name,
                'total_visits': analytics.total_visits,
                'completed_visits': analytics.completed_visits,
                'no_show_rate': (analytics.no_show_visits / analytics.total_visits * 100) if analytics.total_visits else 0,
                'total_revenue': analytics.total_revenue,
                'avg_revenue_per_visit': analytics.avg_revenue_per_visit,
                'outstanding_balance': analytics.outstanding_balance,
                'days_since_last_visit': analytics.days_since_last_visit,
                'patient_category': analytics.patient_category,
                'retention_rate': analytics.retention_rate,
            }
        else:
            # Return aggregated statistics
            total_patients = len(analytics)
            active_patients = len(analytics.filtered(lambda a: a.patient_category != 'inactive'))
            new_patients_month = len(analytics.filtered(lambda a: a.registration_month == datetime.now().strftime('%Y-%m')))

            return {
                'total_patients': total_patients,
                'active_patients': active_patients,
                'new_patients_month': new_patients_month,
                'avg_visits_per_patient': sum(analytics.mapped('total_visits')) / total_patients if total_patients else 0,
                'total_revenue': sum(analytics.mapped('total_revenue')),
                'avg_revenue_per_patient': sum(analytics.mapped('total_revenue')) / total_patients if total_patients else 0,
                'patients_with_insurance': len(analytics.filtered('insurance_coverage')),
                'vip_patients': len(analytics.filtered(lambda a: a.patient_category == 'vip')),
            }