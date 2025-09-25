# Migration Notes - clinic_api

## Version 19.0.1.0.1

### Breaking Changes
- **SQL Constraints Removed**: Replaced with Python constraints
- View and data files need to be created for API management UI

### Migration Steps

#### 1. Remove old SQL constraints from database
```sql
-- Connect to your database and run:
ALTER TABLE clinic_api_jwt_blacklist DROP CONSTRAINT IF EXISTS clinic_api_jwt_blacklist_jti_unique;
```

#### 2. Install Python dependencies
```powershell
# Install required Python packages
pip install pyjwt cryptography
```

#### 3. Update module
```powershell
# Update module
python .\odoo-bin -d <DB_NAME> -u clinic_api

# Verify no errors
Get-Content .\odoo.log -Tail 100 | Select-String "clinic_api"
```

### Changes Applied
1. **jwt_blacklist.py**:
   - Replaced `_sql_constraints` with `@api.constrains` method
   - Added ValidationError import

2. **__manifest__.py**:
   - Removed references to 4 non-existent files
   - Kept existing security files

### Module Functionality
- API models properly defined (api_key, api_log, jwt_blacklist)
- Security groups and ACLs configured
- JWT blacklist for replay attack prevention ready
- Controller skeleton exists for API endpoints

### Notes
- Requires jwt and cryptography Python packages
- Views need to be created for API key management UI
- API endpoints need implementation in controllers

### Compatibility
- Odoo 19 Community Edition
- Python 3.8+
- Depends on: all clinic modules (patient, staff, appointment, treatment, prescription, finance)
- External: pyjwt, cryptography