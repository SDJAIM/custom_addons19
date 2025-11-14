# WhatsApp Template Variable Substitution Guide (TASK-F1-009)

## Overview

This guide documents the WhatsApp template variable substitution system implemented in TASK-F1-009. The system allows dynamic content in WhatsApp templates using numbered placeholders like `{{1}}`, `{{2}}`, etc.

## Template Variable System

### Placeholder Format
WhatsApp Cloud API requires numbered placeholders in sequential order starting from `{{1}}`:

```
Hi {{1}}, your appointment is on {{2}} at {{3}} with {{4}}.
```

### Variable Substitution Process

1. **Template Definition**: Create template with placeholders
2. **Parameter Mapping**: Map appointment data to parameters
3. **Rendering**: Replace placeholders with actual values
4. **Validation**: Ensure sequential placeholders

## Implementation

### 1. Template Model (`whatsapp_template.py`)

#### Core Method: `render_template(**params)`

```python
template = self.env['clinic.whatsapp.template'].browse(1)
result = template.render_template(
    patient_name='John Doe',
    appointment_date='January 15, 2025',
    appointment_time='10:00 AM'
)
```

**Features:**
- Replaces `{{1}}`, `{{2}}`, etc. with provided parameters in order
- Handles different data types (datetime, int, float, str)
- Formats datetime objects automatically
- Converts None to empty string

#### Validation: `_validate_placeholders()`

Automatically validates that placeholders are:
- Sequential (no gaps)
- Starting from `{{1}}`
- No duplicates

```python
# ✅ Valid
"Hi {{1}}, appointment on {{2}} at {{3}}"

# ❌ Invalid - missing {{2}}
"Hi {{1}}, appointment on {{3}}"

# ❌ Invalid - not starting from 1
"Hi {{2}}, appointment on {{3}}"
```

#### Helper Method: `get_placeholder_count()`

Returns the maximum placeholder number in template:

```python
template.message_body = "Hi {{1}}, see you on {{2}} at {{3}}"
count = template.get_placeholder_count()  # Returns: 3
```

### 2. Appointment Integration (`appointment.py`)

#### Method: `_send_reminder_by_whatsapp(appointment, config)`

Sends WhatsApp reminder using configured template:

```python
# Called automatically by reminder cron
appointment._send_reminder_by_whatsapp(appointment, reminder_config)
```

**Process:**
1. Gets template from reminder config
2. Prepares parameters using `_get_whatsapp_template_params()`
3. Renders template with parameters
4. Creates WhatsApp message in queue
5. Returns message ID

#### Method: `_get_whatsapp_template_params(appointment)`

Maps appointment data to template parameters:

```python
params = {
    'patient_name': 'John Doe',           # {{1}}
    'appointment_date': 'January 15, 2025',  # {{2}}
    'appointment_time': '10:00 AM',          # {{3}}
    'doctor_name': 'Dr. Smith',              # {{4}}
    'appointment_type': 'General Checkup',   # {{5}}
    'location': 'Main Clinic',               # {{6}}
    'confirmation_number': 'APT-2025-001',   # {{7}}
    'booking_url': 'https://...',            # {{8}} (optional)
}
```

## Template Examples

### 1. Appointment Reminder (7 variables)

```
Template Name: appointment_reminder_v1
Placeholders: {{1}} through {{7}}

Body:
Hi {{1}}, reminder about your appointment on {{2}} at {{3}} with {{4}}.

Type: {{5}}
Location: {{6}}

Please arrive 15 minutes early. Reply CONFIRM or CANCEL.

Ref: {{7}}

Parameter Mapping:
{{1}} = patient_name
{{2}} = appointment_date
{{3}} = appointment_time
{{4}} = doctor_name
{{5}} = appointment_type
{{6}} = location
{{7}} = confirmation_number
```

### 2. Appointment Confirmation (7 variables)

```
Template Name: appointment_confirmation_v1

Body:
✅ Appointment Confirmed

Hello {{1}}, your appointment is confirmed for {{2}} at {{3}}.

Doctor: {{4}}
Type: {{5}}
Location: {{6}}

Confirmation #: {{7}}

We look forward to seeing you!

Parameter Mapping:
{{1}} = patient_name
{{2}} = appointment_date
{{3}} = appointment_time
{{4}} = doctor_name
{{5}} = appointment_type
{{6}} = location
{{7}} = confirmation_number
```

### 3. Simple Reminder (3 variables)

