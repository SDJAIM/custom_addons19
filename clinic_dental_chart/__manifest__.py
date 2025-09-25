# -*- coding: utf-8 -*-
{
    'name': "Clinic Dental Chart",
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Dental',
    'summary': 'Interactive dental chart with per-tooth procedure tracking and history',
    'sequence': 7,
    
    'description': """
Clinic Dental Chart Module
==========================
Advanced dental charting system with interactive OWL components.

Features:
---------
* Interactive tooth chart with OWL components
* Per-tooth procedure tracking
* Tooth history timeline
* Multiple notation systems (Universal, Palmer, FDI)
* Color-coded tooth states
* Procedure templates
* Treatment planning on chart
* Periodontal charting
* X-ray attachment per tooth
* Mobile-responsive design
* Printable dental charts
* Quadrant filtering
* Undo/redo functionality
    """,
    
    'author': "Clinic System",
    'license': 'LGPL-3',
    'website': "https://www.clinicsystem.com",
    
    'depends': [
        'base',
        'mail',
        'web',
        'clinic_patient',
        'clinic_staff',
        'clinic_appointment_core',
        'clinic_treatment',
    ],
    
    'data': [
        # Security
        'security/dental_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/tooth_data.xml',
        'data/dental_procedures.xml',
        'data/tooth_conditions.xml',
        
        # Views
        'views/dental_chart_views.xml',
        'views/tooth_history_views.xml',
        'views/periodontal_chart_views.xml',
        'views/dental_procedure_views.xml',
        'views/menu_views.xml',
        
        # Reports
        'reports/dental_chart_report.xml',
    ],
    
    'assets': {
        'web.assets_backend': [
            'clinic_dental_chart/static/src/scss/dental_chart.scss',
            'clinic_dental_chart/static/src/js/dental_chart_widget.js',
            'clinic_dental_chart/static/src/js/tooth_component.js',
            'clinic_dental_chart/static/src/xml/dental_chart_templates.xml',
        ],
    },
    
    'installable': True,
    'application': False,
    'auto_install': False,
}