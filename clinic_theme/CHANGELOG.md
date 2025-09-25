# CHANGELOG - clinic_theme

## [19.0.1.0.0] - 2025-09-25

### Fixed
- Added missing assets.xml to data section in `__manifest__.py`
- Kept commented references to empty SCSS files (prevent compilation errors)

### Verified
- No _sql_constraints found (compliant with Odoo 19)
- No commented code blocks requiring action
- SCSS files exist but most are empty (0 bytes)
- Only accessibility.scss (12KB) and variables.scss have content
- assets.xml uses old Odoo approach (template inheritance) instead of manifest 'assets' key

### Notes
- Module uses dual asset definition approach:
  - Old: assets.xml with template inheritance
  - New: 'assets' key in __manifest__.py
- Consider migrating fully to Odoo 19's 'assets' key approach
- Empty SCSS files need content implementation