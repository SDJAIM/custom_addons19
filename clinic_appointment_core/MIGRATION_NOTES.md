# Migration Notes - clinic_appointment_core

## Version 19.0.1.0.1

### Breaking Changes
- **SQL Constraints Removed**: Replaced with Python constraints

### Migration Steps

#### 1. Remove old SQL constraints from database
```sql
-- Connect to your database and run:
ALTER TABLE clinic_appointment_type DROP CONSTRAINT IF EXISTS clinic_appointment_type_code_unique;
```

#### 2. Update module
```powershell
# Update module
python .\odoo-bin -d <DB_NAME> -u clinic_appointment_core

# Verify no errors
Get-Content .\odoo.log -Tail 100 | Select-String "clinic_appointment_core"
```

### Changes Applied
1. **appointment_type.py**:
   - Replaced `_sql_constraints` with `@api.constrains` method
   - Added ValidationError import
   - Added null-safety check for code uniqueness

2. **__manifest__.py**:
   - Removed references to non-existent static files

### Compatibility
- Odoo 19 Community Edition
- Python 3.8+
- Depends on: calendar, resource, clinic_patient, clinic_staff