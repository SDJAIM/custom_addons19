# CHANGELOG - clinic_dental_chart

## [19.0.1.0.1] - 2025-09-25

### Fixed
- Removed references to non-existent files from `__manifest__.py`:
  - 3 missing data files (tooth_data.xml, dental_procedures.xml, tooth_conditions.xml)
  - 5 missing view files
  - 1 missing report file
  - 4 missing asset files (scss, js, xml)

### Verified
- No _sql_constraints found (compliant with Odoo 19)
- No commented code blocks requiring action
- Security files exist and properly configured
- Module dependencies correct (includes clinic_treatment)
- **Important**: This module defines `clinic.tooth` model used by clinic_treatment

### Notes
- This module provides the `clinic.tooth` model that clinic_treatment references
- The tooth_ids field in clinic_treatment can be enabled when this module is installed