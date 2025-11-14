# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PatientAnonymizeWizard(models.TransientModel):
    """
    Wizard for GDPR-compliant patient data anonymization (TASK-F2-006)

    This wizard allows authorized users to anonymize patient personal data
    while preserving medical records as required by law.
    """
    _name = 'clinic.patient.anonymize.wizard'
    _description = 'Patient Anonymization Wizard'

    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        readonly=True,
        help='Patient whose data will be anonymized'
    )

    patient_name = fields.Char(
        string='Current Patient Name',
        related='patient_id.name',
        readonly=True
    )

    confirm = fields.Boolean(
        string='I confirm anonymization (irreversible action)',
        required=True,
        default=False,
        help='You must check this box to confirm you understand this action cannot be undone'
    )

    reason = fields.Text(
        string='Reason for Anonymization',
        help='Optional: Describe the reason for this GDPR request'
    )

    @api.constrains('confirm')
    def _check_confirmation(self):
        """Ensure user explicitly confirms the action"""
        for wizard in self:
            if not wizard.confirm:
                raise UserError(
                    _('You must confirm the anonymization by checking the confirmation box.\n\n'
                      'This is an irreversible action.')
                )

    def action_anonymize(self):
        """
        Anonymize patient data per GDPR request

        This method:
        1. Validates confirmation
        2. Creates anonymized name (DELETED_USER_XXX)
        3. Replaces all personal identifiable information (PII)
        4. Preserves medical records (legal requirement)
        5. Logs anonymization in chatter
        6. Marks patient as anonymized

        Returns:
            dict: Action to close wizard
        """
        self.ensure_one()

        # Double-check confirmation
        if not self.confirm:
            raise UserError(
                _('Please confirm anonymization by checking the confirmation box.')
            )

        patient = self.patient_id

        # Check if already anonymized
        if patient.gdpr_anonymized:
            raise UserError(
                _('This patient has already been anonymized on %s') % (
                    patient.gdpr_anonymized_date.strftime('%Y-%m-%d %H:%M') if patient.gdpr_anonymized_date else 'N/A'
                )
            )

        # Generate anonymized identifier
        anonymized_name = f"DELETED_USER_{patient.id}"
        anonymized_email = f"{anonymized_name}@deleted.local"

        # Log the anonymization before modifying data
        patient.message_post(
            body=_(
                '<strong>Patient Data Anonymized (GDPR Request)</strong><br/>'
                '<ul>'
                '<li>Original Name: %s</li>'
                '<li>Anonymization Date: %s</li>'
                '<li>Reason: %s</li>'
                '<li>Performed by: %s</li>'
                '</ul>'
                '<p><em>Medical records have been preserved as required by law.</em></p>'
            ) % (
                patient.name,
                fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                self.reason or 'Not specified',
                self.env.user.name
            ),
            subject=_('GDPR Anonymization'),
            message_type='notification'
        )

        # ⚠️ ANONYMIZE PERSONAL DATA
        patient.write({
            # Basic identity
            'name': anonymized_name,
            'first_name': 'REDACTED',
            'last_name': 'REDACTED',
            'middle_name': False,

            # Contact information
            'email': anonymized_email,
            'phone': False,
            'mobile': False,
            'whatsapp': False,

            # Address
            'street': 'REDACTED',
            'street2': False,
            'city': 'REDACTED',
            'state_id': False,
            'zip': False,

            # Emergency contact
            'emergency_contact_name': 'REDACTED',
            'emergency_contact_phone': False,
            'emergency_contact_email': False,
            'emergency_contact_relation': False,

            # Non-essential medical data
            'occupation': False,
            'employer': False,

            # GDPR tracking
            'gdpr_anonymized': True,
            'gdpr_anonymized_date': fields.Datetime.now(),

            # Disable portal access
            'portal_access': False,

            # Revoke consents
            'privacy_consent': False,
            'marketing_consent': False,

            # Note: Medical history, prescriptions, appointments are PRESERVED
            # as required by medical record retention laws
        })

        # Return success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Patient Anonymized'),
                'message': _(
                    'Patient data has been successfully anonymized.\n'
                    'Medical records have been preserved as required by law.'
                ),
                'type': 'success',
                'sticky': False,
            }
        }
