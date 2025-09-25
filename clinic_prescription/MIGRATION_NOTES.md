# Migration Notes - clinic_prescription

## Version 19.0.1.0.1

### Breaking Changes
- **SQL Constraints Removed**: Replaced with Python constraints
- View files need to be created for full functionality
- Report files need implementation

### Migration Steps

#### 1. Remove old SQL constraints from database
```sql
-- Connect to your database and run:
ALTER TABLE clinic_frequency DROP CONSTRAINT IF EXISTS clinic_frequency_unique_code;
ALTER TABLE clinic_drug_interaction DROP CONSTRAINT IF EXISTS clinic_drug_interaction_unique_drug_pair;
ALTER TABLE clinic_medication_route DROP CONSTRAINT IF EXISTS clinic_medication_route_unique_code;
ALTER TABLE clinic_dose_unit DROP CONSTRAINT IF EXISTS clinic_dose_unit_unique_abbreviation;
```

#### 2. Update module
```powershell
# Update module
python .\odoo-bin -d <DB_NAME> -u clinic_prescription

# Verify no errors
Get-Content .\odoo.log -Tail 100 | Select-String "clinic_prescription"
```

### Changes Applied
1. **Model constraint migrations**:
   - frequency.py: Replaced _sql_constraints with @api.constrains
   - drug_interaction.py: Replaced composite constraint with Python validation
   - medication_route.py: Replaced _sql_constraints with @api.constrains
   - dose_unit.py: Replaced _sql_constraints with @api.constrains

2. **__manifest__.py**:
   - Removed references to 10 non-existent files
   - Kept existing files: security, data (8 files), 1 view

### Module Functionality
- Prescription models properly defined with workflow states
- FEFO stock management ready
- Drug interaction checking model
- Security and data files configured
- Wizard views for dispensing exist

### Compatibility
- Odoo 19 Community Edition
- Python 3.8+
- Depends on: stock, product, clinic modules