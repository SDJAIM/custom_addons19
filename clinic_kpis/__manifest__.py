# -*- coding: utf-8 -*-
{
    'name': 'Clinic KPIs & Analytics Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': 'KPI dashboard component - Install via Clinic System Installer',
    'sequence': 99,

    'description': '''
Clinic KPIs & Analytics Dashboard
==================================
Real-time analytics and KPI tracking for clinic operations.

Features:
---------
* Interactive KPI dashboard
* Today's appointments widget
* No-show rate tracking
* Revenue analytics by doctor/procedure
* Patient acquisition metrics
* Treatment success rates
* Insurance claim statistics
* Staff utilization reports
* Patient satisfaction scores
* Appointment booking trends
* Top procedures analysis
* Claims status tracker
* Financial performance metrics
* Scheduled email reports
* Custom dashboard widgets
* Data export capabilities
    ''',

    'author': 'Clinic System',
    'license': 'LGPL-3',
    'website': 'https://www.clinicsystem.com',

    'depends': [
        'base',
        'board',  # Community Edition dashboard functionality
        'clinic_patient',
        'clinic_staff',
        'clinic_appointment_core',
        'clinic_treatment',
        'clinic_finance',
        'clinic_prescription',
    ],

    'data': [
        # Security
        'security/kpi_security.xml',
        'security/ir.model.access.csv',

        # Views
        'views/dashboard_views.xml',
    ],

    'assets': {},

    'installable': True,
    'application': False,
    'auto_install': False,
}