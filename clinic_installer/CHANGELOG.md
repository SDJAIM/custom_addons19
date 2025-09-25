# CHANGELOG - clinic_installer

## [19.0.1.0.1] - 2025-09-25

### Fixed
- **Critical**: Added missing `clinic_base` module to dependencies (must be first in load order)
- Removed reference to non-existent `static/src/js/installer.js` file from assets

### Verified
- No _sql_constraints found (compliant with Odoo 19)
- No commented code blocks requiring action
- All data files exist
- All view files exist
- CSS file exists
- Security files properly configured
- External dependencies declared (jwt, cryptography, phonenumbers, requests)

### Notes
- This is the installer module that loads all clinic modules
- Depends on ALL clinic modules in correct order
- clinic_base added as first dependency (provides core utilities)