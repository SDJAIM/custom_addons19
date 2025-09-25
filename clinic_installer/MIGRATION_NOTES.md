# Migration Notes - clinic_installer

## Version 19.0.1.0.1

### Breaking Changes
None - This is an installer module

### Migration Steps

#### 1. Install Python dependencies
```powershell
# Install all required Python packages
pip install pyjwt cryptography phonenumbers requests
```

#### 2. Install module
```powershell
# This will install ALL clinic modules
python .\odoo-bin -d <DB_NAME> -i clinic_installer

# Or update if already installed
python .\odoo-bin -d <DB_NAME> -u clinic_installer

# Verify no errors
Get-Content .\odoo.log -Tail 100 | Select-String "clinic"
```

### Changes Applied
1. **__manifest__.py**:
   - Added `clinic_base` as first dependency
   - Removed reference to non-existent installer.js file

### Module Purpose
- Auto-installer for complete clinic system
- Installs all 15 clinic modules in correct dependency order
- Ensures proper module loading sequence

### Dependency Order
1. clinic_base (utilities)
2. clinic_staff (security groups)
3. clinic_patient
4. clinic_theme
5. clinic_appointment_core
6. clinic_treatment
7. clinic_prescription
8. clinic_dental_chart
9. clinic_finance
10. clinic_appointment_web
11. clinic_integrations_telemed
12. clinic_integrations_whatsapp
13. clinic_api
14. clinic_kpis

### Compatibility
- Odoo 19 Community Edition
- Python 3.8+
- External: jwt, cryptography, phonenumbers, requests