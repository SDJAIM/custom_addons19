# CHANGELOG - clinic_api

## [19.0.1.0.1] - 2025-09-25

### Fixed
- Replaced `_sql_constraints` with `@api.constrains` method in `jwt_blacklist.py` (Odoo 19 compliance)
  - `jti_unique` → `_check_jti_unique()`
  - Added ValidationError import

- Removed references to non-existent files from `__manifest__.py`:
  - 1 missing data file (api_data.xml)
  - 3 missing view files (api_key_views, api_log_views, menu_views)

### Verified
- No commented code blocks requiring action
- Security files exist and properly configured
- Module dependencies correct (all clinic modules)
- External dependencies declared (jwt, cryptography)
- API models properly defined (api_key, api_log, jwt_blacklist)