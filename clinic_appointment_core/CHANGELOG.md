# CHANGELOG - clinic_appointment_core

## [19.0.1.0.1] - 2025-09-25

### Fixed
- Replaced `_sql_constraints` with `@api.constrains` method in `appointment_type.py` (Odoo 19 compliance)
  - `code_unique` → `_check_code_unique()`
  - Added ValidationError import
- Removed non-existent asset references from `__manifest__.py`
  - Removed appointment.scss and appointment_calendar.js references

### Verified
- No commented code blocks requiring action
- Security groups and ACLs properly defined
- Module dependencies correct (base, mail, calendar, resource, clinic_patient, clinic_staff)
- No CSS/JS files present