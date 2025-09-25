# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class DrugInteraction(models.Model):
    """Model to store known drug interactions"""
    _name = 'clinic.drug.interaction'
    _description = 'Drug Interaction Database'
    _order = 'severity desc, drug1_id, drug2_id'

    drug1_id = fields.Many2one(
        'clinic.medication',
        string='Medication 1',
        required=True,
        index=True
    )

    drug2_id = fields.Many2one(
        'clinic.medication',
        string='Medication 2',
        required=True,
        index=True
    )

    severity = fields.Selection([
        ('contraindicated', 'Contraindicated - Do Not Use Together'),
        ('major', 'Major - Use Alternative if Possible'),
        ('moderate', 'Moderate - Monitor Closely'),
        ('minor', 'Minor - Be Aware'),
    ], string='Severity', required=True, default='moderate')

    interaction_type = fields.Selection([
        ('pharmacodynamic', 'Pharmacodynamic'),
        ('pharmacokinetic', 'Pharmacokinetic'),
        ('unknown', 'Unknown Mechanism'),
    ], string='Type', default='unknown')

    description = fields.Text(
        string='Interaction Description',
        required=True
    )

    clinical_effect = fields.Text(
        string='Clinical Effect',
        help='Expected clinical outcome of this interaction'
    )

    management = fields.Text(
        string='Management',
        help='How to manage this interaction if drugs must be used together'
    )

    documentation = fields.Selection([
        ('established', 'Established'),
        ('probable', 'Probable'),
        ('suspected', 'Suspected'),
        ('possible', 'Possible'),
        ('unlikely', 'Unlikely'),
    ], string='Documentation Level', default='probable')

    references = fields.Text(
        string='References',
        help='Scientific references for this interaction'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    @api.constrains('drug1_id', 'drug2_id')
    def _check_unique_drug_pair(self):
        for record in self:
            if record.drug1_id and record.drug2_id:
                existing = self.search_count([
                    ('drug1_id', '=', record.drug1_id.id),
                    ('drug2_id', '=', record.drug2_id.id),
                    ('id', '!=', record.id)
                ])
                if existing > 0:
                    raise ValidationError(_('This drug interaction already exists!'))

    @api.constrains('drug1_id', 'drug2_id')
    def _check_different_drugs(self):
        for record in self:
            if record.drug1_id == record.drug2_id:
                raise ValidationError(_("A drug cannot interact with itself!"))

    @api.model
    def check_interactions(self, medication_ids):
        """
        Check for interactions between multiple medications
        Returns: list of interaction warnings
        """
        if len(medication_ids) < 2:
            return []

        interactions = []
        medication_ids = list(set(medication_ids))  # Remove duplicates

        # Check all pairs
        for i in range(len(medication_ids)):
            for j in range(i + 1, len(medication_ids)):
                drug1 = medication_ids[i]
                drug2 = medication_ids[j]

                # Search for interactions in both directions
                interaction = self.search([
                    '|',
                    '&', ('drug1_id', '=', drug1), ('drug2_id', '=', drug2),
                    '&', ('drug1_id', '=', drug2), ('drug2_id', '=', drug1),
                    ('active', '=', True)
                ], limit=1)

                if interaction:
                    med1 = self.env['clinic.medication'].browse(drug1)
                    med2 = self.env['clinic.medication'].browse(drug2)

                    interactions.append({
                        'medication_1': med1.display_name,
                        'medication_2': med2.display_name,
                        'severity': interaction.severity,
                        'severity_label': dict(self._fields['severity'].selection)[interaction.severity],
                        'description': interaction.description,
                        'clinical_effect': interaction.clinical_effect,
                        'management': interaction.management,
                        'documentation': interaction.documentation,
                        'is_contraindicated': interaction.severity == 'contraindicated',
                        'is_major': interaction.severity == 'major',
                        'is_moderate': interaction.severity == 'moderate',
                        'is_minor': interaction.severity == 'minor',
                    })

        return interactions

    @api.model
    def get_interaction_summary(self, medication_ids):
        """Get a summary of interactions with severity counts"""
        interactions = self.check_interactions(medication_ids)

        summary = {
            'total': len(interactions),
            'contraindicated': 0,
            'major': 0,
            'moderate': 0,
            'minor': 0,
            'has_contraindicated': False,
            'has_major': False,
            'interactions': interactions
        }

        for interaction in interactions:
            severity = interaction['severity']
            summary[severity] += 1
            if severity == 'contraindicated':
                summary['has_contraindicated'] = True
            elif severity == 'major':
                summary['has_major'] = True

        return summary

    @api.model
    def create_common_interactions(self):
        """Create common drug interactions - to be called during module installation"""

        # This would typically be imported from a drug interaction database
        # For now, we'll create some common examples

        common_interactions = [
            {
                'drug1': 'Warfarin',
                'drug2': 'Aspirin',
                'severity': 'major',
                'description': 'Increased risk of bleeding',
                'clinical_effect': 'Both drugs affect blood clotting. Concurrent use significantly increases bleeding risk.',
                'management': 'Monitor INR closely. Consider reducing warfarin dose. Watch for signs of bleeding.',
            },
            {
                'drug1': 'Simvastatin',
                'drug2': 'Clarithromycin',
                'severity': 'contraindicated',
                'description': 'Increased risk of myopathy and rhabdomyolysis',
                'clinical_effect': 'Clarithromycin inhibits CYP3A4, increasing simvastatin levels significantly.',
                'management': 'Do not use together. Consider alternative antibiotic or hold statin during antibiotic course.',
            },
            {
                'drug1': 'Metformin',
                'drug2': 'Contrast Media',
                'severity': 'major',
                'description': 'Risk of lactic acidosis',
                'clinical_effect': 'Contrast media may impair renal function, leading to metformin accumulation.',
                'management': 'Hold metformin 48 hours before and after contrast. Monitor renal function.',
            },
            {
                'drug1': 'ACE Inhibitors',
                'drug2': 'Potassium Supplements',
                'severity': 'moderate',
                'description': 'Risk of hyperkalemia',
                'clinical_effect': 'Both increase potassium levels, potentially causing dangerous hyperkalemia.',
                'management': 'Monitor potassium levels regularly. Adjust doses as needed.',
            },
        ]

        for interaction_data in common_interactions:
            try:
                # Find or create medications
                drug1 = self.env['clinic.medication'].search([
                    ('name', 'ilike', interaction_data['drug1'])
                ], limit=1)
                drug2 = self.env['clinic.medication'].search([
                    ('name', 'ilike', interaction_data['drug2'])
                ], limit=1)

                if drug1 and drug2:
                    existing = self.search([
                        '|',
                        '&', ('drug1_id', '=', drug1.id), ('drug2_id', '=', drug2.id),
                        '&', ('drug1_id', '=', drug2.id), ('drug2_id', '=', drug1.id),
                    ])

                    if not existing:
                        self.create({
                            'drug1_id': drug1.id,
                            'drug2_id': drug2.id,
                            'severity': interaction_data['severity'],
                            'description': interaction_data['description'],
                            'clinical_effect': interaction_data['clinical_effect'],
                            'management': interaction_data['management'],
                            'interaction_type': 'pharmacokinetic' if 'CYP' in interaction_data.get('clinical_effect', '') else 'pharmacodynamic',
                            'documentation': 'established',
                        })
                        _logger.info(f"Created drug interaction: {drug1.name} - {drug2.name}")

            except Exception as e:
                _logger.error(f"Error creating drug interaction: {e}")
                continue


class Medication(models.Model):
    """Extension to add drug interaction checking"""
    _inherit = 'clinic.medication'

    def check_drug_interactions(self, other_medication_ids):
        """
        Check for interactions between this medication and a list of other medications

        :param other_medication_ids: list of medication IDs to check against
        :return: dictionary with interaction details
        """
        self.ensure_one()

        if not other_medication_ids:
            return {
                'has_interactions': False,
                'interactions': [],
                'summary': {'total': 0}
            }

        # Include this medication in the check
        all_medication_ids = [self.id] + list(other_medication_ids)

        # Get interactions
        DrugInteraction = self.env['clinic.drug.interaction']
        summary = DrugInteraction.get_interaction_summary(all_medication_ids)

        result = {
            'has_interactions': summary['total'] > 0,
            'has_contraindicated': summary['has_contraindicated'],
            'has_major': summary['has_major'],
            'interactions': summary['interactions'],
            'summary': summary,
            'warning_message': False
        }

        # Generate warning message
        if summary['has_contraindicated']:
            result['warning_message'] = _("⚠️ CONTRAINDICATED: These medications should NOT be used together!")
        elif summary['has_major']:
            result['warning_message'] = _("⚠️ MAJOR INTERACTION: Use with extreme caution. Consider alternatives.")
        elif summary['total'] > 0:
            result['warning_message'] = _("⚠️ Drug interactions detected. Please review carefully.")

        return result

    def check_all_interactions(self):
        """Action to check all interactions for this medication"""
        self.ensure_one()

        # Get all other active medications
        other_meds = self.search([('id', '!=', self.id), ('active', '=', True)])

        if not other_meds:
            raise UserError(_("No other medications to check against."))

        # Check interactions
        result = self.check_drug_interactions(other_meds.ids)

        if not result['has_interactions']:
            message = _("✅ No known drug interactions found for %s") % self.display_name
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Drug Interaction Check'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }

        # Return a wizard to show interactions
        return {
            'name': _('Drug Interactions for %s') % self.display_name,
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.drug.interaction.result.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_medication_id': self.id,
                'default_interaction_data': result,
            }
        }