# Clinic Appointment Core - Installation & Configuration Guide

## Overview

Enterprise-grade appointment management system for Odoo 19 Community Edition that replicates Odoo Enterprise Appointments functionality.

**Version:** 19.0.1.0.0
**License:** LGPL-3

## Features

### Phase 1: Core Models + Slot Engine
- Multi-stage appointment workflow (Draft → Confirmed → Completed/No Show/Cancelled)
- Configurable appointment types with duration, buffers, and capacity
- Timezone-aware slot generation engine
- Staff assignment modes: Random, Round Robin, By Skill, Customer Choice
- Availability rules with weekday/hour ranges and exclusions
- Pre-appointment questionnaires with multiple question types

### Phase 2: Website Booking
- Public online booking interface
- Real-time slot availability checking
- Responsive design with Bootstrap
- Multi-timezone support (browser timezone detection)
- Token-based authentication for anonymous users

### Phase 3: Tokens + Advanced Confirmation
- Secure token-based appointment management (view/reschedule/cancel)
- ICS/iCalendar file generation (RFC 5545 compliant)
- Professional HTML email templates with inline CSS
- Automatic email notifications with calendar attachments
- Calendar sync for Google/Outlook/Apple Calendar

### Phase 4: SMS & Advanced Features
- Multi-provider SMS system (Twilio, AWS SNS, HTTP API)
- Configurable SMS notifications for confirmation/reminders/cancellations
- SMS log with success/failure tracking
- Automated cron jobs for reminders and no-show marking
- Integration with email workflow

## Prerequisites

### Required Odoo Modules
```
base
mail
calendar
resource
website
clinic_patient
clinic_staff
```

### Python Dependencies
```bash
pip install pytz
```

### Optional Python Dependencies (for SMS)
```bash
# For Twilio
pip install twilio

# For AWS SNS
pip install boto3
```

## Installation

### 1. Module Installation

```powershell
# Navigate to Odoo directory
cd E:\susan\git\Odoo19

# Update module list
python .\odoo-bin -d <YOUR_DATABASE> --update-list

# Install the module
python .\odoo-bin -i clinic_appointment_core -d <YOUR_DATABASE>
```

### 2. Verify Installation

After installation, verify these menu items appear in your Odoo instance:

**Main Menu: Appointments**
- Appointments
  - All Appointments
  - Appointment Types
  - Stages
  - Availability Rules
  - Slots
  - Waiting List
  - SMS Log (if SMS enabled)
- Configuration
  - Appointment Settings
  - Email Templates

### 3. Post-Installation Configuration

#### A. Configure Appointment Stages

Navigate to: **Appointments > Configuration > Stages**

The following 5 stages are pre-configured:
1. **Draft** - New appointments (no email)
2. **Confirmed** - Confirmed appointments (sends confirmation email)
3. **Completed** - Successfully completed (no email)
4. **No Show** - Patient didn't show up (no email)
5. **Cancelled** - Cancelled by staff/patient (sends cancellation email)

You can customize these or add new stages as needed.

#### B. Configure Appointment Types

Navigate to: **Appointments > Configuration > Appointment Types**

6 demo appointment types are pre-configured:
- General Consultation (30 min)
- Follow-up Visit (15 min)
- Telemedicine Consultation (20 min, video meeting)
- Dental Examination (45 min)
- Emergency (15 min, no buffer)
- Health Workshop (2 hours)

**To create your own appointment type:**

1. Click **Create**
2. Fill in basic information:
   - **Name**: e.g., "Cardiology Consultation"
   - **Duration**: Default appointment length (e.g., 0.5 for 30 minutes)
   - **Buffer Before/After**: Time between appointments
   - **Capacity Per Slot**: Number of simultaneous appointments

3. Configure assignment:
   - **Assignment Mode**: How staff is assigned
     - `Customer Choice`: Patient selects doctor
     - `Random`: Randomly assigned
     - `Round Robin`: Balanced distribution
     - `By Skill`: Based on staff skills
   - **Allowed Staff**: Select which staff members can handle this type

4. Configure online booking:
   - **Allow Online Booking**: Enable/disable public booking
   - **Minimum Notice**: Hours required before appointment
   - **Maximum Advance**: How far ahead patients can book
   - **Booking URL**: Automatically generated

5. Configure policies:
   - **Allow Reschedule**: Let patients reschedule
   - **Reschedule Notice**: Hours required to reschedule
   - **Allow Cancel**: Let patients cancel
   - **Cancel Notice**: Hours required to cancel

6. Configure reminders (optional):
   - **Reminder Template**: Email template for reminders
   - **Reminder Hours**: When to send reminder (e.g., 24 hours before)

#### C. Configure Availability Rules

Navigate to: **Appointments > Configuration > Availability Rules**

