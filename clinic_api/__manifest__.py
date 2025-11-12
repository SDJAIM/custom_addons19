# -*- coding: utf-8 -*-
{
    'name': "Clinic REST API",
    'version': '19.0.1.0.0',
    'category': 'Services',
    'summary': 'REST API with JWT authentication for clinic system',
    'sequence': 9,
    
    'description': """
Clinic REST API Module
======================
Comprehensive REST API for external integrations.

Features:
---------
* JWT token authentication
* RESTful endpoints for all resources
* Patient management API
* Appointment booking API
* Prescription API
* Treatment records API
* Staff availability API
* Insurance verification API
* Rate limiting
* API key management
* Webhook support
* Audit logging
* Swagger documentation
    """,
    
    'author': "Clinic System",
    'license': 'LGPL-3',
    'website': "https://www.clinicsystem.com",
    
    'depends': [
        'base',
        'web',
        'clinic_patient',
        'clinic_staff',
        'clinic_appointment_core',
        'clinic_treatment',
        'clinic_prescription',
        'clinic_finance',
    ],
    
    'external_dependencies': {
        'python': ['PyJWT', 'cryptography'],
    },
    
    'data': [
        # Security
        'security/api_security.xml',
        'security/ir.model.access.csv',
    ],
    
    'installable': True,
    'application': False,
    'auto_install': False,
}