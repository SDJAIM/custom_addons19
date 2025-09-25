# -*- coding: utf-8 -*-
{
    'name': "Clinic Appointment Core",
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Appointments',
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
        'calendar',  # Now using calendar.event as base
        'resource',  # For resource management (rooms, staff)
        'clinic_patient',
        'clinic_staff',
    ],
    
    'data': [
        # Security
        'security/appointment_security.xml',
        'security/ir.model.access.csv',
        'security/appointment_record_rules.xml',

        # Data
        'data/appointment_sequence.xml',
        'data/appointment_types.xml',
        'data/appointment_stages.xml',
        
        # Wizards
        'wizards/appointment_reschedule_views.xml',
        'wizards/follow_up_wizard_views.xml',
        
        # Views
        'views/appointment_views.xml',
        'views/appointment_type_views.xml',
        'views/waiting_list_views.xml',
        'views/slot_views.xml',
        'views/menu_views.xml',
    ],
    
    
    'installable': True,
    'application': False,
    'auto_install': False,
}