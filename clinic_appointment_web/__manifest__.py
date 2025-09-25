# -*- coding: utf-8 -*-
{
    'name': "Clinic Appointment Web Booking",
    'version': '19.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Online appointment booking system with slot selection and insurance verification',
    'sequence': 8,
    
    'description': """
Clinic Appointment Web Booking
===============================
Advanced online booking system for clinic appointments.

Features:
---------
* Step-by-step booking wizard
* Service selection with descriptions
* Real-time slot availability
* Next-week booking rule enforcement
* Staff availability checking
* Insurance information collection
* Document upload for insurance
* Pay now vs insurance selection
* Secretary approval workflow
* Patient portal integration
* Appointment rescheduling
* Email/SMS confirmations
* Calendar integration
* Mobile-responsive design
    """,
    
    'author': "Clinic System",
    'license': 'LGPL-3',
    'website': "https://www.clinicsystem.com",
    
    'depends': [
        'website',
        'portal',
        'website_payment',
        'clinic_patient',
        'clinic_staff',
        'clinic_appointment_core',
        'clinic_finance',
    ],
    
    'data': [
        # Security
        'security/booking_security.xml',
        'security/ir.model.access.csv',
        
        # Data
        'data/booking_data.xml',
        'data/email_templates.xml',
        
        # Views - Backend
        'views/booking_config_views.xml',
        'views/booking_request_views.xml',
        'views/menu_views.xml',
        
        # Views - Website
        'views/website_templates.xml',
        'views/booking_templates.xml',
        'views/portal_templates.xml',
        'views/confirmation_templates.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}