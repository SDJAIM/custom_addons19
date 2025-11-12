{
    'name': '🏥 Clinic System Complete',
    'version': '19.0.1.1.0',
    'category': 'Services',
    'summary': 'Complete Clinic Management System - Auto-installs all modules',
    'author': 'Clinic System',
    'website': 'https://github.com/clinic-system',
    'license': 'LGPL-3',
    'description': """
    Clinic System - Complete Installation
    =====================================

    This module automatically installs the complete clinic management system
    with all modules in the correct dependency order.

    Modules Included:
    ----------------
    ✅ Patient Management
    ✅ Staff & HR Management
    ✅ Appointment System
    ✅ Treatment Management
    ✅ Prescription System
    ✅ Financial Management
    ✅ Dental Chart
    ✅ Web Portal & Online Booking
    ✅ REST API
    ✅ WhatsApp Integration
    ✅ Telemedicine
    ✅ Analytics & KPIs

    Installation Notes:
    ------------------
    - All modules will be installed automatically
    - Dependencies are handled in the correct order
    - No manual intervention required
    """,

    'depends': [
        # Odoo Core Dependencies
        'base',
        'web',
        'mail',
        'contacts',
        'portal',
        'calendar',
        'resource',
        'hr',
        'account',
        'sale',
        'stock',  # Includes lot expiration when "Expiration Dates" enabled in settings
        'product',
        'website',
        'website_payment',
        'sms',
        'board',

        # Clinic Modules - In Dependency Order
        'clinic_base',         # Base utilities must be first
        'clinic_staff',        # Staff must be before patient for security rules
        'clinic_patient',      # Patient management
        'clinic_appointment_core',  # Appointments
        'clinic_treatment',    # Treatments
        'clinic_prescription', # Prescriptions (requires Expiration Dates in Inventory settings)
        'clinic_dental_chart', # Dental
        'clinic_finance',      # Finance
        'clinic_appointment_web', # Web booking
        'clinic_integrations_telemed',  # Telemedicine
        'clinic_integrations_whatsapp', # WhatsApp
        'clinic_api',         # REST API
        'clinic_kpis',        # Analytics
    ],

    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'data/clinic_installer_data.xml',
        'views/clinic_installer_simple.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'clinic_installer/static/src/css/installer.css',
        ],
    },

    'external_dependencies': {
        'python': ['PyJWT', 'cryptography', 'phonenumbers', 'requests'],
    },

    'images': ['static/description/icon.png'],
    'installable': True,
    'auto_install': False,
    'application': True,
    'sequence': 1,
    'post_load': 'post_load_hook',
    'post_init_hook': 'post_init_hook',
}