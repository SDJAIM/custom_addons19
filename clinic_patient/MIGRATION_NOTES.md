# Migration Notes - clinic_patient

## Version 19.0.1.0.1

### Breaking Changes
- **SQL Constraints Removed**: Replaced with Python constraints
  - Database-level constraints converted to application-level validation
  - Existing unique constraints will need to be manually removed from DB

### Migration Steps

#### 1. Remove old SQL constraints from database
```sql
-- Connect to your database and run:
ALTER TABLE clinic_patient DROP CONSTRAINT IF EXISTS clinic_patient_patient_id_unique;
ALTER TABLE clinic_patient DROP CONSTRAINT IF EXISTS clinic_patient_email_unique;
ALTER TABLE clinic_insurance_company DROP CONSTRAINT IF EXISTS clinic_insurance_company_name_unique;
ALTER TABLE clinic_insurance_company DROP CONSTRAINT IF EXISTS clinic_insurance_company_code_unique;
```

#### 2. Update module
```powershell
# Update module
python .\odoo-bin -d <DB_NAME> -u clinic_patient

# Verify no errors
Get-Content .\odoo.log -Tail 100 | Select-String "clinic_patient"
```

### Changes Applied
1. **patient.py**:
   - Replaced `_sql_constraints` with `@api.constrains` methods
   - Added null-safety check for email uniqueness

2. **patient_insurance.py**:
   - Replaced `_sql_constraints` with `@api.constrains` methods
   - Added null-safety check for code uniqueness

### Compatibility
- Odoo 19 Community Edition
- Python 3.8+
- Depends on: clinic_staff module