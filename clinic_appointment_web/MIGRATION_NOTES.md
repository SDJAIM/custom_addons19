# Migration Notes - clinic_appointment_web

## Version 19.0.1.0.1

### Breaking Changes
- Removed duplicate model definition from controller file
- View and data files need to be created if web booking functionality is required

### Migration Steps

#### 1. Update module
```powershell
# Update module
python .\odoo-bin -d <DB_NAME> -u clinic_appointment_web

# Verify no errors
Get-Content .\odoo.log -Tail 100 | Select-String "clinic_appointment_web"
```

### Changes Applied
1. **controllers/rate_limiter.py**:
   - Removed entire duplicate ClinicRateLimit class (lines 126-170)
   - Model is properly defined in models/rate_limit.py

2. **__manifest__.py**:
   - Removed references to 12 non-existent files
   - Only security files are currently loaded

### Notes
- The module currently has minimal functionality (models and security only)
- Web booking views and templates need to be implemented
- Rate limiting model is properly defined in models/rate_limit.py

### Compatibility
- Odoo 19 Community Edition
- Python 3.8+
- Depends on: website, portal, website_payment, clinic_finance