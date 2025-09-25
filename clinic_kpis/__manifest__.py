# -*- coding: utf-8 -*-
{
    'name': "Clinic KPIs & Analytics Dashboard",
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Analytics',
    'summary': 'KPI dashboard component - Install via Clinic System Installer',
    'sequence': 99,
    
    'description': """
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
    """,
    
    'author': "Clinic System",
    'license': 'LGPL-3',
    'website': "https://www.clinicsystem.com",
    
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

        # Data
        # 'data/kpi_data.xml',  # File not found - needs to be created
        # 'data/dashboard_data.xml',  # File not found - needs to be created

        # Views
        # 'views/kpi_dashboard_views.xml',  # File not found - needs to be created
        # 'views/appointment_analytics_views.xml',  # File not found - needs to be created
        # 'views/revenue_analytics_views.xml',  # File not found - needs to be created
        # 'views/patient_analytics_views.xml',  # File not found - needs to be created
        # 'views/staff_performance_views.xml',  # File not found - needs to be created
        # 'views/menu_views.xml',  # File not found - needs to be created

        # Reports
        # 'reports/kpi_report_templates.xml',  # File not found - needs to be created
        # 'reports/monthly_report.xml',  # File not found - needs to be created
    ],

    'assets': {
        'web.assets_backend': [
            # 'clinic_kpis/static/src/scss/dashboard.scss',  # File not found - needs to be created
            # 'clinic_kpis/static/src/js/dashboard_widget.js',  # File not found - needs to be created
            # 'clinic_kpis/static/src/js/kpi_renderer.js',  # File not found - needs to be created
            # 'clinic_kpis/static/src/xml/dashboard_templates.xml',  # File not found - needs to be created
        ],
    },
    
    'installable': True,
    'application': False,  # Component module, not standalone app
    'auto_install': False,
}