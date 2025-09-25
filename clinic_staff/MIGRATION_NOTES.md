# Migration Notes - clinic_staff

## Version 19.0.1.0.1

### Breaking Changes
- **SQL Constraints Removed**: Replaced with Python constraints
  - Database-level constraints converted to application-level validation
  - Existing unique constraints will need to be manually removed from DB

### Migration Steps

#### 1. Remove old SQL constraints from database
```sql
-- Connect to your database and run:
ALTER TABLE clinic_staff DROP CONSTRAINT IF EXISTS clinic_staff_staff_code_unique;
ALTER TABLE clinic_staff DROP CONSTRAINT IF EXISTS clinic_staff_email_unique;
ALTER TABLE clinic_staff DROP CONSTRAINT IF EXISTS clinic_staff_license_unique;

ALTER TABLE clinic_staff_specialization DROP CONSTRAINT IF EXISTS clinic_staff_specialization_name_unique;
ALTER TABLE clinic_staff_specialization DROP CONSTRAINT IF EXISTS clinic_staff_specialization_code_unique;

ALTER TABLE clinic_staff_specialization_category DROP CONSTRAINT IF EXISTS clinic_staff_specialization_category_name_unique;

ALTER TABLE clinic_room DROP CONSTRAINT IF EXISTS clinic_room_code_branch_unique;

ALTER TABLE clinic_branch DROP CONSTRAINT IF EXISTS clinic_branch_code_unique;
```

#### 2. Update module
```powershell
# Update module
python .\odoo-bin -d <DB_NAME> -u clinic_staff

# Verify no errors
Get-Content .\odoo.log -Tail 100 | Select-String "clinic_staff"
```

### Changes Applied
1. **staff.py**:
   - Replaced 3 `_sql_constraints` with `@api.constrains` methods
   - Added null-safety checks for optional fields

2. **staff_specialization.py**:
   - Replaced 3 `_sql_constraints` with `@api.constrains` methods
   - Handled composite constraint (name + category_id)
   - Added ValidationError import

3. **room.py**:
   - Replaced composite constraint with `@api.constrains` method
   - Handled branch_id null cases

4. **branch.py**:
   - Replaced `_sql_constraints` with `@api.constrains` method
   - Added ValidationError import

5. **__manifest__.py**:
   - Removed references to non-existent asset files

### Compatibility
- Odoo 19 Community Edition
- Python 3.8+
- Depends on: base, mail, hr, calendar, resource