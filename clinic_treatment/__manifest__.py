# -*- coding: utf-8 -*-
{
    'name': "Clinic Treatment Management",
    'version': '19.0.1.1.0',
    'category': 'Services',
    'summary': 'Complete treatment plans, procedures, and clinical notes management with confidentiality',
    'sequence': 4,
    
    'description': """
Clinic Treatment Management
===========================
Comprehensive treatment and clinical notes management system.

Features:
---------
* Treatment plan creation and templates
* Multi-stage treatment workflows
* Procedure catalog and tracking
* Clinical notes with confidentiality levels
* Treatment history and outcomes
* Progress tracking and milestones
* Cost estimation and tracking
* Treatment protocols and guidelines
* Consent forms management
* Before/after documentation
* Treatment outcome analytics
    """,
    
    'author': "Clinic System",
    'license': 'LGPL-3',
    'website': "https://www.clinicsystem.com",
    
    'depends': [
        'base',
        'mail',
        'clinic_patient',
        'clinic_staff',
        'clinic_appointment_core',
    ],
    
    'data': [
        # Security
        'security/treatment_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/treatment_sequence.xml',
        'data/procedure_categories.xml',
        'data/treatment_templates.xml',
        
        # Views
        'views/treatment_plan_views.xml',
        'views/treatment_procedure_views.xml',
        'views/clinical_note_views.xml',
        'views/treatment_template_views.xml',
        'views/procedure_category_views.xml',
        'views/menu_views.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}