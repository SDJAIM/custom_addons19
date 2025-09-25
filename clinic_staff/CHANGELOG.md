# CHANGELOG - clinic_staff

## [19.0.1.0.1] - 2025-09-25

### Fixed
- Replaced `_sql_constraints` with `@api.constrains` methods in `staff.py` (Odoo 19 compliance)
  - `staff_code_unique` → `_check_staff_code_unique()`
  - `email_unique` → `_check_email_unique()`
  - `license_unique` → `_check_license_unique()`
- Replaced `_sql_constraints` with `@api.constrains` methods in `staff_specialization.py`
  - `name_unique` (with category_id) → `_check_name_unique()`
  - `code_unique` → `_check_code_unique()`
  - Added ValidationError import
- Replaced `_sql_constraints` with `@api.constrains` methods in `room.py`
  - `code_branch_unique` → `_check_code_branch_unique()`
- Replaced `_sql_constraints` with `@api.constrains` methods in `branch.py`
  - `code_unique` → `_check_code_unique()`
  - Added ValidationError import
- Removed non-existent asset references from `__manifest__.py`
  - Removed `staff.scss` and `staff_calendar.js` references

### Verified
- No commented code blocks requiring action
- Security groups and ACLs properly defined
- Module dependencies correct (base, mail, hr, calendar, resource)