# -*- coding: utf-8 -*-
{
    'name': "Clinic Base",
    'version': '19.0.1.0.0',
    'category': 'Services',
    'summary': 'Base module with core utilities for clinic system',
    'sequence': 1,

    'description': """
Clinic Base Module
==================
Core utilities and base functionality for the clinic management system.

Features:
---------
* Audit logging system
* Batch processing utilities
* Cache management
* Data validation framework
* Common utilities and helpers
* System configuration
    """,

    'author': "Clinic System",
    'license': 'LGPL-3',
    'website': "https://www.clinicsystem.com",

    'depends': [
        'base',
        'mail',
        'account',
        'product',
        'resource',
    ],

    'data': [
        # Security
        'security/base_security.xml',
        'security/ir.model.access.csv',

        # Views
        'views/audit_log_views.xml',
        'views/menu_views.xml',

        # Wizards
        'wizard/data_import_wizard_views.xml',
        'wizard/batch_operation_wizard_views.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}