# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
from datetime import datetime, date, timedelta
import logging

_logger = logging.getLogger(__name__)


class DataValidator(models.AbstractModel):
    _name = 'clinic.data.validator'
    _description = 'Data Validation Rules'

    @api.model
    def validate_patient_data(self, patient_data):
        """Comprehensive patient data validation"""
        errors = []
        warnings = []

        # Required fields
        required_fields = ['name', 'birth_date', 'gender']
        for field in required_fields:
            if not patient_data.get(field):
                errors.append(_("Field '%s' is required") % field)

        # Name validation
        if patient_data.get('name'):
            name = patient_data['name']
            if len(name) < 2:
                errors.append(_("Name must be at least 2 characters"))
            if not re.match(r'^[a-zA-Z\s\-\'\.]+$', name):
                warnings.append(_("Name contains unusual characters"))

        # Birth date validation
        if patient_data.get('birth_date'):
            birth_date = patient_data['birth_date']
            if isinstance(birth_date, str):
                try:
                    birth_date = fields.Date.from_string(birth_date)
                except:
                    errors.append(_("Invalid birth date format"))

            if birth_date:
                if birth_date > date.today():
                    errors.append(_("Birth date cannot be in the future"))

                age = (date.today() - birth_date).days / 365.25
                if age > 150:
                    warnings.append(_("Patient age appears to be over 150 years"))
                if age < 0:
                    errors.append(_("Invalid birth date"))

        # Email validation
        if patient_data.get('email'):
            if not self.validate_email_format(patient_data['email']):
                errors.append(_("Invalid email format"))

        # Phone validation
        if patient_data.get('phone'):
            if not self.validate_phone_format(patient_data['phone']):
                warnings.append(_("Phone number format may be invalid"))

        # ID validation
        if patient_data.get('identification_number'):
            if not self.validate_identification(
                patient_data['identification_number'],
                patient_data.get('identification_type', 'dni')
            ):
                warnings.append(_("Identification number format may be invalid"))

        # Insurance validation
        if patient_data.get('insurance_number'):
            if not re.match(r'^[A-Z0-9\-]+$', patient_data['insurance_number']):
                warnings.append(_("Insurance number format may be invalid"))

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    @api.model
    def validate_appointment_data(self, appointment_data):
        """Validate appointment data"""
        errors = []
        warnings = []

        # Required fields
        required = ['patient_id', 'doctor_id', 'appointment_date']
        for field in required:
            if not appointment_data.get(field):
                errors.append(_("Field '%s' is required") % field)

        # Date validation
        if appointment_data.get('appointment_date'):
            apt_date = appointment_data['appointment_date']
            if isinstance(apt_date, str):
                apt_date = fields.Datetime.from_string(apt_date)

            # Check if in the past
            if apt_date < datetime.now():
                warnings.append(_("Appointment date is in the past"))

            # Check if too far in future
            if apt_date > datetime.now() + timedelta(days=365):
                warnings.append(_("Appointment is more than 1 year in the future"))

            # Check working hours
            if hasattr(apt_date, 'hour'):
                if apt_date.hour < 7 or apt_date.hour > 22:
                    warnings.append(_("Appointment is outside normal working hours"))

        # Duration validation
        if appointment_data.get('duration'):
            duration = appointment_data['duration']
            if duration <= 0:
                errors.append(_("Duration must be positive"))
            if duration > 8:
                warnings.append(_("Appointment duration is more than 8 hours"))

        # Check for conflicts
        if all([appointment_data.get('patient_id'),
                appointment_data.get('doctor_id'),
                appointment_data.get('appointment_date')]):

            conflicts = self.check_appointment_conflicts(
                appointment_data['patient_id'],
                appointment_data['doctor_id'],
                appointment_data['appointment_date'],
                appointment_data.get('duration', 0.5)
            )
            if conflicts:
                errors.extend(conflicts)

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    @api.model
    def validate_prescription_data(self, prescription_data):
        """Validate prescription data"""
        errors = []
        warnings = []

        # Check prescription lines
        if not prescription_data.get('prescription_lines'):
            errors.append(_("Prescription must have at least one medication"))

        for line in prescription_data.get('prescription_lines', []):
            # Validate dosage
            if line.get('dosage'):
                dosage = line['dosage']
                if not re.match(r'^\d+(\.\d+)?\s*(mg|ml|g|units?|tablets?|caps?)?$', dosage, re.I):
                    warnings.append(_("Dosage format may be incorrect: %s") % dosage)

            # Validate frequency
            if line.get('frequency'):
                valid_frequencies = ['once daily', 'twice daily', 'three times daily',
                                   'four times daily', 'every hour', 'every 2 hours',
                                   'every 4 hours', 'every 6 hours', 'every 8 hours',
                                   'every 12 hours', 'as needed', 'before meals',
                                   'after meals', 'at bedtime']
                if line['frequency'].lower() not in valid_frequencies:
                    warnings.append(_("Non-standard frequency: %s") % line['frequency'])

            # Validate duration
            if line.get('duration_days'):
                if line['duration_days'] <= 0:
                    errors.append(_("Duration must be positive"))
                if line['duration_days'] > 365:
                    warnings.append(_("Prescription duration is more than 1 year"))

        # Check for controlled substances
        if prescription_data.get('has_controlled_substance'):
            if not prescription_data.get('dea_number'):
                errors.append(_("DEA number required for controlled substances"))

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    @api.model
    def validate_lab_result(self, result_data):
        """Validate lab test result data"""
        errors = []
        warnings = []

        # Check result value
        if result_data.get('result_value'):
            value = result_data['result_value']

            # Check if numeric when expected
            if result_data.get('value_type') == 'numeric':
                try:
                    float(value)
                except ValueError:
                    errors.append(_("Result value must be numeric"))

            # Check reference range
            if result_data.get('normal_range_min') and result_data.get('normal_range_max'):
                try:
                    val = float(value)
                    min_val = float(result_data['normal_range_min'])
                    max_val = float(result_data['normal_range_max'])

                    if val < min_val or val > max_val:
                        warnings.append(_("Result is outside normal range"))

                    # Check for critical values
                    if result_data.get('critical_min') and val < float(result_data['critical_min']):
                        errors.append(_("CRITICAL: Result is below critical minimum"))
                    if result_data.get('critical_max') and val > float(result_data['critical_max']):
                        errors.append(_("CRITICAL: Result is above critical maximum"))
                except:
                    pass

        # Check test date
        if result_data.get('test_date'):
            test_date = result_data['test_date']
            if isinstance(test_date, str):
                test_date = fields.Date.from_string(test_date)

            if test_date > date.today():
                errors.append(_("Test date cannot be in the future"))

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'is_critical': any('CRITICAL' in e for e in errors)
        }

    @api.model
    def validate_invoice_data(self, invoice_data):
        """Validate invoice/billing data"""
        errors = []
        warnings = []

        # Check amounts
        if invoice_data.get('amount_total'):
            if invoice_data['amount_total'] < 0:
                errors.append(_("Invoice amount cannot be negative"))
            if invoice_data['amount_total'] > 1000000:
                warnings.append(_("Invoice amount seems unusually high"))

        # Check tax calculation
        if invoice_data.get('amount_tax') and invoice_data.get('amount_untaxed'):
            tax_rate = invoice_data['amount_tax'] / invoice_data['amount_untaxed']
            if tax_rate > 0.5:  # 50% tax
                warnings.append(_("Tax rate seems unusually high"))

        # Check payment terms
        if invoice_data.get('invoice_date') and invoice_data.get('invoice_date_due'):
            invoice_date = fields.Date.from_string(invoice_data['invoice_date'])
            due_date = fields.Date.from_string(invoice_data['invoice_date_due'])

            if due_date < invoice_date:
                errors.append(_("Due date cannot be before invoice date"))

            days_diff = (due_date - invoice_date).days
            if days_diff > 180:
                warnings.append(_("Payment term is more than 180 days"))

        # Check discount
        if invoice_data.get('discount_percentage'):
            if invoice_data['discount_percentage'] < 0:
                errors.append(_("Discount cannot be negative"))
            if invoice_data['discount_percentage'] > 100:
                errors.append(_("Discount cannot exceed 100%"))
            if invoice_data['discount_percentage'] > 50:
                warnings.append(_("Discount is more than 50%"))

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    @api.model
    def validate_email_format(self, email):
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    @api.model
    def validate_phone_format(self, phone):
        """Validate phone number format"""
        # Remove common formatting characters
        cleaned = re.sub(r'[\s\-\(\)\+\.]', '', phone)

        # Check if it's mostly digits
        if not cleaned.isdigit():
            return False

        # Check length (international numbers can be 7-15 digits)
        if len(cleaned) < 7 or len(cleaned) > 15:
            return False

        return True

    @api.model
    def validate_identification(self, id_number, id_type='dni'):
        """Validate identification number based on type"""
        if id_type == 'dni':  # Spanish DNI
            if not re.match(r'^\d{8}[A-Z]$', id_number):
                return False
            # Validate check letter
            letters = 'TRWAGMYFPDXBNJZSQVHLCKE'
            return id_number[-1] == letters[int(id_number[:-1]) % 23]

        elif id_type == 'nie':  # Spanish NIE
            if not re.match(r'^[XYZ]\d{7}[A-Z]$', id_number):
                return False
            # Convert and validate
            nie_digits = {'X': '0', 'Y': '1', 'Z': '2'}
            number = nie_digits[id_number[0]] + id_number[1:-1]
            letters = 'TRWAGMYFPDXBNJZSQVHLCKE'
            return id_number[-1] == letters[int(number) % 23]

        elif id_type == 'passport':
            # Basic passport validation (alphanumeric, 6-20 chars)
            return bool(re.match(r'^[A-Z0-9]{6,20}$', id_number))

        elif id_type == 'ssn':  # US Social Security Number
            return bool(re.match(r'^\d{3}-\d{2}-\d{4}$', id_number))

        return True  # Default to valid for unknown types

    @api.model
    def check_appointment_conflicts(self, patient_id, doctor_id, appointment_date, duration):
        """Check for appointment conflicts"""
        conflicts = []

        # Convert to datetime if needed
        if isinstance(appointment_date, str):
            appointment_date = fields.Datetime.from_string(appointment_date)

        end_date = appointment_date + timedelta(hours=duration)

        # Check doctor availability
        doctor_appointments = self.env['clinic.appointment'].search([
            ('doctor_id', '=', doctor_id),
            ('state', 'not in', ['cancelled', 'no_show']),
            '|',
            '&', ('appointment_date', '>=', appointment_date),
                 ('appointment_date', '<', end_date),
            '&', ('appointment_date', '<', appointment_date),
                 ('appointment_date', '>', appointment_date)  # This checks for overlapping appointments
        ])

        if doctor_appointments:
            conflicts.append(_("Doctor has conflicting appointments"))

        # Check patient conflicts
        patient_appointments = self.env['clinic.appointment'].search([
            ('patient_id', '=', patient_id),
            ('state', 'not in', ['cancelled', 'no_show']),
            '|',
            '&', ('appointment_date', '>=', appointment_date),
                 ('appointment_date', '<', end_date),
            '&', ('appointment_date', '<', appointment_date),
                 ('appointment_date', '>', appointment_date)
        ])

        if patient_appointments:
            conflicts.append(_("Patient has conflicting appointments"))

        return conflicts

    @api.model
    def validate_medical_code(self, code, code_type='icd10'):
        """Validate medical coding (ICD-10, CPT, etc.)"""
        if code_type == 'icd10':
            # ICD-10 format: Letter followed by 2+ digits, optional decimal and more digits
            pattern = r'^[A-Z][0-9]{2}(\.[0-9]{1,4})?$'
            return bool(re.match(pattern, code.upper()))

        elif code_type == 'cpt':
            # CPT codes are 5 digits
            pattern = r'^\d{5}$'
            return bool(re.match(pattern, code))

        elif code_type == 'hcpcs':
            # HCPCS: Letter followed by 4 digits
            pattern = r'^[A-Z]\d{4}$'
            return bool(re.match(pattern, code.upper()))

        elif code_type == 'ndc':
            # NDC: Various formats like 4-4-2, 5-3-2, 5-4-1
            pattern = r'^\d{4,5}-\d{3,4}-\d{1,2}$'
            return bool(re.match(pattern, code))

        return True

    @api.model
    def validate_clinical_values(self, parameter, value, unit=None):
        """Validate clinical parameters are within expected ranges"""
        ranges = {
            'blood_pressure_systolic': (70, 200),
            'blood_pressure_diastolic': (40, 130),
            'heart_rate': (30, 200),
            'temperature_celsius': (35.0, 42.0),
            'temperature_fahrenheit': (95.0, 107.6),
            'respiratory_rate': (8, 40),
            'oxygen_saturation': (70, 100),
            'blood_glucose': (30, 600),
            'weight_kg': (0.5, 500),
            'height_cm': (20, 300),
            'bmi': (10, 70)
        }

        if parameter in ranges:
            min_val, max_val = ranges[parameter]
            try:
                numeric_value = float(value)
                if numeric_value < min_val or numeric_value > max_val:
                    return {
                        'valid': False,
                        'message': _("Value %s is outside expected range (%s - %s)") % (
                            value, min_val, max_val
                        )
                    }
            except ValueError:
                return {
                    'valid': False,
                    'message': _("Value must be numeric")
                }

        return {'valid': True}

    @api.model
    def sanitize_input(self, input_data, field_type='char'):
        """Sanitize user input to prevent injection attacks"""
        if not input_data:
            return input_data

        if field_type == 'html':
            # Remove dangerous HTML tags and attributes
            from odoo.tools import html_sanitize
            return html_sanitize(input_data)

        elif field_type == 'sql':
            # Escape SQL special characters
            return input_data.replace("'", "''").replace(";", "")

        elif field_type == 'filename':
            # Sanitize filename
            return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', input_data)

        elif field_type == 'url':
            # Basic URL validation
            if not re.match(r'^https?://', input_data):
                return ''
            return input_data

        else:
            # Default: remove control characters
            return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', str(input_data))

    @api.model
    def batch_validate(self, model_name, record_ids=None):
        """Batch validate records of a specific model"""
        Model = self.env[model_name]

        if record_ids:
            records = Model.browse(record_ids)
        else:
            records = Model.search([])

        validation_results = []

        for record in records:
            result = {'record_id': record.id, 'errors': [], 'warnings': []}

            # Get validation method for the model
            validate_method = f"validate_{model_name.replace('.', '_')}_data"

            if hasattr(self, validate_method):
                # Convert record to dictionary
                record_data = record.read()[0] if record else {}
                validation = getattr(self, validate_method)(record_data)
                result['errors'] = validation.get('errors', [])
                result['warnings'] = validation.get('warnings', [])

            validation_results.append(result)

        return validation_results