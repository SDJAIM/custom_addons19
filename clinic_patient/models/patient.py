# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
import re


class ClinicPatient(models.Model):
    _name = 'clinic.patient'
    _description = 'Clinic Patient'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _rec_name = 'display_name'
    _order = 'create_date desc'
    
    # ========================
    # Basic Information Fields
    # ========================
    patient_id = fields.Char(
        string='Patient ID',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'),
        help='Unique patient identifier'
    )
    
    name = fields.Char(
        string='Full Name',
        required=True,
        tracking=True,
        help='Patient full name'
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    first_name = fields.Char(string='First Name', tracking=True)
    last_name = fields.Char(string='Last Name', tracking=True)
    middle_name = fields.Char(string='Middle Name')
    
    date_of_birth = fields.Date(
        string='Date of Birth',
        required=True,
        tracking=True,
        help='Patient date of birth'
    )
    
    age = fields.Integer(
        string='Age',
        compute='_compute_age',
        store=True,
        help='Calculated from date of birth'
    )
    
    age_group = fields.Selection([
        ('infant', 'Infant (0-1)'),
        ('child', 'Child (2-12)'),
        ('teen', 'Teen (13-19)'),
        ('adult', 'Adult (20-59)'),
        ('senior', 'Senior (60+)')
    ], string='Age Group', compute='_compute_age', store=True)
    
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_say', 'Prefer not to say')
    ], string='Gender', tracking=True)
    
    # ========================
    # Contact Information
    # ========================
    phone = fields.Char(string='Phone', tracking=True, index=True)
    mobile = fields.Char(string='Mobile', tracking=True, required=True, index=True)
    email = fields.Char(string='Email', tracking=True, index=True)
    whatsapp = fields.Char(string='WhatsApp Number')
    preferred_contact = fields.Selection([
        ('phone', 'Phone'),
        ('mobile', 'Mobile'),
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp')
    ], string='Preferred Contact Method', default='mobile')
    
    # Address
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    country_id = fields.Many2one('res.country', string='Country')
    zip = fields.Char(string='ZIP')
    
    # ========================
    # Medical Information
    # ========================
    blood_group = fields.Selection([
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-')
    ], string='Blood Group')
    
    marital_status = fields.Selection([
        ('single', 'Single'),
        ('married', 'Married'),
        ('divorced', 'Divorced'),
        ('widowed', 'Widowed'),
        ('separated', 'Separated')
    ], string='Marital Status')
    
    occupation = fields.Char(string='Occupation')
    employer = fields.Char(string='Employer')
    
    # Medical History
    medical_history = fields.Text(string='Medical History')
    surgical_history = fields.Text(string='Surgical History')
    medications = fields.Text(string='Current Medications')
    allergies = fields.Text(string='Allergies', tracking=True)
    chronic_conditions = fields.Text(string='Chronic Conditions')
    
    # Dental History
    dental_history = fields.Text(string='Dental History')
    periodontal_status = fields.Selection([
        ('healthy', 'Healthy'),
        ('gingivitis', 'Gingivitis'),
        ('mild_periodontitis', 'Mild Periodontitis'),
        ('moderate_periodontitis', 'Moderate Periodontitis'),
        ('severe_periodontitis', 'Severe Periodontitis')
    ], string='Periodontal Status')
    
    last_dental_visit = fields.Date(string='Last Dental Visit')
    brushing_frequency = fields.Selection([
        ('never', 'Never'),
        ('occasionally', 'Occasionally'),
        ('once_daily', 'Once Daily'),
        ('twice_daily', 'Twice Daily'),
        ('after_meals', 'After Every Meal')
    ], string='Brushing Frequency', default='twice_daily')
    
    flossing_frequency = fields.Selection([
        ('never', 'Never'),
        ('rarely', 'Rarely'),
        ('weekly', 'Weekly'),
        ('daily', 'Daily')
    ], string='Flossing Frequency', default='rarely')
    
    # Lifestyle
    smoking = fields.Selection([
        ('no', 'No'),
        ('yes', 'Yes'),
        ('former', 'Former Smoker'),
        ('passive', 'Passive Smoker')
    ], string='Smoking Status', default='no')
    
    alcohol_consumption = fields.Selection([
        ('never', 'Never'),
        ('occasionally', 'Occasionally'),
        ('moderate', 'Moderate'),
        ('heavy', 'Heavy')
    ], string='Alcohol Consumption', default='never')
    
    exercise_frequency = fields.Selection([
        ('never', 'Never'),
        ('rarely', 'Rarely'),
        ('weekly', 'Weekly'),
        ('daily', 'Daily')
    ], string='Exercise Frequency')
    
    # ========================
    # Emergency Contact
    # ========================
    emergency_contact_name = fields.Char(string='Emergency Contact Name')
    emergency_contact_phone = fields.Char(string='Emergency Contact Phone')
    emergency_contact_relation = fields.Selection([
        ('spouse', 'Spouse'),
        ('parent', 'Parent'),
        ('child', 'Child'),
        ('sibling', 'Sibling'),
        ('friend', 'Friend'),
        ('other', 'Other')
    ], string='Relationship')
    emergency_contact_email = fields.Char(string='Emergency Contact Email')
    
    # ========================
    # Related Records
    # ========================
    partner_id = fields.Many2one(
        'res.partner',
        string='Related Contact',
        ondelete='restrict',
        help='Link to Odoo contact/partner'
    )

    # Multi-company support
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        index=True,
        default=lambda self: self.env.company,
        help='Company this patient belongs to'
    )

    branch_ids = fields.Many2many(
        'clinic.branch',
        'clinic_patient_branch_rel',
        'patient_id',
        'branch_id',
        string='Branches',
        domain="[('company_id', '=', company_id)]",
        help='Branches where this patient is registered'
    )
    
    family_member_ids = fields.One2many(
        comodel_name='clinic.patient.family',
        inverse_name='patient_id',
        string='Family Members'
    )
    
    insurance_ids = fields.One2many(
        'clinic.patient.insurance',
        'patient_id',
        string='Insurance Policies'
    )
    
    # ========================
    # Status and Settings
    # ========================
    active = fields.Boolean(string='Active', default=True)
    
    registration_date = fields.Date(
        string='Registration Date',
        default=fields.Date.today,
        readonly=True
    )
    
    patient_type = fields.Selection([
        ('regular', 'Regular'),
        ('vip', 'VIP'),
        ('insurance', 'Insurance'),
        ('emergency', 'Emergency')
    ], string='Patient Type', default='regular', tracking=True)
    
    privacy_consent = fields.Boolean(
        string='Privacy Consent Given',
        help='Patient has given consent for data processing'
    )
    
    marketing_consent = fields.Boolean(
        string='Marketing Consent',
        help='Patient agrees to receive marketing communications'
    )
    
    portal_access = fields.Boolean(
        string='Portal Access Enabled',
        compute='_compute_portal_access',
        store=True
    )
    
    # ========================
    # Computed Fields
    # ========================
    appointment_count = fields.Integer(
        string='Appointments',
        compute='_compute_appointment_count'
    )
    
    prescription_count = fields.Integer(
        string='Prescriptions',
        compute='_compute_prescription_count'
    )
    
    invoice_count = fields.Integer(
        string='Invoices',
        compute='_compute_invoice_count'
    )
    
    total_spent = fields.Monetary(
        string='Total Spent',
        compute='_compute_total_spent',
        currency_field='currency_id'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    
    last_visit_date = fields.Date(
        string='Last Visit',
        compute='_compute_last_visit'
    )
    
    notes = fields.Text(string='Internal Notes')
    
    # ========================
    # Constraints and Validations
    # ========================
    @api.constrains('patient_id')
    def _check_patient_id_unique(self):
        for record in self:
            if self.search_count([('patient_id', '=', record.patient_id), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_('Patient ID must be unique!'))

    @api.constrains('email')
    def _check_email_unique(self):
        for record in self:
            if record.email and self.search_count([('email', '=', record.email), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_('Email address must be unique!'))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create new patient record(s) with auto-generated ID and partner.

        Automatically generates unique patient IDs and creates corresponding
        res.partner records for portal access and communication.

        Args:
            vals_list (list): List of dictionaries containing patient data.
                Required fields: name, date_of_birth, mobile
                Optional fields: email, phone, address fields, etc.

        Returns:
            recordset: Created patient record(s)

        Raises:
            ValidationError: If required fields are missing or invalid

        Example:
            >>> patient = self.env['clinic.patient'].create({
            ...     'name': 'John Doe',
            ...     'date_of_birth': '1990-01-01',
            ...     'mobile': '+1234567890',
            ...     'email': 'john@example.com'
            ... })
        """
        for vals in vals_list:
            if vals.get('patient_id', _('New')) == _('New'):
                vals['patient_id'] = self.env['ir.sequence'].next_by_code('clinic.patient') or _('New')

            # Auto-create partner if email provided
            if vals.get('email') and not vals.get('partner_id'):
                partner = self.env['res.partner'].create({
                    'name': vals.get('name'),
                    'email': vals.get('email'),
                    'phone': vals.get('phone'),
                    'mobile': vals.get('mobile'),
                    'street': vals.get('street'),
                    'street2': vals.get('street2'),
                    'city': vals.get('city'),
                    'state_id': vals.get('state_id'),
                    'country_id': vals.get('country_id'),
                    'zip': vals.get('zip'),
                    'is_company': False,
                })
                vals['partner_id'] = partner.id

        return super().create(vals_list)
    
    @api.depends('name', 'patient_id')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"[{record.patient_id}] {record.name}" if record.patient_id else record.name
    
    @api.depends('date_of_birth')
    def _compute_age(self):
        today = date.today()
        for record in self:
            if record.date_of_birth:
                age = relativedelta(today, record.date_of_birth).years
                record.age = age
                
                if age <= 1:
                    record.age_group = 'infant'
                elif age <= 12:
                    record.age_group = 'child'
                elif age <= 19:
                    record.age_group = 'teen'
                elif age <= 59:
                    record.age_group = 'adult'
                else:
                    record.age_group = 'senior'
            else:
                record.age = 0
                record.age_group = False
    
    @api.depends('partner_id', 'partner_id.user_ids')
    def _compute_portal_access(self):
        for record in self:
            record.portal_access = bool(
                record.partner_id and 
                record.partner_id.user_ids.filtered(lambda u: u.has_group('base.group_portal'))
            )
    
    def _compute_appointment_count(self):
        # Will be implemented when appointment module is created
        for record in self:
            record.appointment_count = 0
    
    def _compute_prescription_count(self):
        # Will be implemented when prescription module is created
        for record in self:
            record.prescription_count = 0
    
    def _compute_invoice_count(self):
        # Will be implemented when finance module is created
        for record in self:
            record.invoice_count = 0
    
    def _compute_total_spent(self):
        # Will be implemented when finance module is created
        for record in self:
            record.total_spent = 0.0
    
    def _compute_last_visit(self):
        # Will be implemented when appointment module is created
        for record in self:
            record.last_visit_date = False
    
    @api.constrains('email')
    def _check_email(self):
        """Validate email address format.

        Ensures email addresses follow standard format (user@domain.com).

        Raises:
            ValidationError: If email format is invalid
        """
        for record in self:
            if record.email:
                if not re.match(r"[^@]+@[^@]+\.[^@]+", record.email):
                    raise ValidationError(_("Invalid email address format!"))

    @api.constrains('date_of_birth')
    def _check_date_of_birth(self):
        """Validate date of birth is not in the future.

        Raises:
            ValidationError: If date of birth is after today
        """
        for record in self:
            if record.date_of_birth and record.date_of_birth > fields.Date.today():
                raise ValidationError(_("Date of birth cannot be in the future!"))

    @api.constrains('mobile', 'phone', 'whatsapp')
    def _check_phone_numbers(self):
        """Validate phone number formats.

        Checks that phone numbers contain only digits, spaces, and valid symbols.

        Raises:
            ValidationError: If phone number contains invalid characters
        """
        for record in self:
            for number, field_name in [(record.mobile, 'Mobile'), (record.phone, 'Phone'), (record.whatsapp, 'WhatsApp')]:
                if number and not re.match(r"^[\d\s\+\-\(\)]+$", number):
                    raise ValidationError(_(f"{field_name} number contains invalid characters!"))
    
    # ========================
    # Business Methods
    # ========================
    def action_create_portal_user(self):
        """Create portal user for patient"""
        self.ensure_one()
        if not self.partner_id:
            raise ValidationError(_("Please create a related contact first!"))
        
        if not self.email:
            raise ValidationError(_("Email is required to create portal access!"))
        
        # Create portal user
        user_vals = {
            'partner_id': self.partner_id.id,
            'login': self.email,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id])],
        }
        
        user = self.env['res.users'].create(user_vals)
        
        # Send invitation email
        template = self.env.ref('portal.mail_template_data_portal_welcome')
        if template:
            template.send_mail(user.id, force_send=True)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Portal access created and invitation sent!'),
                'type': 'success',
            }
        }
    
    def action_view_appointments(self):
        """View patient appointments"""
        self.ensure_one()
        action = {
            'name': _('Appointments'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.appointment',
            'view_mode': 'tree,form,calendar',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }
        return action
    
    def action_view_prescriptions(self):
        """View patient prescriptions"""
        self.ensure_one()
        action = {
            'name': _('Prescriptions'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.prescription',
            'view_mode': 'tree,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {'default_patient_id': self.id},
        }
        return action
    
    def action_view_invoices(self):
        """View patient invoices"""
        self.ensure_one()
        action = {
            'name': _('Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.partner_id.id)] if self.partner_id else [],
            'context': {'default_partner_id': self.partner_id.id if self.partner_id else False},
        }
        return action
    
    @api.model
    def get_patient_summary(self, patient_id):
        """API method to get patient summary"""
        patient = self.browse(patient_id)
        if not patient.exists():
            return {}
        
        return {
            'id': patient.id,
            'patient_id': patient.patient_id,
            'name': patient.name,
            'age': patient.age,
            'gender': patient.gender,
            'blood_group': patient.blood_group,
            'allergies': patient.allergies,
            'chronic_conditions': patient.chronic_conditions,
            'emergency_contact': {
                'name': patient.emergency_contact_name,
                'phone': patient.emergency_contact_phone,
                'relation': patient.emergency_contact_relation,
            }
        }