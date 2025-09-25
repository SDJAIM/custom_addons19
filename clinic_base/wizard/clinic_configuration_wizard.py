# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class ClinicConfigurationWizard(models.TransientModel):
    _name = 'clinic.configuration.wizard'
    _description = 'Clinic Configuration Wizard'

    state = fields.Selection([
        ('general', 'General Settings'),
        ('appointment', 'Appointment Settings'),
        ('billing', 'Billing Settings'),
        ('notification', 'Notification Settings'),
        ('integration', 'Integration Settings'),
        ('summary', 'Configuration Summary')
    ], default='general', string='Configuration Step')

    # ========================
    # General Settings
    # ========================
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    clinic_name = fields.Char(
        string='Clinic Name',
        required=True,
        help='Your clinic or hospital name'
    )

    clinic_type = fields.Selection([
        ('hospital', 'Hospital'),
        ('clinic', 'Clinic'),
        ('dental', 'Dental Clinic'),
        ('specialist', 'Specialist Center'),
        ('diagnostic', 'Diagnostic Center')
    ], string='Facility Type', required=True, default='clinic')

    default_currency_id = fields.Many2one(
        'res.currency',
        string='Default Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    multi_branch = fields.Boolean(
        string='Multiple Branches',
        help='Enable multi-branch support'
    )

    patient_code_sequence = fields.Selection([
        ('auto', 'Automatic (PAT0001, PAT0002...)'),
        ('custom', 'Custom Format'),
        ('manual', 'Manual Entry')
    ], string='Patient Code Format', default='auto')

    # ========================
    # Appointment Settings
    # ========================
    appointment_duration = fields.Float(
        string='Default Appointment Duration',
        default=0.5,
        help='Default duration in hours'
    )

    slot_duration = fields.Integer(
        string='Time Slot Duration',
        default=15,
        help='Duration of each time slot in minutes'
    )

    working_hours_start = fields.Float(
        string='Working Hours Start',
        default=8.0,
        help='Start time (24-hour format)'
    )

    working_hours_end = fields.Float(
        string='Working Hours End',
        default=18.0,
        help='End time (24-hour format)'
    )

    allow_overbooking = fields.Boolean(
        string='Allow Overbooking',
        help='Allow booking multiple appointments in the same time slot'
    )

    auto_confirm_appointments = fields.Boolean(
        string='Auto-Confirm Appointments',
        help='Automatically confirm new appointments'
    )

    appointment_reminder_days = fields.Integer(
        string='Reminder Days Before',
        default=1,
        help='Send reminder X days before appointment'
    )

    enable_online_booking = fields.Boolean(
        string='Enable Online Booking',
        help='Allow patients to book appointments online'
    )

    # ========================
    # Billing Settings
    # ========================
    enable_insurance = fields.Boolean(
        string='Enable Insurance',
        default=True,
        help='Enable insurance claim management'
    )

    default_payment_term_id = fields.Many2one(
        'account.payment.term',
        string='Default Payment Terms'
    )

    auto_create_invoice = fields.Boolean(
        string='Auto-Create Invoice',
        help='Automatically create invoice after appointment completion'
    )

    require_deposit = fields.Boolean(
        string='Require Deposit',
        help='Require deposit for appointment booking'
    )

    deposit_percentage = fields.Float(
        string='Deposit Percentage',
        default=30.0,
        help='Percentage of total amount required as deposit'
    )

    enable_payment_plans = fields.Boolean(
        string='Enable Payment Plans',
        help='Allow patients to pay in installments'
    )

    invoice_grouping = fields.Selection([
        ('appointment', 'One Invoice per Appointment'),
        ('patient_monthly', 'Monthly Invoice per Patient'),
        ('treatment_plan', 'One Invoice per Treatment Plan')
    ], string='Invoice Grouping', default='appointment')

    # ========================
    # Notification Settings
    # ========================
    enable_email_notifications = fields.Boolean(
        string='Email Notifications',
        default=True
    )

    enable_sms_notifications = fields.Boolean(
        string='SMS Notifications'
    )

    enable_whatsapp_notifications = fields.Boolean(
        string='WhatsApp Notifications'
    )

    appointment_confirmation_template = fields.Many2one(
        'mail.template',
        string='Appointment Confirmation Template',
        domain=[('model', '=', 'clinic.appointment')]
    )

    appointment_reminder_template = fields.Many2one(
        'mail.template',
        string='Appointment Reminder Template',
        domain=[('model', '=', 'clinic.appointment')]
    )

    patient_portal_access = fields.Boolean(
        string='Patient Portal Access',
        help='Allow patients to access their records via portal'
    )

    # ========================
    # Integration Settings
    # ========================
    enable_lab_integration = fields.Boolean(
        string='Laboratory Integration',
        help='Enable integration with laboratory systems'
    )

    enable_pharmacy_integration = fields.Boolean(
        string='Pharmacy Integration',
        help='Enable integration with pharmacy systems'
    )

    enable_telemedicine = fields.Boolean(
        string='Telemedicine Support',
        help='Enable video consultation features'
    )

    default_telemedicine_platform = fields.Selection([
        ('zoom', 'Zoom'),
        ('google_meet', 'Google Meet'),
        ('teams', 'Microsoft Teams'),
        ('jitsi', 'Jitsi Meet'),
        ('custom', 'Custom Platform')
    ], string='Telemedicine Platform')

    enable_api_access = fields.Boolean(
        string='API Access',
        help='Enable REST API for external integrations'
    )

    # ========================
    # Methods
    # ========================
    @api.model
    def default_get(self, fields_list):
        """Load current configuration values"""
        res = super().default_get(fields_list)

        # Load from company settings or config parameters
        config_param = self.env['ir.config_parameter'].sudo()
        company = self.env.company

        res.update({
            'clinic_name': company.name,
            'clinic_type': config_param.get_param('clinic.type', 'clinic'),
            'multi_branch': config_param.get_param('clinic.multi_branch', False),
            'appointment_duration': float(config_param.get_param('clinic.appointment_duration', 0.5)),
            'slot_duration': int(config_param.get_param('clinic.slot_duration', 15)),
            'enable_insurance': config_param.get_param('clinic.enable_insurance', True),
            'enable_telemedicine': config_param.get_param('clinic.enable_telemedicine', False),
        })

        return res

    def action_next(self):
        """Move to next configuration step"""
        self.ensure_one()

        # Validate current step
        self._validate_current_step()

        # Determine next state
        states = ['general', 'appointment', 'billing', 'notification', 'integration', 'summary']
        current_index = states.index(self.state)

        if current_index < len(states) - 1:
            self.state = states[current_index + 1]
        else:
            # Apply configuration and close
            self.action_apply()
            return {'type': 'ir.actions.act_window_close'}

        # Return wizard action to stay in wizard
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.configuration.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_previous(self):
        """Move to previous configuration step"""
        self.ensure_one()

        states = ['general', 'appointment', 'billing', 'notification', 'integration', 'summary']
        current_index = states.index(self.state)

        if current_index > 0:
            self.state = states[current_index - 1]

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.configuration.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def _validate_current_step(self):
        """Validate the current step configuration"""
        self.ensure_one()

        if self.state == 'general':
            if not self.clinic_name:
                raise ValidationError(_("Please enter the clinic name."))

        elif self.state == 'appointment':
            if self.working_hours_start >= self.working_hours_end:
                raise ValidationError(_("Working hours end time must be after start time."))
            if self.slot_duration <= 0:
                raise ValidationError(_("Time slot duration must be positive."))

        elif self.state == 'billing':
            if self.require_deposit and self.deposit_percentage <= 0:
                raise ValidationError(_("Deposit percentage must be positive."))

    def action_apply(self):
        """Apply all configuration settings"""
        self.ensure_one()

        config_param = self.env['ir.config_parameter'].sudo()

        # Save General Settings
        self.company_id.name = self.clinic_name
        config_param.set_param('clinic.type', self.clinic_type)
        config_param.set_param('clinic.multi_branch', str(self.multi_branch))
        config_param.set_param('clinic.patient_code_sequence', self.patient_code_sequence)

        # Save Appointment Settings
        config_param.set_param('clinic.appointment_duration', str(self.appointment_duration))
        config_param.set_param('clinic.slot_duration', str(self.slot_duration))
        config_param.set_param('clinic.working_hours_start', str(self.working_hours_start))
        config_param.set_param('clinic.working_hours_end', str(self.working_hours_end))
        config_param.set_param('clinic.allow_overbooking', str(self.allow_overbooking))
        config_param.set_param('clinic.auto_confirm_appointments', str(self.auto_confirm_appointments))
        config_param.set_param('clinic.appointment_reminder_days', str(self.appointment_reminder_days))
        config_param.set_param('clinic.enable_online_booking', str(self.enable_online_booking))

        # Save Billing Settings
        config_param.set_param('clinic.enable_insurance', str(self.enable_insurance))
        config_param.set_param('clinic.auto_create_invoice', str(self.auto_create_invoice))
        config_param.set_param('clinic.require_deposit', str(self.require_deposit))
        config_param.set_param('clinic.deposit_percentage', str(self.deposit_percentage))
        config_param.set_param('clinic.enable_payment_plans', str(self.enable_payment_plans))
        config_param.set_param('clinic.invoice_grouping', self.invoice_grouping)

        # Save Notification Settings
        config_param.set_param('clinic.enable_email_notifications', str(self.enable_email_notifications))
        config_param.set_param('clinic.enable_sms_notifications', str(self.enable_sms_notifications))
        config_param.set_param('clinic.enable_whatsapp_notifications', str(self.enable_whatsapp_notifications))
        config_param.set_param('clinic.patient_portal_access', str(self.patient_portal_access))

        # Save Integration Settings
        config_param.set_param('clinic.enable_lab_integration', str(self.enable_lab_integration))
        config_param.set_param('clinic.enable_pharmacy_integration', str(self.enable_pharmacy_integration))
        config_param.set_param('clinic.enable_telemedicine', str(self.enable_telemedicine))
        config_param.set_param('clinic.default_telemedicine_platform', self.default_telemedicine_platform or '')
        config_param.set_param('clinic.enable_api_access', str(self.enable_api_access))

        # Create default calendar if needed
        self._create_default_calendar()

        # Set up sequences
        self._setup_sequences()

        # Log configuration change
        self.env['clinic.audit.log'].create_log(
            action='settings_change',
            description='Clinic configuration updated via wizard',
            module='clinic_base'
        )

        _logger.info("Clinic configuration applied successfully")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Configuration Applied'),
                'message': _('Clinic configuration has been successfully applied.'),
                'sticky': False,
            }
        }

    def _create_default_calendar(self):
        """Create default working calendar based on settings"""
        self.ensure_one()

        calendar = self.env['resource.calendar'].search([
            ('name', '=', 'Clinic Working Hours'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not calendar:
            calendar = self.env['resource.calendar'].create({
                'name': 'Clinic Working Hours',
                'company_id': self.company_id.id,
                'hours_per_day': self.working_hours_end - self.working_hours_start,
            })

            # Create attendance records
            for day in range(5):  # Monday to Friday
                self.env['resource.calendar.attendance'].create({
                    'calendar_id': calendar.id,
                    'dayofweek': str(day),
                    'hour_from': self.working_hours_start,
                    'hour_to': self.working_hours_end,
                    'name': f"Working hours day {day}"
                })

    def _setup_sequences(self):
        """Set up default sequences for clinic records"""
        self.ensure_one()

        sequences = [
            ('clinic.patient.sequence', 'Patient Code', 'PAT', 5),
            ('clinic.appointment.sequence', 'Appointment Code', 'APT', 5),
            ('clinic.prescription.sequence', 'Prescription Code', 'RX', 5),
            ('clinic.treatment.plan.sequence', 'Treatment Plan', 'TP', 5),
        ]

        for seq_code, seq_name, prefix, padding in sequences:
            sequence = self.env['ir.sequence'].search([
                ('code', '=', seq_code),
                ('company_id', '=', self.company_id.id)
            ], limit=1)

            if not sequence:
                self.env['ir.sequence'].create({
                    'name': seq_name,
                    'code': seq_code,
                    'prefix': prefix,
                    'padding': padding,
                    'company_id': self.company_id.id,
                    'number_next': 1,
                    'number_increment': 1,
                })

    def action_skip(self):
        """Skip wizard and use default settings"""
        return {'type': 'ir.actions.act_window_close'}