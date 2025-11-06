# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta


class PrescriptionLotSelectionWizard(models.TransientModel):
    _name = 'clinic.prescription.lot.selection.wizard'
    _description = 'Prescription Lot Selection Wizard (FEFO)'

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

    required_quantity = fields.Float(
        string='Required Quantity',
        required=True
    )

    stock_location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        domain=[('usage', '=', 'internal')],
        required=True
    )

    line_ids = fields.One2many(
        'clinic.prescription.lot.selection.line',
        'wizard_id',
        string='Available Lots'
    )

    selected_line_ids = fields.One2many(
        'clinic.prescription.lot.selection.line',
        'wizard_id',
        string='Selected Lots',
        domain=[('selected', '=', True)]
    )

    total_selected_quantity = fields.Float(
        string='Total Selected',
        compute='_compute_totals'
    )

    remaining_quantity = fields.Float(
        string='Remaining',
        compute='_compute_totals'
    )

    fefo_suggestion = fields.Text(
        string='FEFO Suggestion',
        compute='_compute_fefo_suggestion'
    )

    has_expiring_lots = fields.Boolean(
        string='Has Expiring Lots',
        compute='_compute_has_expiring_lots'
    )

    expiry_warning = fields.Text(
        string='Expiry Warning',
        compute='_compute_has_expiring_lots'
    )

    @api.depends('line_ids.selected', 'line_ids.selected_quantity')
    def _compute_totals(self):
        for wizard in self:
            total = sum(wizard.line_ids.filtered('selected').mapped('selected_quantity'))
            wizard.total_selected_quantity = total
            wizard.remaining_quantity = wizard.required_quantity - total

    @api.depends('line_ids')
    def _compute_fefo_suggestion(self):
        for wizard in self:
            if not wizard.line_ids:
                wizard.fefo_suggestion = "No lots available"
                continue

            # Sort by expiration date (FEFO)
            sorted_lots = wizard.line_ids.sorted('expiration_date')

            suggestions = []
            remaining = wizard.required_quantity

            for line in sorted_lots:
                if remaining <= 0:
                    break

                available = line.available_quantity
                take_qty = min(remaining, available)

                if take_qty > 0:
                    exp_str = line.expiration_date.strftime('%Y-%m-%d') if line.expiration_date else 'N/A'
                    suggestions.append(f"• {line.lot_id.name}: {take_qty} (exp: {exp_str})")
                    remaining -= take_qty

            if remaining > 0:
                suggestions.append(f"⚠️ Still need {remaining} units")

            wizard.fefo_suggestion = "\\n".join(suggestions) if suggestions else "No suggestion available"

    @api.depends('line_ids.selected', 'line_ids.expiration_date')
    def _compute_has_expiring_lots(self):
        for wizard in self:
            warnings = []
            has_expiring = False

            alert_days = wizard.medication_id.alert_time if wizard.medication_id else 30
            warning_date = fields.Date.today() + timedelta(days=alert_days)

            for line in wizard.line_ids.filtered('selected'):
                if line.expiration_date:
                    if line.expiration_date <= fields.Date.today():
                        warnings.append(f"❌ Lot {line.lot_id.name} is EXPIRED")
                        has_expiring = True
                    elif line.expiration_date <= warning_date:
                        warnings.append(f"⚠️ Lot {line.lot_id.name} expires in {(line.expiration_date - fields.Date.today()).days} days")
                        has_expiring = True

            wizard.has_expiring_lots = has_expiring
            wizard.expiry_warning = "\\n".join(warnings) if warnings else False

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)

        if 'prescription_line_id' in res:
            line = self.env['clinic.prescription.line'].browse(res['prescription_line_id'])
            if line:
                res.update({
                    'medication_id': line.medication_id.id,
                    'required_quantity': line.quantity - line.quantity_dispensed,
                    'stock_location_id': line.stock_location_id.id if line.stock_location_id else False,
                })

        return res

    @api.onchange('medication_id', 'stock_location_id')
    def _onchange_medication_location(self):
        if self.medication_id and self.medication_id.product_id:
            self._load_available_lots()

    def _load_available_lots(self):
        """Load available lots for the medication"""
        self.line_ids = [(5, 0, 0)]  # Clear existing lines

        if not self.medication_id or not self.medication_id.product_id:
            return

        # Get stock quants for this product
        domain = [
            ('product_id', '=', self.medication_id.product_id.id),
            ('quantity', '>', 0),
            ('lot_id', '!=', False),
        ]

        if self.stock_location_id:
            domain.append(('location_id', '=', self.stock_location_id.id))

        quants = self.env['stock.quant'].search(domain)

        # Group by lot
        lot_quantities = {}
        for quant in quants:
            lot_id = quant.lot_id.id
            if lot_id not in lot_quantities:
                lot_quantities[lot_id] = {
                    'lot': quant.lot_id,
                    'quantity': 0,
                }
            lot_quantities[lot_id]['quantity'] += quant.quantity

        # Create wizard lines
        lines_data = []
        for lot_data in lot_quantities.values():
            lot = lot_data['lot']
            lines_data.append({
                'lot_id': lot.id,
                'available_quantity': lot_data['quantity'],
                # expiration_date will be set via related field (lot_id.life_date)
                'manufacturing_date': lot.use_date,  # use_date = "best before" date
            })

        self.line_ids = [(0, 0, data) for data in lines_data]

    def action_apply_fefo_suggestion(self):
        """Apply FEFO suggestion automatically"""
        self.ensure_one()

        # Clear all selections first
        self.line_ids.write({'selected': False, 'selected_quantity': 0})

        # Sort by expiration date (FEFO)
        sorted_lots = self.line_ids.sorted('expiration_date')

        remaining = self.required_quantity

        for line in sorted_lots:
            if remaining <= 0:
                break

            available = line.available_quantity
            take_qty = min(remaining, available)

            if take_qty > 0:
                line.write({
                    'selected': True,
                    'selected_quantity': take_qty,
                })
                remaining -= take_qty

        return {'type': 'ir.actions.do_nothing'}

    def action_confirm_selection(self):
        """Confirm lot selection and update prescription line"""
        self.ensure_one()

        selected_lines = self.line_ids.filtered('selected')

        if not selected_lines:
            raise UserError(_("Please select at least one lot."))

        total_selected = sum(selected_lines.mapped('selected_quantity'))

        if total_selected < self.required_quantity:
            raise UserError(_(
                "Selected quantity (%s) is less than required (%s)."
            ) % (total_selected, self.required_quantity))

        # Check for expired lots
        expired_lots = selected_lines.filtered(
            lambda l: l.expiration_date and l.expiration_date <= fields.Date.today()
        )

        if expired_lots and not self.env.context.get('force_expired'):
            raise UserError(_(
                "Cannot select expired lots: %s\\n\\n"
                "Please remove expired lots from selection."
            ) % ", ".join(expired_lots.mapped('lot_id.name')))

        # Update prescription line with selected lots
        lot_ids = selected_lines.mapped('lot_id')
        self.prescription_line_id.write({
            'selected_lot_ids': [(6, 0, lot_ids.ids)],
            'lot_id': lot_ids[0].id if lot_ids else False,  # Primary lot
        })

        return {'type': 'ir.actions.act_window_close'}


