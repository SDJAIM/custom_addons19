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
        """Initialize the SQL view for patient analytics"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    p.id AS patient_id,
                    p.name AS patient_name,
                    p.patient_code AS patient_code,
                    p.gender AS gender,
                    DATE_PART('year', AGE(p.birth_date)) AS age,
                    CASE
                        WHEN DATE_PART('year', AGE(p.birth_date)) <= 12 THEN 'child'
                        WHEN DATE_PART('year', AGE(p.birth_date)) <= 17 THEN 'teen'
                        WHEN DATE_PART('year', AGE(p.birth_date)) <= 35 THEN 'young_adult'
                        WHEN DATE_PART('year', AGE(p.birth_date)) <= 55 THEN 'adult'
                        ELSE 'senior'
                    END AS age_group,
                    DATE(p.create_date) AS registration_date,
                    TO_CHAR(p.create_date, 'YYYY-MM') AS registration_month,
                    EXTRACT(YEAR FROM p.create_date) AS registration_year,
                    (
                        SELECT MIN(appointment_date)
                        FROM clinic_appointment
                        WHERE patient_id = p.id AND state = 'done'
                    ) AS first_visit_date,
                    (
                        SELECT MAX(appointment_date)
                        FROM clinic_appointment
                        WHERE patient_id = p.id AND state = 'done'
                    ) AS last_visit_date,
                    CASE
                        WHEN (SELECT MAX(appointment_date) FROM clinic_appointment WHERE patient_id = p.id AND state = 'done') IS NOT NULL
                        THEN DATE_PART('day', NOW() - (SELECT MAX(appointment_date) FROM clinic_appointment WHERE patient_id = p.id AND state = 'done'))
                        ELSE NULL
                    END AS days_since_last_visit,
                    (
                        SELECT COUNT(*)
                        FROM clinic_appointment
                        WHERE patient_id = p.id
                    ) AS total_visits,
                    (
                        SELECT COUNT(*)
                        FROM clinic_appointment
                        WHERE patient_id = p.id AND state = 'done'
                    ) AS completed_visits,
                    (
                        SELECT COUNT(*)
                        FROM clinic_appointment
                        WHERE patient_id = p.id AND state = 'cancelled'
                    ) AS cancelled_visits,
                    (
                        SELECT COUNT(*)
                        FROM clinic_appointment
                        WHERE patient_id = p.id AND state = 'no_show'
                    ) AS no_show_visits,
                    COALESCE((
                        SELECT SUM(am.amount_total)
                        FROM account_move am
                        JOIN clinic_appointment ca ON ca.id = am.appointment_id
                        WHERE ca.patient_id = p.id AND am.state = 'posted' AND am.move_type = 'out_invoice'
                    ), 0) AS total_revenue,
                    CASE
                        WHEN (SELECT COUNT(*) FROM clinic_appointment WHERE patient_id = p.id AND state = 'done') > 0
                        THEN COALESCE((
                            SELECT SUM(am.amount_total)
                            FROM account_move am
                            JOIN clinic_appointment ca ON ca.id = am.appointment_id
                            WHERE ca.patient_id = p.id AND am.state = 'posted' AND am.move_type = 'out_invoice'
                        ), 0) / (SELECT COUNT(*) FROM clinic_appointment WHERE patient_id = p.id AND state = 'done')
                        ELSE 0
                    END AS avg_revenue_per_visit,
                    COALESCE((
                        SELECT SUM(am.amount_residual)
                        FROM account_move am
                        JOIN clinic_appointment ca ON ca.id = am.appointment_id
                        WHERE ca.patient_id = p.id AND am.state = 'posted' AND am.move_type = 'out_invoice'
                    ), 0) AS outstanding_balance,
                    CASE
                        WHEN EXISTS(SELECT 1 FROM clinic_patient_insurance WHERE patient_id = p.id AND active = TRUE)
                        THEN TRUE
                        ELSE FALSE
                    END AS insurance_coverage,
                    (
                        SELECT COUNT(DISTINCT asl.service_id)
                        FROM clinic_appointment_service_line asl
                        JOIN clinic_appointment ca ON ca.id = asl.appointment_id
                        WHERE ca.patient_id = p.id AND ca.state = 'done'
                    ) AS total_procedures,
                    (
                        SELECT COUNT(*)
                        FROM clinic_prescription pr
                        WHERE pr.patient_id = p.id AND pr.state = 'confirmed'
                    ) AS total_prescriptions,
                    (
                        SELECT COUNT(*)
                        FROM clinic_patient_condition
                        WHERE patient_id = p.id AND is_chronic = TRUE
                    ) AS chronic_conditions,
                    CASE
                        WHEN DATE_PART('day', NOW() - p.create_date) <= 30 THEN 'new'
                        WHEN (SELECT COUNT(*) FROM clinic_appointment WHERE patient_id = p.id AND state = 'done') >= 10 THEN 'vip'
                        WHEN DATE_PART('day', NOW() - COALESCE((SELECT MAX(appointment_date) FROM clinic_appointment WHERE patient_id = p.id AND state = 'done'), p.create_date)) > 180 THEN 'inactive'
                        ELSE 'regular'
                    END AS patient_category,
                    CASE
                        WHEN (SELECT COUNT(*) FROM clinic_appointment WHERE patient_id = p.id) > 0
                        THEN ((SELECT COUNT(*) FROM clinic_appointment WHERE patient_id = p.id AND state = 'done') * 100.0 /
                              (SELECT COUNT(*) FROM clinic_appointment WHERE patient_id = p.id))
                        ELSE 0
                    END AS retention_rate,
                    CASE
                        WHEN (SELECT COUNT(*) FROM clinic_appointment WHERE patient_id = p.id AND state = 'done' AND appointment_date >= NOW() - INTERVAL '30 days') > 0 THEN 'frequent'
                        WHEN (SELECT COUNT(*) FROM clinic_appointment WHERE patient_id = p.id AND state = 'done' AND appointment_date >= NOW() - INTERVAL '90 days') > 0 THEN 'regular'
                        WHEN (SELECT COUNT(*) FROM clinic_appointment WHERE patient_id = p.id AND state = 'done' AND appointment_date >= NOW() - INTERVAL '365 days') > 0 THEN 'occasional'
                        ELSE 'inactive'
                    END AS visit_frequency
                FROM clinic_patient p
                WHERE p.active = TRUE
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