**To create availability rules:**

1. Click **Create**
2. Select **Appointment Type**
3. Select **Staff Member** (optional - leave empty for type-wide rules)
4. Configure schedule:
   - **Timezone**: e.g., "America/New_York"
   - **Weekday**: e.g., "Monday"
   - **Hour From**: e.g., 9.0 (9:00 AM)
   - **Hour To**: e.g., 17.0 (5:00 PM)
   - **Active**: Check to enable

5. Configure exclusions (optional):
   - **Excluded Dates**: Specific dates to exclude (holidays, etc.)

**Example: Monday-Friday 9 AM - 5 PM**

Create 5 rules (one for each weekday):
```
Rule 1: Monday, 9.0 - 17.0, America/New_York
Rule 2: Tuesday, 9.0 - 17.0, America/New_York
Rule 3: Wednesday, 9.0 - 17.0, America/New_York
Rule 4: Thursday, 9.0 - 17.0, America/New_York
Rule 5: Friday, 9.0 - 17.0, America/New_York
```

#### D. Configure Email Templates

Navigate to: **Settings > Technical > Email > Templates**

4 professional email templates are pre-configured:
1. **Appointment Confirmation** (green theme)
2. **Appointment Reminder** (blue theme)
3. **Appointment Cancellation** (red theme)
4. **Appointment Rescheduled** (yellow theme)

All templates include:
- Professional HTML design with inline CSS
- ICS calendar attachment
- Appointment details
- Manage appointment link (reschedule/cancel)
- Responsive layout

You can customize these templates to match your brand.

#### E. Configure SMS Notifications (Optional)

Navigate to: **Settings > Appointments > SMS Notifications**

**1. Enable SMS**
- Check **Enable SMS Notifications**

**2. Configure Provider**

##### Option A: Twilio
1. Select **Twilio** as provider
2. Enter **Account SID** (from Twilio Console)
3. Enter **Auth Token** (from Twilio Console)
4. Enter **From Number** (E.164 format: +1234567890)
5. Get credentials: https://www.twilio.com/console

##### Option B: AWS SNS
1. Select **AWS SNS** as provider
2. Enter **AWS Access Key**
3. Enter **AWS Secret Key**
4. Enter **AWS Region** (e.g., us-east-1)
5. Enter **From Number** (E.164 format: +1234567890)

