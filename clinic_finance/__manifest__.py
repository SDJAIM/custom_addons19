# -*- coding: utf-8 -*-
{
    'name': "Clinic Finance Management",
    'version': '19.0.1.0.0',
    'category': 'Healthcare/Finance',
    'summary': 'Comprehensive billing, insurance claims, and financial management for clinics',
    'sequence': 6,
    
    'description': """
Clinic Finance Management
=========================
Complete financial management system for healthcare clinics.

Features:
---------
* Auto-invoicing on appointment completion
* Insurance policy management
* Insurance claim workflow (draft → submitted → approved → paid → rejected)
* Prior authorization tracking
* Co-payment and deductible calculation
* Payment plan management
* Revenue analytics by doctor/procedure
* Claim reconciliation tools
* Financial reports and KPIs
* Integration with accounting
    """,
    
    'author': "Clinic System",
    'license': 'LGPL-3',
    'website': "https://www.clinicsystem.com",
    
    'depends': [
        'base',
        'mail',
        'account',
        'sale',
        'clinic_patient',
        'clinic_staff',
        'clinic_appointment_core',
        'clinic_treatment',
        'clinic_prescription',
    ],
    
    'data': [
        # Security
        'security/finance_security.xml',
        'security/ir.model.access.csv',

        # Data
        'data/finance_sequence.xml',
        'data/payment_terms.xml',
        'data/insurance_data.xml',

        # Views
        'views/invoice_views.xml',
    ],
    
    'installable': True,
    'application': False,
    'auto_install': False,
}