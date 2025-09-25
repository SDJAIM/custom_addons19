# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PrescriptionDispenseWizard(models.TransientModel):
    _name = 'clinic.prescription.dispense.wizard'
    _description = 'Prescription Dispensing Wizard'

    prescription_line_id = fields.Many2one(
        'clinic.prescription.line',
        string='Prescription Line',
        required=True
    )

    medication_id = fields.Many2one(
        'clinic.medication',
        string='Medication',
        required=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Product',
        related='medication_id.product_id',
        readonly=True
    )

    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        related='prescription_line_id.patient_id',
        readonly=True
    )

    quantity_to_dispense = fields.Float(
        string='Quantity to Dispense',
        required=True
    )

    quantity_prescribed = fields.Float(
        string='Quantity Prescribed',
        related='prescription_line_id.quantity',
        readonly=True
    )

    quantity_already_dispensed = fields.Float(
        string='Already Dispensed',
        related='prescription_line_id.quantity_dispensed',
        readonly=True
    )

    quantity_remaining = fields.Float(
        string='Remaining',
        compute='_compute_quantity_remaining'
    )

    stock_location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        domain=[('usage', '=', 'internal')],
        required=True
    )

    dest_location_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        domain=[('usage', '=', 'customer')],
        required=True
    )

    needs_lot_selection = fields.Boolean(
        string='Needs Lot Selection',
        related='prescription_line_id.needs_lot_selection',
        readonly=True
    )

    selected_lot_ids = fields.Many2many(
        'stock.lot',
        string='Selected Lots',
        related='prescription_line_id.selected_lot_ids',
        readonly=True
    )

    lot_id = fields.Many2one(
        'stock.lot',
        string='Lot',
        domain="[('product_id', '=', product_id)]"
    )

    suggested_lots = fields.Text(
        string='Suggested Lots (FEFO)',
        related='prescription_line_id.suggested_lots',
        readonly=True
    )

    has_expiring_lots = fields.Boolean(
        string='Has Expiring Lots',
        related='prescription_line_id.has_expiring_lots',
        readonly=True
    )

    expiry_warning = fields.Text(
        string='Expiry Warning',
        related='prescription_line_id.expiry_warning',
        readonly=True
    )

    force_expiry = fields.Boolean(
        string='Force Dispense Expiring',
        default=False,
        help='Allow dispensing of expiring/expired lots'
    )

    notes = fields.Text(
        string='Dispensing Notes'
    )

    @api.depends('quantity_prescribed', 'quantity_already_dispensed')
    def _compute_quantity_remaining(self):
        for wizard in self:
            wizard.quantity_remaining = wizard.quantity_prescribed - wizard.quantity_already_dispensed

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)

        if 'prescription_line_id' in res:
            line = self.env['clinic.prescription.line'].browse(res['prescription_line_id'])
            if line:
                remaining = line.quantity - line.quantity_dispensed
                res.update({
                    'medication_id': line.medication_id.id,
                    'quantity_to_dispense': remaining,
                    'stock_location_id': line.stock_location_id.id if line.stock_location_id else False,
                    'dest_location_id': line.dest_location_id.id if line.dest_location_id else False,
                })

                # Set default locations if not set
                if not res.get('stock_location_id'):
                    warehouse = self.env['stock.warehouse'].search([], limit=1)
                    if warehouse:
                        res['stock_location_id'] = warehouse.lot_stock_id.id

                if not res.get('dest_location_id'):
                    customer_loc = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
                    if customer_loc:
                        res['dest_location_id'] = customer_loc.id

        return res

    @api.constrains('quantity_to_dispense')
    def _check_quantity(self):
        for wizard in self:
            if wizard.quantity_to_dispense <= 0:
                raise ValidationError(_("Quantity to dispense must be greater than zero."))

            if wizard.quantity_to_dispense > wizard.quantity_remaining:
                raise ValidationError(_(
                    "Cannot dispense more than remaining quantity (%s)"
                ) % wizard.quantity_remaining)

    def action_select_lots(self):
        """Open lot selection wizard"""
        self.ensure_one()

        if not self.needs_lot_selection:
            raise UserError(_("This medication does not require lot tracking."))

        return {
            'name': _('Select Lots'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.prescription.lot.selection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_prescription_line_id': self.prescription_line_id.id,
                'default_medication_id': self.medication_id.id,
                'default_required_quantity': self.quantity_to_dispense,
                'default_stock_location_id': self.stock_location_id.id,
            }
        }

    def action_dispense(self):
        """Perform the dispensing"""
        self.ensure_one()

        # Validate expiry warnings
        if self.has_expiring_lots and not self.force_expiry:
            raise UserError(_(
                "Expiring lots detected:\\n%s\\n\\n"
                "Please review the lots or check 'Force Dispense Expiring' to proceed."
            ) % self.expiry_warning)

        # Check if we need lot selection
        if self.needs_lot_selection:
            if not self.selected_lot_ids and not self.lot_id:
                raise UserError(_("Please select lots for dispensing."))

            # Prepare lot quantities
            lot_quantities = []

            if self.selected_lot_ids:
                # Use selected lots (multi-lot dispensing)
                remaining = self.quantity_to_dispense
                for lot in self.selected_lot_ids:
                    if remaining <= 0:
                        break

                    # Get available quantity for this lot
                    available = self._get_lot_available_quantity(lot)
                    take_qty = min(remaining, available)

                    if take_qty > 0:
                        lot_quantities.append({
                            'lot': lot,
                            'quantity': take_qty
                        })
                        remaining -= take_qty

                if remaining > 0:
                    raise UserError(_(
                        "Insufficient stock in selected lots. Still need %s units."
                    ) % remaining)

            elif self.lot_id:
                # Single lot dispensing
                available = self._get_lot_available_quantity(self.lot_id)
                if available < self.quantity_to_dispense:
                    raise UserError(_(
                        "Insufficient stock in lot %s. Available: %s, Required: %s"
                    ) % (self.lot_id.name, available, self.quantity_to_dispense))

                lot_quantities = [{
                    'lot': self.lot_id,
                    'quantity': self.quantity_to_dispense
                }]

        else:
            # No lot tracking required
            lot_quantities = [{
                'lot': None,
                'quantity': self.quantity_to_dispense
            }]

        # Create stock moves
        try:
            moves = self.prescription_line_id.create_stock_move(
                lot_quantities,
                self.stock_location_id.id,
                self.dest_location_id.id
            )

            # Update prescription line
            self.prescription_line_id.write({
                'quantity_dispensed': self.prescription_line_id.quantity_dispensed + self.quantity_to_dispense,
                'last_dispensed_date': fields.Datetime.now(),
            })

            # Add notes if provided
            if self.notes:
                self.prescription_line_id.prescription_id.message_post(
                    body=_("Dispensed %s %s of %s\\nNotes: %s") % (
                        self.quantity_to_dispense,
                        self.prescription_line_id.dose_unit_id.name,
                        self.medication_id.name,
                        self.notes
                    )
                )

            # Return success action
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Medication dispensed successfully.'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            raise UserError(_("Error during dispensing: %s") % str(e))

    def _get_lot_available_quantity(self, lot):
        """Get available quantity for a specific lot"""
        if not lot:
            return 0

        quants = self.env['stock.quant'].search([
            ('lot_id', '=', lot.id),
            ('location_id', '=', self.stock_location_id.id),
            ('product_id', '=', self.product_id.id),
        ])

        return sum(quants.mapped('quantity'))

    def action_view_stock_quants(self):
        """View stock quants for this product"""
        self.ensure_one()

        return {
            'name': _('Stock on Hand'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant',
            'view_mode': 'tree,form',
            'domain': [
                ('product_id', '=', self.product_id.id),
                ('location_id', '=', self.stock_location_id.id),
                ('quantity', '>', 0),
            ],
            'context': {'create': False}
        }