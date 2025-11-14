# -*- coding: utf-8 -*-
{
    'name': "Clinic WhatsApp Integration",
    'version': '19.0.1.3.0',
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
        'clinic_finance',  # Required for invoice_whatsapp_integration.py
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
        'data/whatsapp_escalation_cron.xml',  # Fase 5.1
        'data/whatsapp_autoresponder_defaults.xml',  # Fase 5.3

        # Views - Phase 1: Core views with actions (no menu dependencies)
        'views/whatsapp_settings_views_v2.xml',
        'views/whatsapp_config_views.xml',
        'views/whatsapp_message_views.xml',
        'views/whatsapp_template_views.xml',
        #         'views/whatsapp_template_interactive_views.xml',  # TASK-F3-003
        'views/patient_whatsapp_views.xml',
        'views/appointment_reminder_views.xml',  # Extend appointment reminder views

        # Menus - Load parent menus after actions are defined
        'views/menu_views.xml',

        # Views - Phase 2: Views with child menu items (need parent menus)
        'views/whatsapp_webhook_event_views.xml',
        'views/whatsapp_thread_views.xml',
        'views/patient_whatsapp_indicators.xml',  # Fase 3.2
        'views/whatsapp_dashboard_views.xml',  # Fase 3.5

        # Wizards
        'wizard/whatsapp_message_wizard_views.xml',  # Fase 3.4

        # App Integrations (Fase 4)
        'views/appointment_whatsapp_views.xml',  # Fase 4.1
        'views/prescription_whatsapp_views.xml',  # Fase 4.2
        'views/invoice_whatsapp_views.xml',  # Fase 4.3

        # Operator Management (Fase 5.5)
        'views/whatsapp_operator_assignment_views.xml',  # Fase 5.5
        'views/whatsapp_autoresponder_views.xml',  # Fase 5.5
    ],
    
    'installable': True,
    'application': False,
    'auto_install': False,
}