```
Template Name: simple_reminder_v1

Body:
Reminder: {{1}}, you have an appointment on {{2}} at {{3}}.

Please confirm your attendance.

Parameter Mapping:
{{1}} = patient_name
{{2}} = appointment_date
{{3}} = appointment_time
```

## Data Type Handling

### Datetime Formatting

```python
# Input: datetime(2025, 1, 15, 10, 30)
# Output: "2025-01-15 10:30"

appointment.start = datetime(2025, 1, 15, 14, 30)
params = {
    'appointment_date': appointment.start.strftime('%B %d, %Y'),  # "January 15, 2025"
    'appointment_time': appointment.start.strftime('%I:%M %p'),    # "02:30 PM"
}
```

### Number Formatting

```python
# Integer/Float automatically converted to string
params = {
    'count': 5,      # Becomes "5"
    'price': 49.99,  # Becomes "49.99"
}
```

### None Handling

```python
# None values become empty strings
params = {
    'optional_field': None,  # Becomes ""
}
```

## PHI Compliance

### ⚠️ CRITICAL: No PHI in Templates

WhatsApp is NOT HIPAA-compliant. Templates should:

✅ **ALLOWED:**
- Patient first name only
- Generic appointment details (date, time, location)
- Confirmation numbers
- Links to secure patient portal

❌ **PROHIBITED:**
- Last names or full names
- Medical conditions
- Lab results
- Diagnoses
- Medications by name
- Specific symptoms
- Insurance information

### Example: Compliant vs Non-Compliant

```
✅ COMPLIANT:
"Hi {{1}}, you have new information available in your portal."

❌ NON-COMPLIANT:
"Hi {{1}}, your diabetes test results show glucose at {{2}}."
```

The system automatically validates templates using `_compute_phi_compliant()` and rejects templates containing prohibited keywords.

## Configuration

### 1. Create Template

**Settings → WhatsApp → Templates → Create**

Fields:
- **Name**: Display name (e.g., "Appointment Reminder")
- **Template Name**: Meta Business Manager ID (e.g., "appointment_reminder_v1")
- **Template Type**: Category (appointment_reminder, confirmation, etc.)
- **Language Code**: ISO code (en, es, pt_BR, etc.)
- **Message Body**: Template with placeholders
- **Footer**: Optional footer text
- **Active**: Enable/disable template

### 2. Associate with Reminder Config

**Appointments → Configuration → Appointment Types → [Type] → Reminders Tab**

For each reminder:
- **Channel**: WhatsApp
- **WhatsApp Template**: Select template
- **Hours Before**: When to send (e.g., 24 hours)

### 3. Test Template Rendering

From Python shell:

```python
# Get template
template = env['clinic.whatsapp.template'].browse(1)

# Test rendering
result = template.render_template(
    patient_name='Test Patient',
    appointment_date='January 15, 2025',
    appointment_time='10:00 AM',
    doctor_name='Dr. Smith',
    appointment_type='Checkup',
    location='Main Clinic',
    confirmation_number='TEST-001'
)

print(result)
```

## Error Handling

### Validation Errors

```python
# Missing placeholders
ValidationError: "Placeholders must be sequential starting from {{1}}.
Found: {{1}}, {{3}}, {{4}}
Expected: {{1}}, {{2}}, {{3}}, {{4}}
Missing: {{2}}"
```

### Rendering Errors

```python
# Insufficient parameters
# If template has {{1}}, {{2}}, {{3}} but only 2 params provided,
# {{3}} will remain as "{{3}}" in the output
```

### PHI Compliance Errors

```python
ValidationError: "❌ Cannot save template with PHI content!

⚠️ PHI VIOLATION: Found prohibited keywords:
• diabetes, glucose level

WhatsApp templates should only contain:
• Generic appointment reminders
• Links to patient portal for details
• General notifications (no medical details)"
```

## Meta Business Manager Sync

### Fetching Templates from Meta

```python
# Manual sync
env['clinic.whatsapp.template'].sync_templates_from_meta()

# OR via UI button
Appointments → Configuration → WhatsApp Templates → Sync from Meta
```

**Process:**
1. Fetches all approved templates from Meta
2. Maps Meta template structure to Odoo fields
3. Creates/updates local templates
4. Validates PHI compliance
5. Skips non-compliant templates

### Template Status

Templates synced from Meta have additional fields:

