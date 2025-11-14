# -*- coding: utf-8 -*-
{
    'name': "Clinic Telemedicine Integration",
    'version': '19.0.1.1.0',
    'category': 'Services',
    'summary': 'Telemedicine and video consultation integration',
    'sequence': 12,
    
    'description': """
Clinic Telemedicine Integration
================================
Complete telemedicine solution using Odoo Discuss WebRTC for video consultations.

Features:
---------
* Native Odoo Discuss video calling integration
* Google Meet integration (TASK-F3-002) - OAuth2 + automatic link creation
* One-click video consultation setup from appointments
* Automatic Discuss channel creation for patient + doctor
* Real-time video + audio + chat in one interface
* Session management with states (scheduled, waiting, in progress, completed)
* Email invitations and reminders
* Appointment integration with service type 'Telemedicine'
* Recording capabilities (when supported by Discuss)
* Secure, HIPAA-compliant video calls (when properly configured)
* Patient portal access
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
        'security/google_meet_security.xml',  # TASK-F3-002
        'security/ir.model.access.csv',

        # Configuration Data
        'data/telemed_config_data.xml',
        'data/google_meet_params.xml',  # TASK-F3-002

        # Views
        'views/telemed_session_views.xml',
        'views/telemed_session_google_views.xml',  # TASK-F3-002
        'views/telemed_recording_views.xml',
        'views/telemed_settings_views.xml',
        'views/appointment_telemed_views.xml',
        'views/google_meet_config_views.xml',  # TASK-F3-002
        'views/google_oauth_templates.xml',  # TASK-F3-002
    ],

    'external_dependencies': {
        'python': ['requests'],  # TASK-F3-002: Required for Google API calls
    },
    
    'installable': True,
    'application': False,
    'auto_install': False,
}