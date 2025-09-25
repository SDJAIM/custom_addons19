# CHANGELOG - clinic_patient

## [19.0.1.0.1] - 2025-09-25

### Fixed
- Replaced `_sql_constraints` with `@api.constrains` methods in `patient.py` (Odoo 19 compliance)
  - `patient_id_unique` → `_check_patient_id_unique()`
  - `email_unique` → `_check_email_unique()`
- Replaced `_sql_constraints` with `@api.constrains` methods in `patient_insurance.py`
  - `name_unique` → `_check_name_unique()`
  - `code_unique` → `_check_code_unique()`

### Verified
- No commented code blocks requiring action
- Security groups and ACLs properly defined
- Module dependencies correct (base, mail, contacts, portal, clinic_staff)
- No CSS files present