# CHANGELOG - clinic_treatment

## [19.0.1.0.1] - 2025-09-25

### Fixed
- **Critical**: Removed references to non-existent `clinic.tooth` model:
  - Removed 2 lines from `security/ir.model.access.csv` for clinic.tooth access rules
  - Fixed `report/treatment_plan_report.xml` - replaced tooth_ids display with body_area field
  - Note: tooth_ids field remains commented in `treatment_plan_line.py` for future use with dental module

- Replaced `_sql_constraints` with `@api.constrains` methods (Odoo 19 compliance):
  - `treatment_consent.py`: 'code_unique' → `_check_code_unique()` (added ValidationError import)
  - `treatment_procedure.py`: 'code_unique' → `_check_code_unique()` (2 occurrences)

### Verified
- No other commented code requiring action
- Security groups and ACLs properly defined
- Module dependencies correct (base, mail, clinic_patient, clinic_staff, clinic_appointment_core)
- No CSS files present