# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ClinicBatchOperationWizard(models.TransientModel):
    _name = 'clinic.batch.operation.wizard'
    _description = 'Batch Operation Wizard'

    operation_type = fields.Selection([
        ('archive', 'Archive Records'),
        ('unarchive', 'Unarchive Records'),
        ('update', 'Update Fields'),
        ('export', 'Export Data'),
        ('delete', 'Delete Records'),
    ], string='Operation Type', required=True, default='archive')

    model_name = fields.Char(
        string='Model Name',
        required=True,
        help='Technical name of the model (e.g., clinic.patient)'
    )

    record_count = fields.Integer(
        string='Record Count',
        compute='_compute_record_count',
        store=False
    )

    @api.depends('model_name')
    def _compute_record_count(self):
        for wizard in self:
            if wizard.model_name:
                try:
                    Model = self.env[wizard.model_name]
                    wizard.record_count = Model.search_count([])
                except KeyError:
                    wizard.record_count = 0
            else:
                wizard.record_count = 0

    def action_execute(self):
        """Execute the batch operation"""
        self.ensure_one()

        if not self.model_name:
            raise UserError(_('Please specify a model name'))

        try:
            Model = self.env[self.model_name]
        except KeyError:
            raise UserError(_('Invalid model name: %s') % self.model_name)

        # Get records based on active_ids if available, otherwise all records
        if self._context.get('active_ids'):
            records = Model.browse(self._context['active_ids'])
        else:
            records = Model.search([])

        if not records:
            raise UserError(_('No records found to process'))

        # Execute operation based on type
        if self.operation_type == 'archive':
            records.write({'active': False})
            message = _('%d records archived successfully') % len(records)
        elif self.operation_type == 'unarchive':
            records.write({'active': True})
            message = _('%d records unarchived successfully') % len(records)
        elif self.operation_type == 'delete':
            count = len(records)
            records.unlink()
            message = _('%d records deleted successfully') % count
        else:
            raise UserError(_('Operation type %s not implemented yet') % self.operation_type)

        # Log the operation
        self.env['clinic.audit.log'].create_log(
            action='write',
            model_name=self.model_name,
            description=f'Batch operation: {self.operation_type} on {len(records)} records'
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }