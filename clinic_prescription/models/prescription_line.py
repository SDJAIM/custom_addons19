# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class PrescriptionLine(models.Model):
    _name = 'clinic.prescription.line'
    _description = 'Prescription Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'
    _rec_name = 'medication_id'
    
    # Basic Fields
    prescription_id = fields.Many2one(
        'clinic.prescription',
        string='Prescription',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of medications on prescription'
    )
    
    medication_id = fields.Many2one(
        'clinic.medication',
        string='Medication',
        required=True,
        tracking=True,
        domain=[('active', '=', True)]
    )
    
    generic_name = fields.Char(
        string='Generic Name',
        related='medication_id.generic_name',
        store=True,
        readonly=True
    )
    
    medication_form = fields.Selection(
        related='medication_id.medication_form',
        store=True,
        readonly=True
    )
    
    # Dosage Fields
    dose = fields.Float(
        string='Dose',
        required=True,
        tracking=True,
        help='Amount per dose'
    )
    
    dose_unit_id = fields.Many2one(
        'clinic.dose.unit',
        string='Dose Unit',
        required=True,
        tracking=True
    )
    
    route_id = fields.Many2one(
        'clinic.medication.route',
        string='Route',
        required=True,
        tracking=True,
        help='Route of administration'
    )
    
    frequency_id = fields.Many2one(
        'clinic.frequency',
        string='Frequency',
        required=True,
        tracking=True
    )
    
    frequency_display = fields.Char(
        string='Frequency Display',
        compute='_compute_frequency_display',
        store=True
    )
    
    duration = fields.Integer(
        string='Duration (Days)',
        required=True,
        default=7,
        tracking=True
    )
    
    # Quantity Fields
    quantity = fields.Float(
        string='Total Quantity',
        compute='_compute_quantity',
        store=True,
        readonly=False,
        tracking=True,
        help='Total quantity to dispense'
    )
    
    quantity_dispensed = fields.Float(
        string='Quantity Dispensed',
        default=0.0,
        tracking=True
    )
    
    refills_authorized = fields.Integer(
        string='Refills Authorized',
        default=0,
        tracking=True
    )
    
    refills_remaining = fields.Integer(
        string='Refills Remaining',
        compute='_compute_refills_remaining',
        store=True
    )
    
    # Instructions
    instructions = fields.Text(
        string='Instructions',
        help='Additional instructions for patient'
    )
    
    pharmacy_note = fields.Text(
        string='Pharmacy Note',
        help='Note for pharmacist'
    )
    
    # Special Instructions
    take_with_food = fields.Boolean(
        string='Take with Food',
        default=False
    )
    
    take_on_empty_stomach = fields.Boolean(
        string='Take on Empty Stomach',
        default=False
    )
    
    prn = fields.Boolean(
        string='PRN (As Needed)',
        default=False,
        help='Take as needed'
    )
    
    prn_condition = fields.Char(
        string='PRN Condition',
        help='Condition for PRN use (e.g., for pain, for nausea)'
    )
    
    # Timing
    start_date = fields.Date(
        string='Start Date',
        default=fields.Date.context_today,
        required=True,
        tracking=True
    )
    
    end_date = fields.Date(
        string='End Date',
        compute='_compute_end_date',
        store=True
    )
    
    # Substitution
    allow_substitution = fields.Boolean(
        string='Allow Generic Substitution',
        default=True,
        tracking=True
    )
    
    substitution_reason = fields.Text(
        string='No Substitution Reason',
        help='Reason why substitution is not allowed'
    )
    
    # Status Fields
    is_active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    
    is_dispensed = fields.Boolean(
        string='Dispensed',
        compute='_compute_is_dispensed',
        store=True
    )
    
    discontinue_date = fields.Date(
        string='Discontinue Date',
        tracking=True
    )
    
    discontinue_reason = fields.Text(
        string='Discontinue Reason'
    )
    
    # Related Fields
    patient_id = fields.Many2one(
        related='prescription_id.patient_id',
        store=True,
        readonly=True
    )
    
    doctor_id = fields.Many2one(
        related='prescription_id.doctor_id',
        store=True,
        readonly=True
    )
    
    state = fields.Selection(
        related='prescription_id.state',
        store=True,
        readonly=True
    )
    
    # Stock Management (Enhanced with native integration)
    stock_move_ids = fields.One2many(
        'stock.move',
        'prescription_line_id',
        string='Stock Moves'
    )

    selected_lot_ids = fields.Many2many(
        'stock.lot',
        'prescription_line_lot_rel',
        'prescription_line_id',
        'lot_id',
        string='Selected Lots',
        help='Lots selected for dispensing (FEFO)'
    )

    lot_id = fields.Many2one(
        'stock.lot',
        string='Primary Lot',
        help='Primary lot used for single-lot dispensing'
    )

    suggested_lots = fields.Text(
        string='Suggested Lots (FEFO)',
        compute='_compute_suggested_lots',
        help='FEFO suggested lots for dispensing'
    )

    needs_lot_selection = fields.Boolean(
        string='Needs Lot Selection',
        compute='_compute_needs_lot_selection',
        help='True if medication requires lot tracking'
    )

    has_expiring_lots = fields.Boolean(
        string='Has Expiring Lots',
        compute='_compute_has_expiring_lots',
        help='True if selected lots are expiring soon'
    )

    expiry_warning = fields.Text(
        string='Expiry Warning',
        compute='_compute_has_expiring_lots'
    )

    stock_location_id = fields.Many2one(
        'stock.location',
        string='Stock Location',
        domain=[('usage', '=', 'internal')],
        help='Location to pick from'
    )

    dest_location_id = fields.Many2one(
        'stock.location',
        string='Destination Location',
        domain=[('usage', '=', 'customer')],
        help='Destination location for dispensing'
    )
    
    # Validation Fields
    has_interaction = fields.Boolean(
        string='Has Drug Interaction',
        compute='_compute_has_interaction',
        store=True
    )
    
    interaction_warning = fields.Text(
        string='Interaction Warning',
        compute='_compute_has_interaction',
        store=True
    )
    
    has_allergy_alert = fields.Boolean(
        string='Has Allergy Alert',
        compute='_compute_has_allergy',
        store=True
    )
    
    allergy_warning = fields.Text(
        string='Allergy Warning',
        compute='_compute_has_allergy',
        store=True
    )
    
    # Compliance Tracking
    compliance_rate = fields.Float(
        string='Compliance Rate (%)',
        compute='_compute_compliance_rate',
        store=True
    )
    
    last_dispensed_date = fields.Datetime(
        string='Last Dispensed',
        readonly=True
    )
    
    # Cost Fields
    unit_price = fields.Float(
        string='Unit Price',
        related='medication_id.list_price',
        store=True
    )
    
    total_price = fields.Float(
        string='Total Price',
        compute='_compute_total_price',
        store=True
    )
    
    insurance_coverage = fields.Float(
        string='Insurance Coverage (%)',
        default=0.0
    )
    
    patient_copay = fields.Float(
        string='Patient Copay',
        compute='_compute_patient_copay',
        store=True
    )
    
    @api.depends('frequency_id')
    def _compute_frequency_display(self):
        for line in self:
            if line.frequency_id:
                line.frequency_display = line.frequency_id.display_name
            else:
                line.frequency_display = ''
    
    @api.depends('dose', 'frequency_id', 'duration')
    def _compute_quantity(self):
        for line in self:
            if line.frequency_id and line.duration:
                daily_doses = line.frequency_id.times_per_day
                line.quantity = line.dose * daily_doses * line.duration
            else:
                line.quantity = line.dose
    
    @api.depends('refills_authorized', 'prescription_id.refill_count')
    def _compute_refills_remaining(self):
        for line in self:
            line.refills_remaining = max(0, line.refills_authorized - line.prescription_id.refill_count)
    
    @api.depends('start_date', 'duration')
    def _compute_end_date(self):
        for line in self:
            if line.start_date and line.duration:
                line.end_date = line.start_date + timedelta(days=line.duration)
            else:
                line.end_date = False
    
    @api.depends('quantity', 'quantity_dispensed')
    def _compute_is_dispensed(self):
        for line in self:
            line.is_dispensed = line.quantity_dispensed >= line.quantity
    
    @api.depends('medication_id', 'prescription_id.prescription_line_ids.medication_id')
    def _compute_has_interaction(self):
        # Batch process all lines at once to avoid N+1 queries
        # Prefetch all medications and prescription lines
        all_medications = self.mapped('medication_id')
        all_prescriptions = self.mapped('prescription_id')
        all_prescription_lines = all_prescriptions.mapped('prescription_line_ids')

        # Pre-load all interactions for batch processing
        interaction_cache = {}

        for line in self:
            if not line.medication_id:
                line.has_interaction = False
                line.interaction_warning = False
                continue

            # Use already loaded data instead of new queries
            other_lines = all_prescription_lines.filtered(
                lambda l: l.prescription_id == line.prescription_id and l.id != line.id and l.medication_id
            )
            other_meds = other_lines.mapped('medication_id')

            interactions = []
            for other_med in other_meds:
                # Use cached interaction check
                cache_key = (line.medication_id.id, other_med.id)
                if cache_key not in interaction_cache:
                    interaction_cache[cache_key] = self._check_drug_interaction(line.medication_id, other_med)

                interaction = interaction_cache[cache_key]
                if interaction:
                    interactions.append(interaction)

            if interactions:
                line.has_interaction = True
                line.interaction_warning = '\n'.join(interactions)
            else:
                line.has_interaction = False
                line.interaction_warning = False
    
    @api.depends('medication_id', 'patient_id.allergy_ids')
    def _compute_has_allergy(self):
        for line in self:
            if not line.medication_id or not line.patient_id:
                line.has_allergy_alert = False
                line.allergy_warning = False
                continue
            
            # Check patient allergies
            allergies = []
            for allergy in line.patient_id.allergy_ids:
                if allergy.type == 'medication':
                    # Check if medication contains allergen
                    if self._check_medication_allergy(line.medication_id, allergy):
                        allergies.append(f"Patient allergic to {allergy.name}")
            
            if allergies:
                line.has_allergy_alert = True
                line.allergy_warning = '\n'.join(allergies)
            else:
                line.has_allergy_alert = False
                line.allergy_warning = False
    
    @api.depends('quantity', 'quantity_dispensed', 'duration', 'start_date')
    def _compute_compliance_rate(self):
        for line in self:
            if not line.duration or not line.start_date:
                line.compliance_rate = 0.0
                continue
            
            today = fields.Date.today()
            days_elapsed = (today - line.start_date).days
            
            if days_elapsed <= 0:
                line.compliance_rate = 100.0
            else:
                expected_quantity = (line.quantity / line.duration) * min(days_elapsed, line.duration)
                if expected_quantity > 0:
                    line.compliance_rate = min(100.0, (line.quantity_dispensed / expected_quantity) * 100)
                else:
                    line.compliance_rate = 100.0
    
    @api.depends('quantity', 'unit_price')
    def _compute_total_price(self):
        for line in self:
            line.total_price = line.quantity * line.unit_price
    
    @api.depends('total_price', 'insurance_coverage')
    def _compute_patient_copay(self):
        for line in self:
            coverage_amount = line.total_price * (line.insurance_coverage / 100.0)
            line.patient_copay = line.total_price - coverage_amount
    
    def _check_drug_interaction(self, med1, med2):
        """Check for drug interactions between two medications"""
        # This would connect to a drug interaction database
        # For now, return sample interaction if certain combinations
        dangerous_combos = [
            ('warfarin', 'aspirin'),
            ('metformin', 'contrast'),
            ('ssri', 'maoi'),
        ]
        
        med1_lower = med1.name.lower()
        med2_lower = med2.name.lower()
        
        for combo in dangerous_combos:
            if (combo[0] in med1_lower and combo[1] in med2_lower) or \
               (combo[1] in med1_lower and combo[0] in med2_lower):
                return f"⚠️ Interaction: {med1.name} + {med2.name} - Requires monitoring"
        
        return False
    
    def _check_medication_allergy(self, medication, allergy):
        """Check if medication contains allergen"""
        # This would check medication ingredients against allergy
        # For now, simple name matching
        return allergy.allergen.lower() in medication.name.lower() or \
               allergy.allergen.lower() in (medication.generic_name or '').lower()
    
    @api.constrains('dose')
    def _check_dose(self):
        for line in self:
            if line.dose <= 0:
                raise ValidationError(_("Dose must be greater than zero."))
            
            # Check maximum dose if defined
            if line.medication_id.max_dose and line.dose > line.medication_id.max_dose:
                raise ValidationError(_(
                    "Dose exceeds maximum allowed dose of %s %s for %s"
                ) % (line.medication_id.max_dose, line.dose_unit_id.name, line.medication_id.name))
    
    @api.constrains('take_with_food', 'take_on_empty_stomach')
    def _check_food_instructions(self):
        for line in self:
            if line.take_with_food and line.take_on_empty_stomach:
                raise ValidationError(_("Cannot take medication both with food and on empty stomach."))
    
    @api.constrains('prn', 'prn_condition')
    def _check_prn(self):
        for line in self:
            if line.prn and not line.prn_condition:
                raise ValidationError(_("PRN medications must specify the condition for use."))
    
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for line in self:
            if line.end_date and line.start_date and line.end_date < line.start_date:
                raise ValidationError(_("End date cannot be before start date."))
    
    @api.onchange('medication_id')
    def _onchange_medication_id(self):
        if self.medication_id:
            # Set default dose unit and route
            if self.medication_id.default_dose_unit_id:
                self.dose_unit_id = self.medication_id.default_dose_unit_id
            if self.medication_id.default_route_id:
                self.route_id = self.medication_id.default_route_id

            # Set default dose if available
            if self.medication_id.default_dose:
                self.dose = self.medication_id.default_dose

            # Set default locations
            if not self.stock_location_id:
                # Try to find a pharmacy location
                pharmacy_location = self.env['stock.location'].search([
                    ('usage', '=', 'internal'),
                    ('name', 'ilike', 'pharmacy')
                ], limit=1)
                if pharmacy_location:
                    self.stock_location_id = pharmacy_location
                else:
                    # Fallback to default stock location
                    warehouse = self.env['stock.warehouse'].search([], limit=1)
                    if warehouse:
                        self.stock_location_id = warehouse.lot_stock_id

            if not self.dest_location_id:
                # Set customer location
                customer_location = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
                if customer_location:
                    self.dest_location_id = customer_location

            # Check for interactions and allergies
            self._compute_has_interaction()
            self._compute_has_allergy()
    
    @api.onchange('prn')
    def _onchange_prn(self):
        if not self.prn:
            self.prn_condition = False
    
    @api.onchange('allow_substitution')
    def _onchange_allow_substitution(self):
        if self.allow_substitution:
            self.substitution_reason = False
    
    @api.depends('medication_id', 'medication_id.product_id', 'medication_id.tracking')
    def _compute_needs_lot_selection(self):
        for line in self:
            line.needs_lot_selection = (
                line.medication_id and
                line.medication_id.product_id and
                line.medication_id.tracking in ['lot', 'serial']
            )

    @api.depends('medication_id', 'quantity', 'stock_location_id')
    def _compute_suggested_lots(self):
        for line in self:
            if not line.medication_id or not line.medication_id.product_id:
                line.suggested_lots = False
                continue

            try:
                fefo_lots = line.medication_id.get_fefo_lots(
                    line.quantity,
                    line.stock_location_id.id if line.stock_location_id else None
                )

                if fefo_lots:
                    suggestions = []
                    for lot_info in fefo_lots:
                        lot = lot_info['lot_id']
                        qty = lot_info['quantity']
                        exp_date = lot_info['expiration_date']
                        suggestions.append(f"Lot: {lot.name}, Qty: {qty}, Exp: {exp_date}")

                    line.suggested_lots = "\n".join(suggestions)
                else:
                    line.suggested_lots = "No suitable lots available"
            except Exception as e:
                line.suggested_lots = f"Error: {str(e)}"

    @api.depends('selected_lot_ids', 'selected_lot_ids.expiration_date')
    def _compute_has_expiring_lots(self):
        for line in self:
            warnings = []
            has_expiring = False

            alert_days = line.medication_id.alert_time if line.medication_id else 30
            warning_date = fields.Date.today() + timedelta(days=alert_days)

            for lot in line.selected_lot_ids:
                if lot.expiration_date:
                    if lot.expiration_date <= fields.Date.today():
                        warnings.append(f"❌ Lot {lot.name} is EXPIRED (expired {lot.expiration_date})")
                        has_expiring = True
                    elif lot.expiration_date <= warning_date:
                        warnings.append(f"⚠️ Lot {lot.name} expires soon ({lot.expiration_date})")
                        has_expiring = True

            line.has_expiring_lots = has_expiring
            line.expiry_warning = "\n".join(warnings) if warnings else False

    def action_dispense(self):
        """Dispense medication and update stock"""
        self.ensure_one()

        if self.state not in ['confirmed', 'sent']:
            raise UserError(_("Can only dispense confirmed or sent prescriptions."))

        if self.is_dispensed:
            raise UserError(_("This medication has already been fully dispensed."))

        # Create dispensing wizard
        return {
            'name': _('Dispense Medication'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.prescription.dispense.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_prescription_line_id': self.id,
                'default_medication_id': self.medication_id.id,
                'default_quantity': self.quantity - self.quantity_dispensed,
                'default_suggested_lots': self.suggested_lots,
                'default_needs_lot_selection': self.needs_lot_selection,
            }
        }

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
                'default_prescription_line_id': self.id,
                'default_medication_id': self.medication_id.id,
                'default_quantity': self.quantity,
            }
        }

    def create_stock_move(self, lot_quantities, location_id, dest_location_id):
        """Create stock moves for dispensing with specific lots"""
        self.ensure_one()

        if not self.medication_id.product_id:
            raise UserError(_("No product linked to medication %s") % self.medication_id.name)

        moves = self.env['stock.move']

        for lot_qty in lot_quantities:
            lot = lot_qty['lot']
            quantity = lot_qty['quantity']

            move_vals = {
                'name': f"Dispense {self.medication_id.name}",
                'product_id': self.medication_id.product_id.id,
                'product_uom_qty': quantity,
                'product_uom': self.medication_id.product_id.uom_id.id,
                'location_id': location_id,
                'location_dest_id': dest_location_id,
                'prescription_line_id': self.id,
                'origin': self.prescription_id.prescription_number,
                'restrict_lot_id': lot.id if lot else False,
            }

            move = self.env['stock.move'].create(move_vals)
            move._action_confirm()
            move._action_assign()

            if move.state == 'assigned':
                # Force reserve the specific lot
                if lot:
                    move.move_line_ids.write({
                        'lot_id': lot.id,
                        'qty_done': quantity,
                    })
                else:
                    move.move_line_ids.write({'qty_done': quantity})

                move._action_done()
                moves |= move
            else:
                raise UserError(_(f"Could not reserve stock for lot {lot.name if lot else 'N/A'}"))

        return moves
    
    def action_discontinue(self):
        """Discontinue medication"""
        self.ensure_one()
        
        return {
            'name': _('Discontinue Medication'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.prescription.discontinue.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_prescription_line_id': self.id,
            }
        }
    
    def action_view_stock_moves(self):
        """View related stock moves"""
        self.ensure_one()
        
        return {
            'name': _('Stock Movements'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.move',
            'view_mode': 'tree,form',
            'domain': [('prescription_line_id', '=', self.id)],
            'context': {'create': False}
        }
    
    def get_administration_schedule(self):
        """Generate administration schedule for patient"""
        self.ensure_one()
        
        schedule = []
        if self.frequency_id:
            times = self.frequency_id.get_administration_times()
            for time in times:
                schedule.append({
                    'time': time,
                    'medication': self.medication_id.name,
                    'dose': f"{self.dose} {self.dose_unit_id.name}",
                    'route': self.route_id.name,
                    'instructions': self.instructions or '',
                    'with_food': self.take_with_food,
                    'empty_stomach': self.take_on_empty_stomach,
                })
        
        return schedule
    
    @api.model
    def check_refill_reminders(self):
        """Cron job to check for refill reminders"""
        # Find prescriptions needing refill
        lines = self.search([
            ('is_active', '=', True),
            ('refills_remaining', '>', 0),
            ('quantity_dispensed', '>=', self.quantity * 0.8),  # 80% dispensed
        ])
        
        for line in lines:
            # Create activity for refill reminder
            line.prescription_id.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=f'Refill reminder for {line.medication_id.name}',
                note=f'Patient may need refill for {line.medication_id.name}',
                user_id=line.doctor_id.user_id.id if line.doctor_id.user_id else self.env.user.id
            )
    
    def name_get(self):
        result = []
        for line in self:
            name = f"{line.medication_id.name} - {line.dose} {line.dose_unit_id.name}"
            result.append((line.id, name))
        return result