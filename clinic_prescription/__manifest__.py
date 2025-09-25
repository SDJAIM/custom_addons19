# -*- coding: utf-8 -*-
{
    'name': "Clinic Prescription Management",
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Prescription',
    'summary': 'Advanced prescription management with workflow, FEFO stock tracking, and QWeb printing',
    'sequence': 5,
    
    'description': """
Clinic Prescription Management
==============================
Comprehensive prescription and medication management system.

Features:
---------
* Prescription workflow (draft → confirmed → sent → dispensed)
* Medication database with dosage forms
* Routes of administration management
* Dose units and frequency configuration
* FEFO (First Expired, First Out) stock management
* Drug interaction warnings
* Allergy checking
* Prescription templates
* QWeb prescription layouts for printing/email
* E-prescription support
* Refill management
* Controlled substance tracking
* Pharmacy integration ready
    """,
    
    'author': "Clinic System",
    'license': 'LGPL-3',
    'website': "https://www.clinicsystem.com",
    
    'depends': [
        'base',
        'mail',
        'stock',
        'product',
        'clinic_patient',
        'clinic_staff',
        'clinic_appointment_core',
        'clinic_treatment',
    ],
    
    'data': [
        # Security
        'security/prescription_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/product_category_data.xml',
        'data/prescription_sequence.xml',
        'data/medication_routes.xml',
        'data/medication_forms.xml',
        'data/dose_units.xml',
        'data/frequency_data.xml',
        'data/cron_jobs.xml',

        # Reports
        'reports/prescription_report.xml',
        'reports/prescription_templates.xml',

        # Views
        'views/prescription_views.xml',
        'views/medication_views.xml',
        'views/medication_stock_views.xml',
        'views/prescription_template_views.xml',
        'views/medication_route_views.xml',
        'views/prescription_wizard_views.xml',
        'views/menu_views.xml',
    ],
    
    'assets': {
        'web.assets_backend': [
            'clinic_prescription/static/src/scss/prescription.scss',
            'clinic_prescription/static/src/js/prescription_widget.js',
        ],
    },
    
    'installable': True,
    'application': False,
    'auto_install': False,
}