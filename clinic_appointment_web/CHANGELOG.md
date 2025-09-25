# CHANGELOG - clinic_appointment_web

## [19.0.1.0.1] - 2025-09-25

### Fixed
- **Critical**: Removed duplicate and incorrect model definition from `controllers/rate_limiter.py`
  - Removed class ClinicRateLimit that incorrectly inherited from non-existent http.Model
  - Removed _sql_constraints from controller file (should only be in models)
  - Model properly defined in `models/rate_limit.py`
- Fixed `__manifest__.py` - removed references to non-existent files:
  - Removed 10 missing view files
  - Removed 2 missing data files

### Verified
- No _sql_constraints in this module (compliant with Odoo 19)
- No commented code blocks requiring action
- Security files exist and properly configured
- Module dependencies correct (website, portal, website_payment, clinic modules)