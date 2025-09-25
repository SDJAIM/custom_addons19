# -*- coding: utf-8 -*-
from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    prescription_line_id = fields.Many2one(
        'clinic.prescription.line',
        string='Prescription Line',
        help='Prescription line this move relates to',
        index=True
    )

    prescription_id = fields.Many2one(
        'clinic.prescription',
        string='Prescription',
        related='prescription_line_id.prescription_id',
        store=True,
        readonly=True
    )

    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        related='prescription_line_id.patient_id',
        store=True,
        readonly=True
    )

    medication_id = fields.Many2one(
        'clinic.medication',
        string='Medication',
        related='prescription_line_id.medication_id',
        store=True,
        readonly=True
    )

    is_prescription_dispense = fields.Boolean(
        string='Is Prescription Dispense',
        compute='_compute_is_prescription_dispense',
        store=True
    )

    def _compute_is_prescription_dispense(self):
        for move in self:
            move.is_prescription_dispense = bool(move.prescription_line_id)