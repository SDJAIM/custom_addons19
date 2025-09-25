# Migration Notes - clinic_treatment

## Version 19.0.1.0.1

### Breaking Changes
- **Removed clinic.tooth references**: The module no longer references the dental-specific model
- **SQL Constraints Removed**: Replaced with Python constraints

### Migration Steps

#### 1. Remove old SQL constraints from database
```sql
-- Connect to your database and run:
ALTER TABLE clinic_treatment_consent DROP CONSTRAINT IF EXISTS clinic_treatment_consent_code_unique;
ALTER TABLE clinic_treatment_procedure DROP CONSTRAINT IF EXISTS clinic_treatment_procedure_code_unique;
ALTER TABLE clinic_procedure_category DROP CONSTRAINT IF EXISTS clinic_procedure_category_code_unique;
```

#### 2. Update module
```powershell
# Update module
python .\odoo-bin -d <DB_NAME> -u clinic_treatment

# Verify no errors (especially AssertionError for clinic.tooth)
Get-Content .\odoo.log -Tail 100 | Select-String "clinic_treatment"
```

### Changes Applied
1. **Security fixes**:
   - Removed invalid ACL entries for clinic.tooth model

2. **Report fixes**:
   - treatment_plan_report.xml: Changed from tooth_ids to body_area field

3. **Constraint migrations**:
   - treatment_consent.py: Replaced _sql_constraints with @api.constrains
   - treatment_procedure.py: Replaced 2 _sql_constraints with @api.constrains
   - Added ValidationError import where needed

### Notes
- The tooth_ids field remains commented in treatment_plan_line.py for future activation when clinic_dental_chart module is installed
- This fixes the "Field clinic.treatment.plan.line.tooth_ids with unknown comodel_name 'clinic.tooth'" error

### Compatibility
- Odoo 19 Community Edition
- Python 3.8+
- Depends on: clinic_patient, clinic_staff, clinic_appointment_core