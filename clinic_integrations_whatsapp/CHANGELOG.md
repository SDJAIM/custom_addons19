# CHANGELOG - clinic_integrations_whatsapp

## [19.0.1.1.0] - 2025-09-25

### Fixed
- Commented out references to non-existent files from `__manifest__.py`:
  - 2 missing data files (message_templates.xml, whatsapp_cron.xml)
  - 5 missing view files (whatsapp_config_views, whatsapp_message_views, whatsapp_template_views, patient_whatsapp_views, menu_views)
  - 2 missing wizard files (send_whatsapp_wizard_views, broadcast_wizard_views)

### Verified
- No _sql_constraints found (compliant with Odoo 19)
- No commented code blocks requiring action
- Security files exist and properly configured
- Data file exists (whatsapp_config_data.xml)
- One view file exists (whatsapp_settings_views.xml)
- Module dependencies correct (includes sms, mail, clinic modules)
- External dependencies: requests, phonenumbers