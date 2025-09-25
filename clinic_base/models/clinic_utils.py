# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import re
import hashlib
import random
import string
from datetime import datetime, timedelta, date
import phonenumbers
import logging

_logger = logging.getLogger(__name__)


class ClinicUtils(models.AbstractModel):
    _name = 'clinic.utils'
    _description = 'Clinic Utility Functions'

    @api.model
    def validate_email(self, email):
        """Validate email format"""
        if not email:
            return False

        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    @api.model
    def validate_phone(self, phone, country_code='US'):
        """Validate phone number format"""
        if not phone:
            return False

        try:
            parsed = phonenumbers.parse(phone, country_code)
            return phonenumbers.is_valid_number(parsed)
        except:
            # Fallback to simple validation
            pattern = r'^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{4,6}$'
            return bool(re.match(pattern, phone))

    @api.model
    def format_phone(self, phone, country_code='US', format_type='INTERNATIONAL'):
        """Format phone number"""
        if not phone:
            return phone

        try:
            parsed = phonenumbers.parse(phone, country_code)
            if format_type == 'INTERNATIONAL':
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            elif format_type == 'NATIONAL':
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
            else:
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except:
            return phone

    @api.model
    def generate_random_password(self, length=12, include_special=True):
        """Generate a secure random password"""
        characters = string.ascii_letters + string.digits
        if include_special:
            characters += string.punctuation

        password = ''.join(random.choice(characters) for _ in range(length))

        # Ensure at least one of each type
        if include_special:
            password = (
                random.choice(string.ascii_uppercase) +
                random.choice(string.ascii_lowercase) +
                random.choice(string.digits) +
                random.choice(string.punctuation) +
                password[4:]
            )

        # Shuffle the password
        password_list = list(password)
        random.shuffle(password_list)
        return ''.join(password_list)

    @api.model
    def calculate_age(self, birth_date, reference_date=None):
        """Calculate age from birth date"""
        if not birth_date:
            return 0

        if isinstance(birth_date, str):
            birth_date = fields.Date.from_string(birth_date)

        reference_date = reference_date or date.today()
        if isinstance(reference_date, str):
            reference_date = fields.Date.from_string(reference_date)

        age = reference_date.year - birth_date.year

        # Check if birthday has occurred this year
        if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
            age -= 1

        return age

    @api.model
    def calculate_bmi(self, weight_kg, height_cm):
        """Calculate Body Mass Index"""
        if not weight_kg or not height_cm or height_cm == 0:
            return 0.0

        height_m = height_cm / 100.0
        bmi = weight_kg / (height_m ** 2)
        return round(bmi, 2)

    @api.model
    def get_bmi_category(self, bmi):
        """Get BMI category"""
        if bmi < 18.5:
            return 'underweight'
        elif bmi < 25:
            return 'normal'
        elif bmi < 30:
            return 'overweight'
        elif bmi < 35:
            return 'obese_i'
        elif bmi < 40:
            return 'obese_ii'
        else:
            return 'obese_iii'

    @api.model
    def get_next_working_day(self, start_date=None, days=1, calendar=None):
        """Get the next working day based on resource calendar"""
        start_date = start_date or fields.Date.today()
        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)

        if not calendar:
            calendar = self.env.company.resource_calendar_id

        current_date = start_date
        working_days_added = 0

        while working_days_added < days:
            current_date += timedelta(days=1)

            # Check if it's a working day
            if calendar:
                work_intervals = calendar._work_intervals_batch(
                    datetime.combine(current_date, datetime.min.time()),
                    datetime.combine(current_date, datetime.max.time())
                )[False]

                if work_intervals:
                    working_days_added += 1
            else:
                # Simple check for weekdays
                if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
                    working_days_added += 1

        return current_date

    @api.model
    def get_time_slots(self, date, duration_minutes=30, start_hour=8, end_hour=18, occupied_slots=None):
        """Generate available time slots for a given date"""
        occupied_slots = occupied_slots or []
        slots = []

        current_time = datetime.combine(date, datetime.min.time()).replace(hour=start_hour)
        end_time = datetime.combine(date, datetime.min.time()).replace(hour=end_hour)

        while current_time < end_time:
            slot_end = current_time + timedelta(minutes=duration_minutes)

            # Check if slot is occupied
            is_occupied = False
            for occupied_start, occupied_end in occupied_slots:
                if (current_time >= occupied_start and current_time < occupied_end) or \
                   (slot_end > occupied_start and slot_end <= occupied_end):
                    is_occupied = True
                    break

            slots.append({
                'start': current_time,
                'end': slot_end,
                'available': not is_occupied,
                'display': f"{current_time.strftime('%H:%M')} - {slot_end.strftime('%H:%M')}"
            })

            current_time = slot_end

        return slots

    @api.model
    def format_currency(self, amount, currency=None, precision=2):
        """Format amount as currency string"""
        if not currency:
            currency = self.env.company.currency_id

        if hasattr(currency, 'symbol'):
            symbol = currency.symbol or currency.name
            position = getattr(currency, 'position', 'before')
        else:
            symbol = '$'
            position = 'before'

        formatted_amount = f"{amount:,.{precision}f}"

        if position == 'after':
            return f"{formatted_amount} {symbol}"
        else:
            return f"{symbol}{formatted_amount}"

    @api.model
    def sanitize_html(self, html_content):
        """Sanitize HTML content to prevent XSS"""
        if not html_content:
            return html_content

        from odoo.tools import html_sanitize
        return html_sanitize(html_content)

    @api.model
    def generate_barcode(self, data, barcode_type='code128'):
        """Generate barcode image"""
        try:
            import barcode
            from barcode.writer import ImageWriter
            import io
            import base64

            barcode_class = barcode.get_barcode_class(barcode_type)
            barcode_instance = barcode_class(data, writer=ImageWriter())

            buffer = io.BytesIO()
            barcode_instance.write(buffer)
            buffer.seek(0)

            return base64.b64encode(buffer.read()).decode('utf-8')
        except ImportError:
            _logger.warning("Barcode library not installed")
            return False

    @api.model
    def generate_qr_code(self, data, size=10):
        """Generate QR code image"""
        try:
            import qrcode
            import io
            import base64

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=size,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)

            return base64.b64encode(buffer.read()).decode('utf-8')
        except ImportError:
            _logger.warning("QRCode library not installed")
            return False

    @api.model
    def encrypt_data(self, data, key=None):
        """
        Encrypt sensitive data using Fernet symmetric encryption.

        Args:
            data (str): The data to encrypt
            key (str): Optional encryption key. If not provided, uses database secret

        Returns:
            str: Base64 encoded encrypted data

        Raises:
            ImportError: If cryptography library is not installed
        """
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
            import base64
        except ImportError:
            _logger.error("cryptography library not installed. Install with: pip install cryptography")
            raise UserError(_("Encryption library not available. Please contact administrator."))

        if not data:
            return ''

        if not key:
            key = self.env['ir.config_parameter'].sudo().get_param('database.secret')

        # Derive a proper encryption key from the provided key
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'clinic_salt_v1',  # In production, use a random salt stored securely
            iterations=100000,
        )
        key_bytes = base64.urlsafe_b64encode(kdf.derive(key.encode()))

        # Create Fernet instance and encrypt
        f = Fernet(key_bytes)
        encrypted = f.encrypt(data.encode())

        return encrypted.decode()

    @api.model
    def decrypt_data(self, encrypted_data, key=None):
        """
        Decrypt data encrypted with encrypt_data method.

        Args:
            encrypted_data (str): The encrypted data to decrypt
            key (str): Optional encryption key. If not provided, uses database secret

        Returns:
            str: The decrypted plaintext data

        Raises:
            ImportError: If cryptography library is not installed
            InvalidToken: If decryption fails (wrong key or corrupted data)
        """
        try:
            from cryptography.fernet import Fernet, InvalidToken
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
            import base64
        except ImportError:
            _logger.error("cryptography library not installed. Install with: pip install cryptography")
            raise UserError(_("Encryption library not available. Please contact administrator."))

        if not encrypted_data:
            return ''

        if not key:
            key = self.env['ir.config_parameter'].sudo().get_param('database.secret')

        # Derive the same encryption key
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'clinic_salt_v1',  # Must match the salt used in encrypt_data
            iterations=100000,
        )
        key_bytes = base64.urlsafe_b64encode(kdf.derive(key.encode()))

        # Create Fernet instance and decrypt
        f = Fernet(key_bytes)

        try:
            decrypted = f.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except InvalidToken:
            raise ValidationError(_("Failed to decrypt data. Invalid key or corrupted data."))

    @api.model
    def calculate_business_days(self, start_date, end_date, exclude_holidays=True):
        """Calculate number of business days between two dates"""
        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)
        if isinstance(end_date, str):
            end_date = fields.Date.from_string(end_date)

        business_days = 0
        current_date = start_date

        while current_date <= end_date:
            if current_date.weekday() < 5:  # Monday = 0, Sunday = 6
                business_days += 1
            current_date += timedelta(days=1)

        # TODO: Subtract holidays if exclude_holidays is True

        return business_days

    @api.model
    def format_medical_record_number(self, number, prefix='MRN'):
        """Format medical record number"""
        if not number:
            return ''

        # Ensure number is string
        number = str(number)

        # Pad with zeros
        padded = number.zfill(8)

        # Format as MRN-0000-0000
        formatted = f"{prefix}-{padded[:4]}-{padded[4:]}"

        return formatted

    @api.model
    def parse_medical_codes(self, code_string, code_type='icd10'):
        """Parse medical codes from string"""
        if not code_string:
            return []

        # Split by common delimiters
        codes = re.split(r'[,;\s]+', code_string)

        # Clean and validate codes
        valid_codes = []
        for code in codes:
            code = code.strip().upper()

            if code_type == 'icd10':
                # ICD-10 format: Letter followed by numbers and optional decimal
                if re.match(r'^[A-Z][0-9]{2}(\.[0-9]{1,4})?$', code):
                    valid_codes.append(code)
            elif code_type == 'cpt':
                # CPT format: 5 digits
                if re.match(r'^[0-9]{5}$', code):
                    valid_codes.append(code)
            else:
                valid_codes.append(code)

        return valid_codes

    @api.model
    def calculate_appointment_duration(self, services):
        """Calculate total appointment duration based on services"""
        total_duration = 0.0

        for service in services:
            if hasattr(service, 'duration'):
                total_duration += service.duration
            else:
                # Default duration
                total_duration += 0.5

        # Round to nearest 15 minutes
        return round(total_duration * 4) / 4

    @api.model
    def get_working_hours_for_date(self, date, resource=None):
        """Get working hours for a specific date and resource"""
        if isinstance(date, str):
            date = fields.Date.from_string(date)

        calendar = resource.calendar_id if resource else self.env.company.resource_calendar_id

        if not calendar:
            # Default hours
            return {'start': 8.0, 'end': 18.0, 'breaks': []}

        # Get work intervals for the date
        start_dt = datetime.combine(date, datetime.min.time())
        end_dt = datetime.combine(date, datetime.max.time())

        intervals = calendar._work_intervals_batch(
            start_dt, end_dt,
            resources=resource
        )[resource.id if resource else False]

        if not intervals:
            return None

        # Convert intervals to hours
        working_hours = {
            'start': intervals[0][0].hour + intervals[0][0].minute / 60.0,
            'end': intervals[-1][1].hour + intervals[-1][1].minute / 60.0,
            'breaks': []
        }

        # Detect breaks
        for i in range(len(intervals) - 1):
            break_start = intervals[i][1]
            break_end = intervals[i + 1][0]

            if break_end > break_start:
                working_hours['breaks'].append({
                    'start': break_start.hour + break_start.minute / 60.0,
                    'end': break_end.hour + break_end.minute / 60.0
                })

        return working_hours

    @api.model
    def validate_nif(self, nif, country_code='ES'):
        """Validate tax identification number"""
        if not nif:
            return False

        nif = nif.upper().strip()

        if country_code == 'ES':
            # Spanish NIF/NIE validation
            if len(nif) != 9:
                return False

            if nif[0] in 'XYZ':
                # NIE
                nie_digits = {'X': '0', 'Y': '1', 'Z': '2'}
                nif = nie_digits[nif[0]] + nif[1:]

            if not nif[:-1].isdigit():
                return False

            letters = 'TRWAGMYFPDXBNJZSQVHLCKE'
            return nif[-1] == letters[int(nif[:-1]) % 23]

        # Add more country validations as needed
        return True

    @api.model
    def generate_unique_code(self, prefix='', length=8, model_name=None, field_name='code'):
        """Generate a unique code"""
        chars = string.ascii_uppercase + string.digits

        while True:
            code = prefix + ''.join(random.choice(chars) for _ in range(length))

            # Check uniqueness if model provided
            if model_name:
                exists = self.env[model_name].search_count([
                    (field_name, '=', code)
                ])
                if not exists:
                    return code
            else:
                return code

    @api.model
    def convert_timezone(self, datetime_value, from_tz='UTC', to_tz=None):
        """Convert datetime between timezones"""
        import pytz

        if not to_tz:
            to_tz = self.env.user.tz or 'UTC'

        if isinstance(datetime_value, str):
            datetime_value = fields.Datetime.from_string(datetime_value)

        # Localize to source timezone
        from_timezone = pytz.timezone(from_tz)
        localized_dt = from_timezone.localize(datetime_value)

        # Convert to target timezone
        to_timezone = pytz.timezone(to_tz)
        converted_dt = localized_dt.astimezone(to_timezone)

        return converted_dt