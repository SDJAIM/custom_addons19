# Migration Notes - clinic_dental_chart

## Version 19.0.1.0.1

### Breaking Changes
- View and data files need to be created for dental chart functionality
- Asset files for interactive dental chart need implementation

### Migration Steps

#### 1. Update module
```powershell
# Update module
python .\odoo-bin -d <DB_NAME> -u clinic_dental_chart

# Verify no errors
Get-Content .\odoo.log -Tail 100 | Select-String "clinic_dental_chart"
```

#### 2. Enable tooth_ids in clinic_treatment (optional)
Once this module is installed, you can uncomment the tooth_ids field in:
- `clinic_treatment/models/treatment_plan_line.py` (lines 46-50)

### Changes Applied
1. **__manifest__.py**:
   - Removed references to 13 non-existent files
   - Only security files are currently loaded

### Module Functionality
- Defines `clinic.tooth` model with proper structure
- Provides dental chart models (tooth, dental_chart, periodontal_chart, etc.)
- Security groups and ACLs configured

### Compatibility
- Odoo 19 Community Edition
- Python 3.8+
- Depends on: clinic_patient, clinic_staff, clinic_appointment_core, clinic_treatment