##### Option C: HTTP API (Custom)
1. Select **HTTP API (Custom)** as provider
2. Enter **API URL** (e.g., https://api.example.com/sms)
3. Enter **API Key** (authentication token)
4. Select **HTTP Method** (GET or POST)
5. Enter **From Number** (E.164 format: +1234567890)

**3. Test SMS**

After configuration, test by:
1. Creating a test appointment
2. Confirming it (sends confirmation SMS)
3. Check **SMS Log** for delivery status

#### F. Configure Cron Jobs

Navigate to: **Settings > Technical > Automation > Scheduled Actions**

2 cron jobs are pre-configured:

**1. Appointments: Send Reminders**
- **Interval**: 1 day
- **Next Execution**: Tomorrow at 10:00 AM
- **Action**: Sends email/SMS reminders for upcoming appointments
- **Logic**: Sends reminders X hours before appointment (configured per appointment type)

**2. Appointments: Mark No-Shows**
- **Interval**: 1 hour
- **Action**: Automatically marks appointments as "No Show" if patient didn't arrive
- **Logic**: Checks confirmed appointments that passed their start time

Both cron jobs are active by default. You can customize:
- Execution time
- Interval
- Active status

## Website Booking Configuration

### 1. Enable Online Booking

For each appointment type you want to offer online:
1. Edit the appointment type
2. Check **Allow Online Booking**
3. Configure **Minimum Notice Hours** (e.g., 24)
4. Configure **Maximum Advance Days** (e.g., 30)
5. Save

### 2. Share Booking URL

Each appointment type has a unique booking URL:
```
https://yourdomain.com/appointment/book/<type_id>
```

You can find this URL in the appointment type form under **Booking URL**.

Share this URL:
- On your website
- In email signatures
- In marketing materials
- On social media

### 3. Booking Flow

**Patient Experience:**

1. **Select Type** → Patient clicks booking URL
2. **Choose Date/Time** → Sees available slots in their timezone
3. **Select Staff** (if Customer Choice mode)
4. **Enter Information** → Name, email, phone
5. **Answer Questions** (if questionnaire configured)
6. **Confirm Booking** → Receives confirmation email with ICS attachment
7. **Manage Booking** → Can view/reschedule/cancel using token link

### 4. Token-Based Management

Each appointment has a secure token that allows patients to:
- **View** appointment details: `/appointment/view/<id>/<token>`
- **Reschedule**: `/appointment/reschedule/<id>/<token>`
- **Cancel**: `/appointment/cancel/<id>/<token>`

These links are included in all emails automatically.

**Security:**
- Tokens are 32-byte URL-safe random strings
- No login required
- Token expires when appointment is cancelled/deleted

## Usage Examples

### Example 1: Create Manual Appointment

1. Navigate to **Appointments > All Appointments**
2. Click **Create**
3. Fill in details:
   - **Patient**: Select from clinic_patient
   - **Appointment Type**: e.g., "General Consultation"
   - **Staff**: Select doctor
   - **Start Date**: Choose date/time
   - **Duration**: Auto-filled from type
4. Click **Save**
5. Click **Confirm** → Sends email/SMS

### Example 2: Configure Doctor Schedule

**Scenario:** Dr. Smith works Mon-Fri 9-5, lunch break 12-1

1. Create appointment type "Dr. Smith Consultation"
2. Create 5 morning rules:
   ```
   Mon-Fri: 9.0 - 12.0, America/New_York, Staff: Dr. Smith
   ```
3. Create 5 afternoon rules:
   ```
   Mon-Fri: 13.0 - 17.0, America/New_York, Staff: Dr. Smith
   ```
4. Set appointment type to allow online booking
5. Share booking URL with patients

### Example 3: Emergency Appointments

**Scenario:** Accept walk-in emergencies with minimal notice

1. Create appointment type "Emergency"
2. Configure:
   - **Duration**: 0.25 (15 minutes)
   - **Buffer Before**: 0 (no buffer)
   - **Buffer After**: 0 (no buffer)
   - **Minimum Notice Hours**: 0 (immediate)
   - **Assignment Mode**: Random
3. Create availability rules for all available staff
4. Enable online booking

### Example 4: Group Workshops

**Scenario:** Health education workshop for 20 people

1. Create appointment type "Health Workshop"
2. Configure:
   - **Duration**: 2.0 (2 hours)
   - **Capacity Per Slot**: 20
   - **Meeting Mode**: Physical
3. Create questionnaire for registration info
4. Enable online booking
5. Share URL with community

## Troubleshooting

### Module Won't Install

**Error:** Missing dependency

**Solution:**
```powershell
# Install missing base modules first
python .\odoo-bin -i clinic_patient,clinic_staff -d <DB>

# Then install appointment core
python .\odoo-bin -i clinic_appointment_core -d <DB>
```

### No Slots Available

**Problem:** Online booking shows "No slots available"

**Solutions:**
1. Check availability rules exist for the appointment type
2. Verify rules have correct timezone
3. Ensure staff members are assigned to the type
4. Check Maximum Advance Days setting
5. Verify appointment type is active

### Emails Not Sending

**Problem:** Confirmation emails not received

**Solutions:**
1. Check email configuration: **Settings > Technical > Email > Outgoing Mail Servers**
2. Verify email template is assigned to stage
3. Check patient has valid email address
4. Look in **Settings > Technical > Email > Emails** for send status
5. Check spam folder

### SMS Not Sending

**Problem:** SMS messages not delivered

**Solutions:**
1. Check SMS is enabled: **Settings > Appointments > SMS Notifications**
2. Verify provider credentials are correct
3. Check phone number format (must be E.164: +country code + number)
4. View **SMS Log** for error messages
5. Test credentials directly with provider (Twilio Console, AWS SNS)

### Cron Jobs Not Running

**Problem:** Reminders not sending automatically

**Solutions:**
1. Check cron job is active: **Settings > Technical > Automation > Scheduled Actions**
2. Verify next execution date is in the future
3. Check Odoo is running (crons don't run when server is stopped)
4. Look for errors in **Settings > Technical > Logging**
5. Manually trigger: Open cron job → Click **Run Manually**

### Token Links Not Working

**Problem:** Patient can't access appointment with token link

**Solutions:**
1. Verify token exists on appointment record
2. Check URL format: `/appointment/view/<id>/<token>`
3. Ensure appointment hasn't been deleted
4. Try generating new token: Edit appointment → **Generate Access Token** button
5. Check website module is installed and configured

## Technical Architecture

### Models

**Core Models:**
- `clinic.appointment` - Main appointment record (_inherits calendar.event)
- `clinic.appointment.type` - Appointment type configuration
- `clinic.appointment.stage` - Pipeline stages
- `clinic.appointment.rule` - Availability rules
- `clinic.appointment.slot` - Generated time slots

**Questionnaire:**
- `clinic.appointment.questionnaire.line` - Questions
- `clinic.appointment.questionnaire.answer` - Patient answers

**Supporting Models:**
- `clinic.waiting.list` - Waiting list entries
- `clinic.appointment.sms.log` - SMS delivery log

**Abstract Models (no database tables):**
- `clinic.appointment.slot.engine` - Slot generation logic
- `clinic.appointment.ics.generator` - ICS file generation
- `clinic.appointment.sms.manager` - SMS sending logic

**Configuration:**
- `res.config.settings` - SMS configuration parameters

### Key Technical Patterns

**1. _inherits Pattern (Delegation)**
```python
_inherits = {'calendar.event': 'event_id'}
```
This delegates to calendar.event for Enterprise compatibility without Many2many conflicts.

**2. Stage-based Workflow**
```python
stage_id = fields.Many2one('clinic.appointment.stage')
state = fields.Selection(related='stage_id.stage_type', store=True, readonly=True)
```
Flexible pipeline with automatic state computation.

**3. Token-based Authentication**
```python
access_token = fields.Char(copy=False, index=True)

def _generate_access_token(self):
    return secrets.token_urlsafe(32)
```
Secure anonymous access without login.

**4. Timezone Conversion**
```python
# Browser TZ → Rule TZ → UTC
user_dt = pytz.timezone(user_tz).localize(naive_dt)
rule_dt = user_dt.astimezone(pytz.timezone(rule.timezone))
utc_dt = rule_dt.astimezone(pytz.UTC)
```
Proper timezone handling for global appointments.

**5. Multi-provider SMS**
```python
def send_sms(self, phone, message):
    if provider == 'twilio':
        return self._send_via_twilio(...)
    elif provider == 'aws_sns':
        return self._send_via_aws_sns(...)
```
Provider abstraction for flexibility.

## Security

### User Groups

3 security groups are defined in `security/appointment_security.xml`:

1. **Appointment User** - Can view and create appointments
2. **Appointment Manager** - Can manage appointments and configuration
3. **Appointment Admin** - Full access including deletion

### Access Rights

Access rights are defined in `security/ir.model.access.csv`:

- **Public** - Read-only access to stages, questionnaires (for online booking)
- **Portal** - Read-only access to own appointments
- **User** - Read/write appointments, read configuration
- **Manager** - Full access except deletion
- **Admin** - Full access including deletion

### Record Rules

Record rules are defined in `security/appointment_record_rules.xml`:

- Users can only see appointments for their assigned staff members
- Managers and admins can see all appointments
- Public users can only access appointments via valid token

## Performance Optimization

### Database Indexes

Key fields are indexed for performance:
- `access_token` - Fast token lookup
- `patient_id` - Fast patient search
- `staff_id` - Fast staff filtering
- `appointment_type_id` - Fast type filtering
- `stage_id` - Fast stage filtering

### Slot Generation

Slot engine uses efficient algorithms:
- Generates slots on-demand (not pre-generated)
- Uses database queries to check capacity
- Caches availability rules in memory
- Timezone calculations done once per rule

### Email/SMS Queueing

Notifications use Odoo's mail queue:
- Emails sent asynchronously via `mail.mail`
- SMS logged in database for audit
- Failed sends can be retried manually

## Upgrade Path

### From 1.0.0 to Future Versions

When upgrading:

```powershell
# Backup database first
pg_dump <DB_NAME> > backup.sql

# Update module
python .\odoo-bin -u clinic_appointment_core -d <DB_NAME>
```

### Migration Notes

- Stage data will not be overwritten (`noupdate="1"`)
- Appointment type demo data will not be overwritten
- Custom email templates will be preserved
- Cron jobs will not be overwritten

## Support & Contributing

### Documentation
- **Odoo 19 Docs**: https://www.odoo.com/documentation/19.0/
- **ORM Reference**: https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html
- **QWeb Templates**: https://www.odoo.com/documentation/19.0/developer/reference/frontend/qweb.html

### Reporting Issues

When reporting issues, include:
1. Odoo version
2. Module version
3. Steps to reproduce
4. Error logs from **Settings > Technical > Logging**
5. Browser console errors (for website issues)

### Customization

This module is designed to be extensible. Common customizations:

**Add custom fields to appointments:**
```python
class ClinicAppointment(models.Model):
    _inherit = 'clinic.appointment'

    custom_field = fields.Char(string='Custom Field')
```

**Add custom email template:**
1. Create new template in `data/email_templates.xml`
2. Assign to stage or use in custom workflow

**Add custom SMS provider:**
```python
class SmsManager(models.AbstractModel):
    _inherit = 'clinic.appointment.sms.manager'

    def _send_via_custom_provider(self, phone, message, config):
        # Your implementation
        pass
```

## License

LGPL-3 - See LICENSE file for details

## Credits

**Author:** Clinic System
**Maintainer:** Your Organization
**Version:** 19.0.1.0.0
**Odoo Version:** 19.0 Community Edition

---

**Happy Scheduling!** 📅
