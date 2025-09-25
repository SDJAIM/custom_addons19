# -*- coding: utf-8 -*-
{
    'name': "Clinic Telemedicine Integration",
    'version': '19.0.1.1.0',
    'category': 'Healthcare/Telemedicine',
    'summary': 'Telemedicine and video consultation integration',
    'sequence': 12,
    
    'description': """
Clinic Telemedicine Integration
================================
Complete telemedicine solution for remote consultations.

Features:
---------
* Video consultation scheduling
* Meeting link generation
* Zoom/Google Meet/Jitsi integration
* Waiting room functionality
* Screen sharing support
* Chat during consultation
* Recording capabilities
* E-prescription after consultation
* Digital consent forms
* Payment integration
* Calendar synchronization
* Email/SMS notifications
* Patient portal access
* Technical support chat
* Post-consultation follow-up
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
        'clinic_prescription',
    ],
    
    'data': [
        # Security
        'security/telemed_security.xml',
        'security/ir.model.access.csv',

        # Configuration Data
        'data/telemed_config_data.xml',
        'data/telemed_data.xml',

        # Views
        'views/telemed_settings_views.xml',
        'views/telemed_session_views.xml',
        'views/telemed_config_views.xml',
        'views/appointment_telemed_views.xml',
        'views/menu_views.xml',
    ],
    
    'installable': True,
    'application': False,
    'auto_install': False,
}