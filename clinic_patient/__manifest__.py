# -*- coding: utf-8 -*-
{
    'name': "Clinic Patient Management",
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Patient',
    'summary': 'Comprehensive patient management system for medical and dental clinics',
    'sequence': 1,
    
    'description': """
Clinic Patient Management
=========================
Core patient management module for the clinic system.

Features:
---------
* Complete patient records with demographics
* Medical and dental history tracking
* Insurance information management
* Family members and emergency contacts
* Document management and attachments
* Portal access for patients
* GDPR-compliant data handling
    """,
    
    'author': "Clinic System",
    'license': 'LGPL-3',
    'website': "https://www.clinicsystem.com",
    
    'depends': [
        'base',
        'mail',
        'contacts',
        'portal',
        'clinic_staff',  # Required for security rules using user.staff_id
    ],
    
    'data': [
        # Security
        'security/patient_security.xml',
        'security/ir.model.access.csv',
        'security/patient_record_rules.xml',

        # Data
        'data/patient_sequence.xml',
        
        # Views (load after models are fully initialized)
        'views/patient_views.xml',
        'views/menu_views.xml',
    ],
    
    
    
    'installable': True,
    'application': False,
    'auto_install': False,
}