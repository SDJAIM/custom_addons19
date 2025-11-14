# -*- coding: utf-8 -*-
{
    'name': "Clinic Appointment Core",
    'version': '19.0.1.2.0',
    'category': 'Services',
    'summary': 'Advanced appointment management system with slot booking and multi-view support',
    'sequence': 3,
    
    'description': """
Clinic Appointment Management Core
===================================
Comprehensive appointment management system for healthcare facilities.

Features:
---------
* Multi-state appointment workflow
* Slot-based booking with availability checking
* No-overlap constraints
* Multiple view types (Kanban, Calendar, Gantt)
* Service types (Medical, Dental, Telemedicine)
* Urgency levels and triage
* Follow-up appointment linking
* Insurance authorization tracking
* Automatic reminders and notifications
* Room and resource allocation
* Waiting list management
* Appointment templates
    """,
    
    'author': "Clinic System",
    'license': 'LGPL-3',
    'website': "https://www.clinicsystem.com",
    
    'depends': [
        'base',
        'mail',
        'sms',  # TASK-F1-006: Use Odoo CE's built-in SMS module
        'calendar',  # Now using calendar.event as base
        'resource',  # For resource management (rooms, staff)
        'website',  # For online booking (Phase 2)
        'clinic_patient',
        'clinic_staff',
    ],
    
    'data': [
        # Security - MUST load first
        'security/appointment_security.xml',
        'security/ir.model.access.csv',
        'security/appointment_record_rules.xml',

        # Data - Email templates MUST load before stages
        'data/appointment_sequence.xml',
        'data/email_templates.xml',
        'data/sms_templates.xml',  # TASK-F1-006: SMS templates using Odoo CE
        'data/appointment_types.xml',
        'data/appointment_stages.xml',
        'data/cron_jobs.xml',

        # Wizards
        'wizards/appointment_reschedule_views.xml',
        'wizards/follow_up_wizard_views.xml',

        # Views - Questionnaire MUST load before main appointment views
        'views/questionnaire_views.xml',

        # Views - Backend
        'views/appointment_views.xml',
        'views/appointment_type_views.xml',
        'views/appointment_reminder_config_views.xml',  # TASK-F1-003
        'views/waiting_list_views.xml',
        'views/slot_views.xml',
        'views/menu_views.xml',
        'views/slot_metrics_views.xml',  # TASK-F1-012 - Loaded after menus
        'views/appointment_team_views.xml',  # TASK-F2-001 - Loaded after menus
        'views/share_flexible_times_wizard_views.xml',  # TASK-F3-001 - Loaded after menus
        'views/sms_config_views.xml',
        'views/appointment_dashboard_views.xml',  # TASK-F3-004

        # Views - Website (Phase 2)
        'views/website/booking_templates.xml',
        'views/website/manage_templates.xml',
        'views/website/social_sharing_templates.xml',  # TASK-F3-005
    ],

    'assets': {
        'web.assets_backend': [
            'clinic_appointment_core/static/src/js/appointment_dashboard.js',
            'clinic_appointment_core/static/src/css/appointment_dashboard.css',
        ],
        'web.assets_qweb': [
            'clinic_appointment_core/static/src/xml/appointment_dashboard.xml',
        ],
    },

    'images': ['static/description/icon.png'],

    'installable': True,
    'application': False,
    'auto_install': False,
}