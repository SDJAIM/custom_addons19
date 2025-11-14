# -*- coding: utf-8 -*-
{
    'name': "Clinic Staff Management",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Comprehensive staff and practitioner management for medical and dental clinics',
    'sequence': 2,
    
    'description': """
Clinic Staff Management
=======================
Complete staff management module for healthcare facilities.

Features:
---------
* Multiple staff types (Doctor, Dentist, Nurse, Receptionist, etc.)
* Specialization and qualification tracking
* Working hours and availability management
* Consultation fee configuration
* Multi-branch support
* Performance metrics and KPIs
* Staff scheduling and calendar integration
* Document management for certifications
* Leave management integration
    """,
    
    'author': "Clinic System",
    'license': 'LGPL-3',
    'website': "https://www.clinicsystem.com",
    
    'depends': [
        'base',
        'clinic_base',  # Added for utilities
        'mail',
        'hr',
        'calendar',
        'resource',
    ],
    
    'data': [
        # Security
        'security/staff_security.xml',
        'security/ir.model.access.csv',
        'security/staff_record_rules.xml',

        # Data
        'data/staff_sequence.xml',
        'data/specialization_data.xml',
        
        # Views
        'views/staff_views.xml',
        'views/room_views.xml',
        'views/specialization_views.xml',
        'views/schedule_views.xml',
        'views/menu_views.xml',  # Menu structure must be loaded after actions

        # Wizards - TASK-F3-006
        'wizards/resource_calendar_migration_views.xml',
    ],
    
    
    'installable': True,
    'application': False,
    'auto_install': False,
}