# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, date, timedelta
from odoo.exceptions import ValidationError, UserError, AccessError


class ClinicPrescription(models.Model):
    _name = 'clinic.prescription'
    _description = 'Medical Prescription'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'prescription_number'
    _order = 'prescription_date desc'
    
    # ========================
    # Basic Information
    # ========================
    prescription_number = fields.Char(
        string='Prescription Number',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'),
        tracking=True
    )
    
    prescription_date = fields.Datetime(
        string='Prescription Date',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        index=True,
        states={'confirmed': [('readonly', True)], 'sent': [('readonly', True)], 'dispensed': [('readonly', True)]}
    )

    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        tracking=True,
        ondelete='restrict',
        index=True,
        states={'confirmed': [('readonly', True)], 'sent': [('readonly', True)], 'dispensed': [('readonly', True)]}
    )

    doctor_id = fields.Many2one(
        'clinic.staff',
        string='Prescribing Doctor',
        required=True,
        default=lambda self: self._get_default_doctor(),
        tracking=True,
        domain="[('staff_type', 'in', ['doctor', 'dentist']), ('state', '=', 'active')]",
        index=True,
        states={'confirmed': [('readonly', True)], 'sent': [('readonly', True)], 'dispensed': [('readonly', True)]}
    )
    
    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Related Appointment',
        help='Appointment this prescription was created from'
    )
    
    treatment_plan_id = fields.Many2one(
        'clinic.treatment.plan',
        string='Treatment Plan',
        help='Treatment plan this prescription belongs to'
    )
    
    # ========================
    # Prescription Type
    # ========================
    prescription_type = fields.Selection([
        ('acute', 'Acute'),
        ('chronic', 'Chronic'),
        ('preventive', 'Preventive'),
        ('prn', 'PRN (As Needed)'),
        ('controlled', 'Controlled Substance')
    ], string='Type', default='acute', required=True, tracking=True)
    
    is_urgent = fields.Boolean(
        string='Urgent',
        default=False,
        tracking=True
    )
    
    # ========================
    # Workflow State (KEY FEATURE)
    # ========================
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('sent', 'Sent to Pharmacy'),
        ('dispensed', 'Dispensed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired')
    ], string='Status', default='draft', tracking=True, index=True)
    
    # ========================
    # Prescription Lines
    # ========================
    prescription_line_ids = fields.One2many(
        'clinic.prescription.line',
        'prescription_id',
        string='Medications',
        states={'confirmed': [('readonly', True)], 'sent': [('readonly', True)], 'dispensed': [('readonly', True)]}
    )
    
    medication_count = fields.Integer(
        string='Medications',
        compute='_compute_counts'
    )
    
    # ========================
    # Validity
    # ========================
    valid_until = fields.Date(
        string='Valid Until',
        compute='_compute_valid_until',
        store=True,
        help='Prescription expiry date'
    )
    
    validity_days = fields.Integer(
        string='Validity (Days)',
        default=30,
        help='Number of days prescription is valid'
    )
    
    is_expired = fields.Boolean(
        string='Expired',
        compute='_compute_is_expired',
        store=True
    )
    
    # ========================
    # Refills
    # ========================
    refills_allowed = fields.Integer(
        string='Refills Allowed',
        default=0,
        states={'confirmed': [('readonly', True)], 'sent': [('readonly', True)], 'dispensed': [('readonly', True)]}
    )
    
    refills_used = fields.Integer(
        string='Refills Used',
        default=0,
        readonly=True
    )
    
    refills_remaining = fields.Integer(
        string='Refills Remaining',
        compute='_compute_refills_remaining',
        store=True
    )
    
    can_refill = fields.Boolean(
        string='Can Refill',
        compute='_compute_can_refill'
    )
    
    # ========================
    # Pharmacy Information
    # ========================
    # Commented out - clinic.pharmacy model not available
    # pharmacy_id = fields.Many2one(
    #     'clinic.pharmacy',
    #     string='Pharmacy',
    #     help='Pharmacy where prescription will be filled'
    # )
    
    sent_to_pharmacy_date = fields.Datetime(
        string='Sent to Pharmacy On',
        readonly=True
    )
    
    dispensed_date = fields.Datetime(
        string='Dispensed On',
        readonly=True
    )
    
    dispensed_by = fields.Char(
        string='Dispensed By',
        readonly=True
    )
    
    # ========================
    # Patient Information Display
    # ========================
    patient_age = fields.Integer(
        related='patient_id.age',
        string='Patient Age'
    )
    
    patient_allergies = fields.Text(
        related='patient_id.allergies',
        string='Patient Allergies'
    )
    
    patient_weight = fields.Float(
        string='Patient Weight (kg)',
        help='For dosage calculations'
    )
    
    # ========================
    # Instructions
    # ========================
    general_instructions = fields.Text(
        string='General Instructions',
        help='General instructions for the patient'
    )
    
    pharmacy_notes = fields.Text(
        string='Notes to Pharmacy',
        help='Special instructions for the pharmacist'
    )
    
    # ========================
    # E-Prescription
    # ========================
    is_electronic = fields.Boolean(
        string='E-Prescription',
        default=True
    )
    
    signature = fields.Binary(
        string='Doctor Signature',
        attachment=True
    )
    
    qr_code = fields.Binary(
        string='QR Code',
        compute='_compute_qr_code',
        help='QR code for prescription verification'
    )
    
    # ========================
    # Warnings and Checks
    # ========================
    has_interactions = fields.Boolean(
        string='Has Drug Interactions',
        compute='_compute_warnings',
        store=True
    )

    has_allergy_warning = fields.Boolean(
        string='Has Allergy Warning',
        compute='_compute_warnings',
        store=True
    )

    interaction_warnings = fields.Text(
        string='Interaction Warnings',
        help='Details of drug-drug interactions'
    )

    allergy_warning = fields.Text(
        string='Allergy Warnings',
        compute='_compute_warnings',
        store=True
    )

    warning_message = fields.Text(
        string='Warning Message',
        help='Summary warning message for display'
    )

    pharmacy_reference = fields.Char(
        string='Pharmacy Reference',
        help='Reference number from pharmacy system'
    )

    pharmacy_sent_date = fields.Datetime(
        string='Sent to Pharmacy',
        help='Date/time when prescription was sent to pharmacy'
    )
    
    # ========================
    # Template
    # ========================
    template_id = fields.Many2one(
        'clinic.prescription.template',
        string='Based on Template'
    )
    
    # ========================
    # Additional Fields
    # ========================
    diagnosis = fields.Text(
        string='Diagnosis',
        help='Diagnosis for this prescription'
    )
    
    icd_code = fields.Char(
        string='ICD Code',
        help='ICD-10 diagnosis code'
    )
    
    notes = fields.Text(
        string='Internal Notes'
    )
    
    # ========================
    # Computed Methods
    # ========================
    @api.model
    def create(self, vals):
        if vals.get('prescription_number', _('New')) == _('New'):
            vals['prescription_number'] = self.env['ir.sequence'].next_by_code('clinic.prescription') or _('New')
        
        # Apply template if specified
        if vals.get('template_id'):
            prescription = super().create(vals)
            prescription._apply_template()
            return prescription
        
        prescription = super().create(vals)
        
        # Check for interactions and allergies
        prescription._check_drug_interactions()
        prescription._check_allergies()
        
        return prescription
    
    def _get_default_doctor(self):
        """Get default doctor from current user's staff record"""
        staff = self.env['clinic.staff'].search([
            ('user_id', '=', self.env.user.id),
            ('staff_type', 'in', ['doctor', 'dentist'])
        ], limit=1)
        return staff.id if staff else False
    
    @api.depends('prescription_line_ids')
    def _compute_counts(self):
        for record in self:
            record.medication_count = len(record.prescription_line_ids)
    
    @api.depends('prescription_date', 'validity_days')
    def _compute_valid_until(self):
        for record in self:
            if record.prescription_date and record.validity_days:
                valid_until = record.prescription_date + timedelta(days=record.validity_days)
                record.valid_until = valid_until.date()
            else:
                record.valid_until = False
    
    @api.depends('valid_until', 'state')
    def _compute_is_expired(self):
        today = date.today()
        for record in self:
            record.is_expired = (
                record.valid_until and 
                record.valid_until < today and 
                record.state not in ['cancelled', 'expired']
            )
    
    @api.depends('refills_allowed', 'refills_used')
    def _compute_refills_remaining(self):
        for record in self:
            record.refills_remaining = max(0, record.refills_allowed - record.refills_used)
    
    @api.depends('refills_remaining', 'is_expired', 'state')
    def _compute_can_refill(self):
        for record in self:
            record.can_refill = (
                record.refills_remaining > 0 and
                not record.is_expired and
                record.state == 'dispensed'
            )
    
    def _compute_qr_code(self):
        """Generate QR code for prescription verification"""
        for record in self:
            # QR code generation would be implemented here
            record.qr_code = False
    
    @api.depends('prescription_line_ids', 'patient_id')
    def _compute_warnings(self):
        """Check for drug interactions and allergies"""
        for record in self:
            record.has_interactions = False
            record.has_allergy_warning = False
            record.interaction_warning = ''
            record.allergy_warning = ''
            
            if record.prescription_line_ids and record.patient_id:
                # Check drug interactions
                interactions = record._check_drug_interactions()
                if interactions:
                    record.has_interactions = True
                    record.interaction_warning = interactions
                
                # Check allergies
                allergy_warnings = record._check_allergies()
                if allergy_warnings:
                    record.has_allergy_warning = True
                    record.allergy_warning = allergy_warnings
    
    # ========================
    # Business Methods
    # ========================
    def _apply_template(self):
        """Apply prescription template"""
        self.ensure_one()
        if not self.template_id:
            return
        
        for template_line in self.template_id.line_ids:
            self.env['clinic.prescription.line'].create({
                'prescription_id': self.id,
                'medication_id': template_line.medication_id.id,
                'dose': template_line.dose,
                'dose_unit_id': template_line.dose_unit_id.id,
                'route_id': template_line.route_id.id,
                'frequency_id': template_line.frequency_id.id,
                'duration_days': template_line.duration_days,
                'quantity': template_line.quantity,
                'instructions': template_line.instructions,
            })
    
    def _check_drug_interactions(self):
        """Check for drug-drug interactions using the drug interaction database"""
        self.ensure_one()

        # Get all medications in this prescription
        medication_ids = self.prescription_line_ids.mapped('medication_id').ids

        if len(medication_ids) < 2:
            # No interactions possible with less than 2 medications
            self.write({
                'has_interactions': False,
                'interaction_warnings': False,
                'warning_message': False
            })
            return False

        # Check interactions using our drug interaction model
        DrugInteraction = self.env['clinic.drug.interaction']
        summary = DrugInteraction.get_interaction_summary(medication_ids)

        # Build warning messages
        warning_messages = []
        critical_warnings = []

        for interaction in summary['interactions']:
            severity_emoji = {
                'contraindicated': '🚫',
                'major': '⚠️',
                'moderate': '⚡',
                'minor': 'ℹ️'
            }.get(interaction['severity'], '')

            warning_msg = f"{severity_emoji} {interaction['medication_1']} + {interaction['medication_2']}: {interaction['description']}"

            if interaction['management']:
                warning_msg += f"\n   → Management: {interaction['management']}"

            warning_messages.append(warning_msg)

            # Track critical warnings
            if interaction['severity'] in ['contraindicated', 'major']:
                critical_warnings.append(interaction)

        # Update prescription with interaction information
        self.write({
            'has_interactions': summary['total'] > 0,
            'interaction_warnings': '\n'.join(warning_messages) if warning_messages else False,
            'warning_message': self._generate_interaction_warning_message(summary)
        })

        # If there are contraindicated interactions, block the prescription
        if summary['has_contraindicated']:
            self.message_post(
                body=_("🚫 CONTRAINDICATED DRUG INTERACTION DETECTED!\n\n%s") % '\n'.join(warning_messages),
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
                author_id=self.env.user.partner_id.id,
            )

            # Create high-priority activity
            self.activity_schedule(
                'mail.mail_activity_data_warning',
                summary=_('Contraindicated drug interaction!'),
                note=_('This prescription contains medications that should NOT be used together. Please review immediately.'),
                user_id=self.staff_id.user_id.id if self.staff_id.user_id else self.env.user.id
            )

            return 'contraindicated'

        # If there are major interactions, warn but allow with confirmation
        elif summary['has_major']:
            self.message_post(
                body=_("⚠️ Major drug interaction detected. Please review carefully:\n\n%s") % '\n'.join(warning_messages),
                message_type='notification',
                subtype_xmlid='mail.mt_comment',
            )
            return 'major'

        # For moderate/minor interactions, just log
        elif summary['total'] > 0:
            self.message_post(
                body=_("Drug interactions detected:\n\n%s") % '\n'.join(warning_messages),
                message_type='notification',
            )
            return 'minor'

        return False

    def _generate_interaction_warning_message(self, summary):
        """Generate a user-friendly warning message based on interaction summary"""
        if not summary['total']:
            return False

        if summary['has_contraindicated']:
            return _("🚫 CONTRAINDICATED: These medications should NOT be used together! (%d interactions)") % summary['total']
        elif summary['has_major']:
            return _("⚠️ MAJOR INTERACTIONS: Use with extreme caution. Consider alternatives. (%d interactions)") % summary['total']
        elif summary['moderate'] > 0:
            return _("⚡ MODERATE INTERACTIONS: Monitor patient closely. (%d interactions)") % summary['total']
        elif summary['minor'] > 0:
            return _("ℹ️ Minor interactions detected. Be aware. (%d interactions)") % summary['total']

        return _("Drug interactions detected (%d)") % summary['total']
    
    def _check_allergies(self):
        """Check medications against patient allergies"""
        self.ensure_one()
        warnings = []
        
        if not self.patient_id or not self.patient_id.allergies:
            return False
        
        patient_allergies = self.patient_id.allergies.lower()
        
        for line in self.prescription_line_ids:
            # Check if medication or its components match allergies
            if line.medication_id.name.lower() in patient_allergies:
                warnings.append(f"Patient may be allergic to {line.medication_id.name}")
            
            # Check active ingredients
            if line.medication_id.active_ingredient:
                if line.medication_id.active_ingredient.lower() in patient_allergies:
                    warnings.append(f"Patient may be allergic to {line.medication_id.active_ingredient} in {line.medication_id.name}")
        
        return '\n'.join(warnings) if warnings else False
    
    # ========================
    # Workflow Actions
    # ========================
    def action_confirm(self):
        """Confirm prescription (doctor signature)"""
        for record in self:
            if record.state != 'draft':
                raise UserError(_('Only draft prescriptions can be confirmed.'))
            
            if not record.prescription_line_ids:
                raise UserError(_('Please add at least one medication.'))
            
            # Check if doctor has permission
            if record.doctor_id.user_id != self.env.user and not self.env.user.has_group('clinic_prescription.group_prescription_manager'):
                raise AccessError(_('Only the prescribing doctor can confirm this prescription.'))
            
            # Final checks
            if record.has_interactions and not self.env.context.get('force_confirm'):
                raise UserError(_(
                    'Drug interactions detected:\n%s\n\n'
                    'Please review and modify the prescription or force confirm if appropriate.'
                ) % record.interaction_warning)
            
            if record.has_allergy_warning and not self.env.context.get('force_confirm'):
                raise UserError(_(
                    'Allergy warnings detected:\n%s\n\n'
                    'Please review and modify the prescription or force confirm if appropriate.'
                ) % record.allergy_warning)
            
            record.state = 'confirmed'
            
            # Log the confirmation
            record.message_post(
                body=_('Prescription confirmed by %s') % self.env.user.name,
                subject=_('Prescription Confirmed')
            )
    
    def action_send_to_pharmacy(self):
        """Send prescription to pharmacy"""
        for record in self:
            if record.state != 'confirmed':
                raise UserError(_('Only confirmed prescriptions can be sent to pharmacy.'))
            
            # Commented out - pharmacy_id field disabled
            # if not record.pharmacy_id and record.is_electronic:
            #     raise UserError(_('Please select a pharmacy for electronic prescription.'))
            
            record.write({
                'state': 'sent',
                'sent_to_pharmacy_date': fields.Datetime.now()
            })
            
            # Send to pharmacy (integration would go here)
            record._send_to_pharmacy()
            
            # Notify patient
            record._notify_patient_prescription_sent()
    
    def action_dispense(self):
        """Mark prescription as dispensed"""
        for record in self:
            if record.state != 'sent':
                raise UserError(_('Only sent prescriptions can be marked as dispensed.'))
            
            # Check FEFO stock if integrated
            for line in record.prescription_line_ids:
                line.action_dispense()
            
            record.write({
                'state': 'dispensed',
                'dispensed_date': fields.Datetime.now(),
                'dispensed_by': self.env.user.name
            })
    
    def action_cancel(self):
        """Cancel prescription"""
        for record in self:
            if record.state in ['dispensed']:
                raise UserError(_('Dispensed prescriptions cannot be cancelled.'))
            
            record.state = 'cancelled'
    
    def action_refill(self):
        """Create refill prescription"""
        self.ensure_one()
        
        if not self.can_refill:
            raise UserError(_('This prescription cannot be refilled.'))
        
        # Create new prescription as refill
        refill = self.copy({
            'prescription_date': fields.Datetime.now(),
            'state': 'draft',
            'refills_allowed': 0,
            'refills_used': 0,
        })
        
        # Update original prescription
        self.refills_used += 1
        
        # Link refill to original
        refill.message_post(
            body=_('Refill of prescription %s') % self.prescription_number,
            subject=_('Prescription Refill')
        )
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.prescription',
            'res_id': refill.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_print(self):
        """Print prescription using QWeb report"""
        self.ensure_one()
        return self.env.ref('clinic_prescription.action_report_prescription').report_action(self)
    
    def action_send_email(self):
        """Send prescription by email"""
        self.ensure_one()
        
        template = self.env.ref('clinic_prescription.email_template_prescription', False)
        if template:
            template.send_mail(self.id, force_send=True)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Prescription sent by email.'),
                'type': 'success',
            }
        }
    
    def _send_to_pharmacy(self):
        """Send prescription to pharmacy system"""
        self.ensure_one()

        if self.state != 'confirmed':
            raise UserError(_("Only confirmed prescriptions can be sent to pharmacy."))

        # Prepare prescription data
        prescription_data = {
            'prescription_number': self.name,
            'patient': {
                'name': self.patient_id.name,
                'birth_date': str(self.patient_id.birth_date) if self.patient_id.birth_date else None,
                'phone': self.patient_id.phone,
                'email': self.patient_id.email,
                'insurance_number': self.patient_id.insurance_number if hasattr(self.patient_id, 'insurance_number') else None,
            },
            'prescriber': {
                'name': self.staff_id.name,
                'license': self.staff_id.license_number if hasattr(self.staff_id, 'license_number') else None,
                'phone': self.staff_id.phone,
                'email': self.staff_id.email,
            },
            'prescription_date': str(self.prescription_date),
            'valid_until': str(self.valid_until),
            'medications': [],
            'pharmacy_notes': self.pharmacy_notes or '',
        }

        # Add medication details
        for line in self.prescription_line_ids:
            medication_info = {
                'medication': line.medication_id.display_name,
                'generic_name': line.medication_id.generic_name,
                'strength': line.medication_id.strength,
                'dose': line.dose,
                'dose_unit': line.dose_unit_id.name if line.dose_unit_id else '',
                'route': line.route_id.name if line.route_id else '',
                'frequency': line.frequency_id.name if line.frequency_id else '',
                'duration': line.duration,
                'quantity': line.quantity,
                'refills': line.refills,
                'instructions': line.instructions,
                'generic_ok': line.generic_ok,
            }
            prescription_data['medications'].append(medication_info)

        # Get pharmacy API configuration
        IrConfig = self.env['ir.config_parameter'].sudo()
        pharmacy_api_url = IrConfig.get_param('clinic.pharmacy.api.url')
        pharmacy_api_key = IrConfig.get_param('clinic.pharmacy.api.key')

        if pharmacy_api_url and pharmacy_api_key:
            try:
                import requests
                import json

                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {pharmacy_api_key}'
                }

                response = requests.post(
                    f"{pharmacy_api_url}/prescriptions",
                    headers=headers,
                    data=json.dumps(prescription_data),
                    timeout=30
                )

                if response.status_code == 200:
                    result = response.json()
                    # Update prescription with pharmacy reference
                    self.write({
                        'pharmacy_reference': result.get('reference_number'),
                        'pharmacy_sent_date': fields.Datetime.now(),
                        'state': 'sent',
                    })

                    # Notify patient
                    self._notify_patient_prescription_sent()

                    # Log success
                    self.message_post(
                        body=_("Prescription sent to pharmacy successfully. Reference: %s") % result.get('reference_number')
                    )

                    return True
                else:
                    raise UserError(_("Failed to send prescription to pharmacy. Status: %s") % response.status_code)

            except requests.exceptions.RequestException as e:
                _logger.error(f"Error sending prescription to pharmacy: {str(e)}")
                raise UserError(_("Failed to connect to pharmacy system. Please try again later."))
        else:
            # If no API configured, just mark as sent and create activity
            self.write({
                'state': 'sent',
                'pharmacy_sent_date': fields.Datetime.now(),
            })

            # Create manual task for pharmacy
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Send prescription to pharmacy'),
                note=_('Prescription needs to be manually sent to pharmacy:\n%s') % prescription_data,
                user_id=self.env.user.id
            )

            # Still notify patient
            self._notify_patient_prescription_sent()

            return True

    def _notify_patient_prescription_sent(self):
        """Notify patient that prescription was sent to pharmacy"""
        self.ensure_one()

        if not self.patient_id:
            return

        # Try to send via WhatsApp if available
        if self.env['ir.module.module'].search([('name', '=', 'clinic_integrations_whatsapp'), ('state', '=', 'installed')]):
            try:
                whatsapp_msg = self.env['clinic.whatsapp.message'].sudo()
                template = self.env.ref('clinic_prescription.whatsapp_prescription_sent', raise_if_not_found=False)

                if template and self.patient_id.phone:
                    whatsapp_msg.create({
                        'phone': self.patient_id.phone,
                        'message': template.body % {
                            'patient_name': self.patient_id.name,
                            'prescription_number': self.name,
                            'pharmacy_reference': self.pharmacy_reference or 'N/A',
                            'valid_until': self.valid_until,
                        },
                        'res_model': 'clinic.prescription',
                        'res_id': self.id,
                    }).send()
            except Exception as e:
                _logger.warning(f"Could not send WhatsApp notification: {str(e)}")

        # Send email notification
        if self.patient_id.email:
            try:
                template = self.env.ref('clinic_prescription.email_prescription_sent', raise_if_not_found=False)
                if template:
                    template.send_mail(self.id, force_send=True)
                else:
                    # Create simple email if no template
                    mail_values = {
                        'subject': _('Prescription Sent to Pharmacy - %s') % self.name,
                        'email_to': self.patient_id.email,
                        'email_from': self.env.company.email or 'noreply@clinic.com',
                        'body_html': f"""
                        <p>Dear {self.patient_id.name},</p>
                        <p>Your prescription <b>{self.name}</b> has been sent to the pharmacy.</p>
                        <p>Details:</p>
                        <ul>
                            <li>Prescription Number: {self.name}</li>
                            <li>Valid Until: {self.valid_until}</li>
                            <li>Pharmacy Reference: {self.pharmacy_reference or 'Will be provided by pharmacy'}</li>
                        </ul>
                        <p>The pharmacy will contact you when your medication is ready for pickup.</p>
                        <p>Best regards,<br/>
                        {self.env.company.name}</p>
                        """,
                        'auto_delete': True,
                    }
                    self.env['mail.mail'].create(mail_values).send()

            except Exception as e:
                _logger.warning(f"Could not send email notification: {str(e)}")

        # Create a note in the prescription
        self.message_post(
            body=_("Patient notified about prescription being sent to pharmacy"),
            message_type='notification',
        )
    
    @api.model
    def check_expired_prescriptions(self):
        """Cron job to mark expired prescriptions"""
        expired = self.search([
            ('valid_until', '<', date.today()),
            ('state', 'not in', ['cancelled', 'expired', 'dispensed'])
        ])
        
        expired.write({'state': 'expired'})