- **Meta Template ID**: Unique ID in Meta
- **Meta Status**: APPROVED, PENDING, REJECTED, PAUSED, DISABLED
- **Meta Category**: AUTHENTICATION, MARKETING, UTILITY
- **Meta Last Sync**: Last sync timestamp
- **Meta Rejection Reason**: If rejected by Meta

## Best Practices

### 1. Keep Templates Simple

✅ Good:
```
Hi {{1}}, appointment on {{2}} at {{3}}.
Ref: {{4}}
```

❌ Too Complex:
```
Dear Mr./Mrs. {{1}}, regarding your scheduled medical consultation appointment
at our facility located at {{2}} on the date of {{3}} at precisely {{4}} hours...
```

### 2. Test Before Approval

Always test template rendering before submitting to Meta:

```python
template.render_template(
    patient_name='John',
    appointment_date='Jan 15',
    appointment_time='10 AM'
)
```

### 3. Use Consistent Parameter Order

Maintain consistent parameter order across templates:

```
{{1}} = patient_name (always first)
{{2}} = appointment_date (always second)
{{3}} = appointment_time (always third)
{{4}} = doctor_name
{{5}} = appointment_type
{{6}} = location
{{7}} = confirmation_number
```

### 4. Handle Optional Parameters

```python
# In template: check if parameter exists before using
params = {
    'doctor_name': appointment.staff_id.name if appointment.staff_id else 'your provider',
    'location': appointment.branch_id.name if appointment.branch_id else 'our clinic',
}
```

### 5. Localization

Create separate templates for each language:

- `appointment_reminder_en_v1`
- `appointment_reminder_es_v1`
- `appointment_reminder_pt_v1`

## Testing

### Unit Tests

```python
def test_template_rendering(self):
    """Test template variable substitution"""
    template = self.env['clinic.whatsapp.template'].create({
        'name': 'Test Template',
        'message_body': 'Hi {{1}}, appointment on {{2}} at {{3}}',
    })

    result = template.render_template(
        patient_name='John',
        appointment_date='Jan 15',
        appointment_time='10:00 AM'
    )

    self.assertEqual(
        result,
        'Hi John, appointment on Jan 15 at 10:00 AM'
    )

def test_placeholder_validation(self):
    """Test placeholder sequence validation"""
    with self.assertRaises(ValidationError):
        self.env['clinic.whatsapp.template'].create({
            'name': 'Invalid Template',
            'message_body': 'Hi {{1}}, see you on {{3}}',  # Missing {{2}}
        })
```

### Integration Tests

```python
def test_appointment_reminder_integration(self):
    """Test full reminder flow with template"""
    # Create appointment
    appointment = self.env['clinic.appointment'].create({...})

    # Create reminder config with template
    config = self.env['clinic.appointment.reminder.config'].create({
        'type_id': appointment.appointment_type_id.id,
        'channel': 'whatsapp',
        'whatsapp_template_id': self.template.id,
        'hours_before': 24,
    })

    # Send reminder
    msg_id = appointment._send_reminder_by_whatsapp(appointment, config)

    # Verify message created
    self.assertTrue(msg_id)
    msg = self.env['clinic.whatsapp.message'].browse(msg_id)
    self.assertEqual(msg.state, 'queued')
    self.assertIn(appointment.patient_id.name, msg.message_body)
```

## Troubleshooting

### Issue: Template Not Rendering

**Symptoms:** Placeholders remain as `{{1}}`, `{{2}}` in output

**Solutions:**
1. Check parameter order matches placeholder numbers
2. Verify all required parameters are provided
3. Check for typos in parameter names

### Issue: Validation Error on Save

**Symptoms:** "Placeholders must be sequential"

**Solutions:**
1. Ensure placeholders start from `{{1}}`
2. Check for missing numbers ({{1}}, {{2}}, {{4}} → missing {{3}})
3. Remove duplicate placeholders

### Issue: PHI Compliance Error

**Symptoms:** "Cannot save template with PHI content"

**Solutions:**
1. Remove specific medical terms
2. Use generic language
3. Link to patient portal instead of including details

## References

- [Meta WhatsApp Business API - Message Templates](https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates)
- [Meta Template Components](https://developers.facebook.com/docs/whatsapp/business-management-api/message-templates/components)
- [HIPAA WhatsApp Compliance](https://www.hhs.gov/hipaa/for-professionals/security/guidance/index.html)
- Odoo Model: `clinic.whatsapp.template`
- Python Method: `whatsapp_template.py:render_template()`
- Appointment Integration: `appointment.py:_send_reminder_by_whatsapp()`