class PrescriptionLotSelectionLine(models.TransientModel):
    _name = 'clinic.prescription.lot.selection.line'
    _description = 'Prescription Lot Selection Line'
    _order = 'expiration_date, lot_name'

    wizard_id = fields.Many2one(
        'clinic.prescription.lot.selection.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )

    lot_id = fields.Many2one(
        'stock.lot',  # In Odoo 19, this is stock.lot (formerly stock.production.lot)
        string='Lot',
        required=True
    )

    lot_name = fields.Char(
        string='Lot Number',
        related='lot_id.name',
        readonly=True
    )

    available_quantity = fields.Float(
        string='Available Quantity',
        required=True
    )

    selected = fields.Boolean(
        string='Selected',
        default=False
    )

    selected_quantity = fields.Float(
        string='Selected Quantity',
        default=0.0
    )

    expiration_date = fields.Date(
        string='Expiration Date',
        compute='_compute_expiration_date',
        store=False,  # TransientModel - no need to persist
        readonly=True,
        help='Expiration date from lot (uses life_date, use_date, removal_date, or alert_date)'
    )

    @api.depends('lot_id')
    def _compute_expiration_date(self):
        """
        Compute expiration date from lot fields (robust fallback).

        Tries fields in priority order:
        1. life_date (end of life)
        2. use_date (best before)
        3. removal_date (remove from stock)
        4. alert_date (alert date)

        This approach prevents KeyError if expiration dates are not enabled yet.

        Note: Lot fields are Datetime, we convert to Date for display.
        """
        preferred_fields = ('life_date', 'use_date', 'removal_date', 'alert_date')

        for rec in self:
            rec.expiration_date = False
            lot = rec.lot_id  # Define lot variable inside the loop

            if not lot:
                continue

            value = False
            # Try each field in order until we find one that exists and has a value
            for field_name in preferred_fields:
                if field_name in lot._fields:
                    field_value = getattr(lot, field_name, False)
                    if field_value:
                        value = field_value
                        break

            # Convert Datetime to Date (lot fields are Datetime)
            rec.expiration_date = fields.Date.to_date(value) if value else False

    manufacturing_date = fields.Date(
        string='Manufacturing Date'
    )

    days_to_expiry = fields.Integer(
        string='Days to Expiry',
        compute='_compute_days_to_expiry'
    )

    expiry_status = fields.Selection([
        ('ok', 'OK'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('expired', 'Expired'),
    ], string='Expiry Status', compute='_compute_expiry_status')

    @api.depends('expiration_date')
    def _compute_days_to_expiry(self):
        today = fields.Date.today()
        for line in self:
            if line.expiration_date:
                delta = line.expiration_date - today
                line.days_to_expiry = delta.days
            else:
                line.days_to_expiry = 999

    @api.depends('days_to_expiry')
    def _compute_expiry_status(self):
        for line in self:
            if line.days_to_expiry < 0:
                line.expiry_status = 'expired'
            elif line.days_to_expiry <= 7:
                line.expiry_status = 'critical'
            elif line.days_to_expiry <= 30:
                line.expiry_status = 'warning'
            else:
                line.expiry_status = 'ok'

    @api.onchange('selected')
    def _onchange_selected(self):
        if self.selected and self.selected_quantity == 0:
            # Auto-fill with available quantity up to remaining needed
            wizard = self.wizard_id
            if wizard:
                remaining = wizard.required_quantity - wizard.total_selected_quantity
                self.selected_quantity = min(self.available_quantity, remaining)
        elif not self.selected:
            self.selected_quantity = 0

    @api.constrains('selected_quantity', 'available_quantity')
    def _check_selected_quantity(self):
        for line in self:
            if line.selected and line.selected_quantity > line.available_quantity:
                raise ValidationError(_(
                    "Selected quantity (%s) cannot exceed available quantity (%s) for lot %s"
                ) % (line.selected_quantity, line.available_quantity, line.lot_id.name))

            if line.selected and line.selected_quantity <= 0:
                raise ValidationError(_(
                    "Selected quantity must be greater than zero for lot %s"
                ) % line.lot_id.name)