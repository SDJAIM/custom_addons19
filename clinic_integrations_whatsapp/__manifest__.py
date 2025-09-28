# -*- coding: utf-8 -*-
{
    'name': "Clinic WhatsApp Integration",
    'version': '19.0.1.1.0',
    'category': 'Marketing',
    'summary': 'WhatsApp messaging integration for appointment reminders and notifications',
    'sequence': 10,
    
    'description': """
Clinic WhatsApp Integration
============================
WhatsApp Business API integration for clinic communications.

Features:
---------
* Opt-in consent management
* Appointment reminder messages
* Confirmation notifications
* Follow-up messages
* Lab result notifications
* Prescription reminders
* Two-way messaging support
* Message templates management
* Webhook handlers for replies
* Delivery status tracking
* Retry mechanism for failed messages
* Audit logging
* Patient timeline integration
* Bulk messaging campaigns
* Emergency broadcast system
    """,
    
    'author': "Clinic System",
    'license': 'LGPL-3',
    'website': "https://www.clinicsystem.com",
    
    'depends': [
        'base',
        'mail',
        'sms',
        'clinic_patient',
        'clinic_appointment_core',
        'clinic_prescription',
        'clinic_treatment',
    ],
    
    'external_dependencies': {
        'python': ['requests', 'phonenumbers'],
    },
    
    'data': [
        # Security
        'security/whatsapp_security.xml',
        'security/ir.model.access.csv',

        # Configuration Data
        'data/whatsapp_config_data.xml',
        'data/message_templates.xml',
        'data/whatsapp_cron.xml',

        # Views
        'views/whatsapp_settings_views.xml',
        'views/whatsapp_config_views.xml',
        'views/whatsapp_message_views.xml',
        'views/whatsapp_template_views.xml',
        'views/patient_whatsapp_views.xml',
        'views/menu_views.xml',

        # Wizards
        'wizards/send_whatsapp_wizard_views.xml',
        'wizards/broadcast_wizard_views.xml',
    ],
    
    'installable': True,
    'application': False,
    'auto_install': False,
}