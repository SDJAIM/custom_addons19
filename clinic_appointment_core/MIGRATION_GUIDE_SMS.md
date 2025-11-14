# SMS Manager Migration Guide (TASK-F1-006)

## Overview
This guide documents the migration from the custom SMS manager to Odoo Community Edition's built-in `sms` module.

## Changes Made

### 1. Module Dependencies
**File**: `__manifest__.py`
- Added `'sms'` to dependencies list

### 2. SMS Templates
**File**: `data/sms_templates.xml` (NEW)
- Created SMS templates using `sms.template` model:
  - `sms_template_appointment_confirmation`
  - `sms_template_appointment_reminder`
  - `sms_template_appointment_cancelled`
  - `sms_template_appointment_rescheduled`
  - `sms_template_waiting_list_notification`

### 3. Appointment Model
**File**: `models/appointment.py`
- Updated `_send_confirmation_sms()` to use `_message_sms_with_template()`
- Updated `_send_reminder_sms()` to use `_message_sms_with_template()`
- Updated `_send_cancellation_sms()` to use `_message_sms_with_template()`
- Updated `_send_reminder_by_sms()` to support `sms_template_id` from reminder config

### 4. Waiting List Model
**File**: `models/waiting_list.py`
- Updated `_send_sms_notification()` to use `_message_sms_with_template()`
- Integrated with `sms_template_waiting_list_notification` template

### 5. SMS Manager (Deprecated)
**File**: `models/sms_manager.py`
- Converted to compatibility wrapper with deprecation warnings
- All methods now delegate to Odoo CE's SMS system
- Maintains backward compatibility for existing code
- Will be removed in future major version

### 6. Security
**File**: `security/ir.model.access.csv`
- Added read/write access to `sms.template` for appointment user groups
- Added read/write access to `sms.sms` for appointment user groups

## Benefits

### ✅ Native Integration
- Uses Odoo's built-in SMS infrastructure
- No need to maintain custom SMS gateway code
- Leverages Odoo's SMS provider abstraction

### ✅ Better Template Management
- SMS templates can be edited from UI
- Supports Jinja2 templating with full object context
- Multi-language support built-in

### ✅ Improved Monitoring
- SMS queue visible in Odoo's Discuss menu
- Delivery status tracking out of the box
- Automatic retry for failed messages

### ✅ Reduced Code Complexity
- Removed ~300 lines of custom SMS gateway code
- No need to manage Twilio/AWS SNS credentials separately
- Uses Odoo's IAP (In-App Purchase) SMS credits

## Migration Steps for Production

### 1. Update Module
```bash
python odoo-bin -u clinic_appointment_core -d your_database
```

### 2. Configure SMS Provider
Navigate to: **Settings → Technical → SMS → SMS Providers**

Options:
- **Odoo IAP SMS** (recommended for CE): Built-in, pay-as-you-go
- **SMS Twilio**: If you have existing Twilio account
- **Custom SMS Gateway**: Configure custom provider

### 3. Test SMS Sending
1. Create a test appointment
2. Trigger confirmation SMS
3. Check SMS queue: **Discuss → SMS Messages**
4. Verify delivery status

### 4. Migrate Existing SMS Logs (Optional)
If you need to preserve historical SMS data:
```python
# Run this script via Odoo shell
# python odoo-bin shell -d your_database -c your_config.conf

# Link old SMS logs to new sms.sms records if needed
old_logs = env['clinic.appointment.sms.log'].search([])
for log in old_logs:
    if log.message_id:
        # Check if corresponding sms.sms record exists
        sms_record = env['sms.sms'].search([('uuid', '=', log.message_id)], limit=1)
        if sms_record:
            log.write({'sms_sms_id': sms_record.id})
```

### 5. Monitor Deprecation Warnings
Check logs for any usage of deprecated methods:
```bash
grep "DEPRECATED: clinic.appointment.sms.manager" odoo.log
```

Update any custom modules or integrations that use deprecated methods.

## API Changes

### Before (Custom SMS Manager)
```python
# Old way - DEPRECATED
sms_manager = self.env['clinic.appointment.sms.manager'].sudo()
result = sms_manager.send_appointment_reminder_sms(appointment)
```

### After (Odoo CE SMS)
```python
# New way - RECOMMENDED
result = appointment._send_reminder_sms()

# Or using template directly
template = self.env.ref('clinic_appointment_core.sms_template_appointment_reminder')
appointment._message_sms_with_template(
    template=template,
    partner_ids=appointment.patient_id.partner_id.ids,
    number_field='patient_phone',
)
```

### Direct SMS Sending (No Template)
```python
# Create and send SMS directly
sms = self.env['sms.sms'].create({
    'number': '+1234567890',
    'body': 'Your custom message',
})
sms.send()
```

## Configuration

### SMS Templates Location
**Settings → Technical → SMS → SMS Templates**

You can customize any template by:
1. Finding the template by name
2. Editing the "Body" field (supports Jinja2)
3. Testing with the "Preview" button

### Available Template Variables
In SMS templates, you have access to:
- `object`: The appointment record
- `object.patient_id`: Patient record
- `object.staff_id`: Staff record
- `object.appointment_type_id`: Appointment type
- `object.start`: Appointment datetime
- Any computed field or related field

Example:
```jinja2
Hello {{ object.patient_id.name }},

Your appointment on {{ object.start.strftime('%B %d at %H:%M') }}
with {{ object.staff_id.name }} is confirmed.

Ref: {{ object.appointment_number }}
```

## Troubleshooting

### SMS Not Sending
1. Check SMS provider configuration: **Settings → Technical → SMS**
2. Verify phone number format (E.164 format: +1234567890)
3. Check SMS queue: **Discuss → SMS Messages**
4. Review logs for errors: `grep "sms" odoo.log`

### Template Not Found
If you see "Template not found" errors:
1. Verify module is fully upgraded: `python odoo-bin -u clinic_appointment_core`
2. Check data file loaded: **Settings → Technical → External IDs** → Filter by "sms_template"
3. Reload data: `python odoo-bin -u clinic_appointment_core --init`

### Phone Number Issues
Odoo's SMS system requires E.164 format:
- ✅ Correct: `+12025551234`
- ❌ Wrong: `(202) 555-1234`
- ❌ Wrong: `2025551234`

The system will attempt to sanitize phone numbers automatically.

## Backward Compatibility

The old `clinic.appointment.sms.manager` methods still work but will log deprecation warnings:
- `send_sms()`
- `send_appointment_reminder_sms()`
- `send_appointment_confirmation_sms()`
- `send_appointment_cancelled_sms()`

These will be removed in version 20.0.

## Future Enhancements

Planned for future versions:
- [ ] SMS delivery webhooks integration
- [ ] SMS campaign management for appointment reminders
- [ ] SMS-based appointment confirmation (reply YES/NO)
- [ ] Multi-language SMS templates
- [ ] SMS cost tracking and budgeting

## Related Tasks
- TASK-F1-009: WhatsApp Templates (uses similar pattern)
- TASK-F1-010: WhatsApp PDF Attachments
- TASK-F1-003: Multiple Reminders (already supports sms_template_id)

## References
- [Odoo SMS Documentation](https://www.odoo.com/documentation/19.0/developer/reference/backend/mixins.html#sms-management)
- [Odoo IAP SMS](https://www.odoo.com/documentation/19.0/applications/general/in_app_purchase.html#sms)
- [SMS Template Fields](https://www.odoo.com/documentation/19.0/developer/reference/backend/mixins.html#odoo.addons.sms.models.sms_template.SmsTemplate)
