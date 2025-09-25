# CHANGELOG - clinic_prescription

## [19.0.1.0.1] - 2025-09-25

### Fixed
- Replaced `_sql_constraints` with `@api.constrains` methods (Odoo 19 compliance):
  - `frequency.py`: 'unique_code' → `_check_code_unique()` (added ValidationError import)
  - `drug_interaction.py`: 'unique_drug_pair' → `_check_unique_drug_pair()`
  - `medication_route.py`: 'unique_code' → `_check_code_unique()` (added ValidationError import)
  - `dose_unit.py`: 'unique_abbreviation' → `_check_abbreviation_unique()` (added ValidationError import)

- Removed references to non-existent files from `__manifest__.py`:
  - 2 missing report files (prescription_report, prescription_templates)
  - 6 missing view files (prescription_views, medication_views, medication_stock_views, prescription_template_views, medication_route_views, menu_views)
  - 2 missing asset files (prescription.scss, prescription_widget.js)

### Verified
- No commented code blocks requiring action
- Security files exist and properly configured
- All 8 data files exist
- 1 view file exists (prescription_wizard_views.xml)
- Wizard files exist
- Module dependencies correct (stock, product, clinic modules)