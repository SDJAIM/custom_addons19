# 👥 Clinic Patient Management Module

## Overview
The **clinic_patient** module is a comprehensive patient management system designed for medical and dental clinics using Odoo 19 Community Edition. It provides complete patient record management with GDPR compliance, family relationships, insurance tracking, and portal access capabilities.

## ✨ Features

### Core Features
- 📋 **Complete Patient Records**: Demographics, contact info, medical history
- 👨‍👩‍👧‍👦 **Family Management**: Link family members and emergency contacts
- 🏥 **Insurance Tracking**: Multiple insurance policies per patient
- 🌐 **Portal Access**: Patient self-service portal integration
- 📊 **Analytics Ready**: Age groups, patient types, visit tracking
- 🔒 **GDPR Compliant**: Privacy consent and data protection

### Technical Features
- Auto-generated unique patient IDs
- Automatic partner creation for portal access
- Multi-branch support
- Advanced search with indexed fields
- Email and phone validation
- Age calculation and categorization

## 📦 Dependencies

### Odoo Core Modules
- `base` - Core Odoo functionality
- `mail` - Email and messaging
- `contacts` - Partner management
- `portal` - Patient portal access

### Custom Modules
- `clinic_staff` - Required for security rules

## 🏗️ Module Structure

```
clinic_patient/
├── models/
│   ├── patient.py          # Main patient model
│   ├── patient_family.py   # Family members
│   └── patient_insurance.py # Insurance policies
├── views/
│   ├── patient_views.xml   # Patient forms and lists
│   └── menu_views.xml      # Menu structure
├── security/
│   ├── patient_security.xml # Security groups
│   ├── ir.model.access.csv  # Access rights
│   └── patient_record_rules.xml # Record rules
├── data/
│   └── patient_sequence.xml # ID sequences
└── __manifest__.py
```

## 📊 Data Models

### clinic.patient
Main patient model with comprehensive patient information.

#### Key Fields
| Field | Type | Description |
|-------|------|-------------|
| `patient_id` | Char | Unique auto-generated ID |
| `name` | Char | Full patient name |
| `date_of_birth` | Date | Birth date (required) |
| `age` | Integer | Auto-calculated age |
| `gender` | Selection | Gender selection |
| `phone` | Char | Phone number (indexed) |
| `mobile` | Char | Mobile number (required, indexed) |
| `email` | Char | Email address (unique, indexed) |
| `blood_group` | Selection | Blood type |
| `allergies` | Text | Known allergies |

#### Computed Fields
- `age` - Calculated from date_of_birth
- `age_group` - Categorized (infant/child/teen/adult/senior)
- `display_name` - [Patient_ID] Name format

#### Methods

##### `create(vals_list)`
Creates new patient records with auto-generated IDs.

```python
patient = self.env['clinic.patient'].create({
    'name': 'John Doe',
    'date_of_birth': '1990-01-01',
    'mobile': '+1234567890',
    'email': 'john@example.com'
})
```

##### `action_create_portal_user()`
Creates portal access for patient self-service.

```python
patient.action_create_portal_user()
# Creates user with portal access rights
```

##### `action_view_appointments()`
Opens patient's appointment history.

```python
action = patient.action_view_appointments()
# Returns action dict for appointment list view
```

### clinic.patient.family
Family member and emergency contact management.

#### Key Fields
| Field | Type | Description |
|-------|------|-------------|
| `patient_id` | Many2one | Related patient |
| `member_name` | Char | Family member name |
| `relationship` | Selection | Relationship type |
| `phone` | Char | Contact phone |
| `is_emergency_contact` | Boolean | Emergency contact flag |

### clinic.patient.insurance
Insurance policy tracking per patient.

#### Key Fields
| Field | Type | Description |
|-------|------|-------------|
| `patient_id` | Many2one | Related patient |
| `insurance_company_id` | Many2one | Insurance provider |
| `policy_number` | Char | Policy number |
| `valid_from` | Date | Coverage start |
| `valid_to` | Date | Coverage end |

## 🔒 Security

### Access Groups
- `group_clinic_patient_user` - View patient records
- `group_clinic_patient_manager` - Full patient management
- `group_portal` - Patient self-service access

### Record Rules
- Portal users can only see their own records
- Staff see patients from their assigned branches
- Managers have unrestricted access

## 🚀 Installation

1. Place module in `custom_addons/` directory
2. Update apps list: `python odoo-bin --update-list`
3. Install via Apps menu or command:
```bash
python odoo-bin -i clinic_patient -d your_database
```

## ⚙️ Configuration

### Patient ID Sequence
Configure in Settings > Technical > Sequences > `clinic.patient`
- Default format: `PAT/%(year)s/%(month)s/%(day)s/%(h24)s%(min)s%(sec)s`

### Portal Access
1. Ensure `portal` module is installed
2. Patient must have valid email
3. Use "Create Portal User" button on patient form

### Multi-Branch Setup
1. Define branches in `clinic.branch`
2. Assign patients to branches via Many2many field
3. Configure user access per branch

## 📈 Usage Examples

### Creating a Patient
```python
# Via UI
Navigate to Clinic > Patients > New

# Via Code
patient = self.env['clinic.patient'].create({
    'name': 'Jane Smith',
    'date_of_birth': '1985-05-15',
    'mobile': '+1987654321',
    'gender': 'female',
    'blood_group': 'o+',
    'email': 'jane.smith@example.com'
})
```

### Adding Family Members
```python
family = self.env['clinic.patient.family'].create({
    'patient_id': patient.id,
    'member_name': 'John Smith',
    'relationship': 'spouse',
    'phone': '+1987654320',
    'is_emergency_contact': True
})
```

### Search Operations (Optimized)
```python
# Search by phone (indexed for performance)
patients = self.env['clinic.patient'].search([
    ('mobile', 'like', '9876%')
])

# Age group filtering
seniors = self.env['clinic.patient'].search([
    ('age_group', '=', 'senior')
])
```

## 🔄 Upgrade Notes

### From Previous Versions
- Run data migration for patient IDs if upgrading
- Reindex phone/email fields for performance
- Update security groups assignments

## 🧪 Testing

### Test Coverage Areas
- Patient creation with validation
- Age calculation accuracy
- Email/phone format validation
- Portal user creation
- Family member linking
- Insurance policy management

### Sample Test
```python
def test_patient_creation(self):
    patient = self.env['clinic.patient'].create({
        'name': 'Test Patient',
        'date_of_birth': '2000-01-01',
        'mobile': '+1234567890'
    })
    self.assertTrue(patient.patient_id)
    self.assertEqual(patient.age, 25)  # As of 2025
```

## 🐛 Known Issues
- Email uniqueness constraint may conflict with archived patients
- Portal user creation requires manual password reset email

## 📝 Changelog

### Version 19.0.1.0.0 (Current)
- Initial release for Odoo 19
- Complete patient management system
- Family and insurance tracking
- Portal integration
- Performance optimizations with field indexing

## 🤝 Contributing
Please submit issues and pull requests via the project repository.

## 📄 License
LGPL-3

## 📞 Support
For support, please contact the Clinic System team or raise an issue in the project repository.

---
*Module developed for Odoo 19 Community Edition*
*Part of the Complete Clinic Management System*