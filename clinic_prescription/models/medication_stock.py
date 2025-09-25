# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class MedicationStock(models.Model):
    _name = 'clinic.medication.stock'
    _description = 'Medication Stock Management with FEFO'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'expiration_date, lot_number'
    _rec_name = 'display_name'
    
    # Basic Information
    medication_id = fields.Many2one(
        'clinic.medication',
        string='Medication',
        required=True,
        tracking=True,
        index=True,
        ondelete='restrict'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        related='medication_id.product_id',
        store=True,
        readonly=True
    )
    
    lot_number = fields.Char(
        string='Lot/Batch Number',
        required=True,
        tracking=True,
        index=True,
        copy=False
    )
    
    serial_number = fields.Char(
        string='Serial Number',
        index=True,
        copy=False
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    # Dates
    manufacturing_date = fields.Date(
        string='Manufacturing Date',
        required=True,
        tracking=True
    )
    
    expiration_date = fields.Date(
        string='Expiration Date',
        required=True,
        tracking=True,
        index=True
    )
    
    received_date = fields.Date(
        string='Received Date',
        default=fields.Date.context_today,
        required=True,
        tracking=True
    )
    
    # Quantities
    initial_quantity = fields.Float(
        string='Initial Quantity',
        required=True,
        tracking=True,
        digits='Product Unit of Measure'
    )
    
    current_quantity = fields.Float(
        string='Current Quantity',
        compute='_compute_current_quantity',
        store=True,
        digits='Product Unit of Measure'
    )
    
    reserved_quantity = fields.Float(
        string='Reserved Quantity',
        compute='_compute_reserved_quantity',
        store=True,
        digits='Product Unit of Measure'
    )
    
    available_quantity = fields.Float(
        string='Available Quantity',
        compute='_compute_available_quantity',
        store=True,
        digits='Product Unit of Measure'
    )
    
    dispensed_quantity = fields.Float(
        string='Dispensed Quantity',
        compute='_compute_dispensed_quantity',
        store=True,
        digits='Product Unit of Measure'
    )
    
    # Status
    state = fields.Selection([
        ('available', 'Available'),
        ('low', 'Low Stock'),
        ('expired', 'Expired'),
        ('quarantine', 'Quarantine'),
        ('recalled', 'Recalled'),
        ('depleted', 'Depleted'),
    ], string='Status', compute='_compute_state', store=True, tracking=True)
    
    is_expired = fields.Boolean(
        string='Is Expired',
        compute='_compute_is_expired',
        store=True
    )
    
    days_until_expiry = fields.Integer(
        string='Days Until Expiry',
        compute='_compute_days_until_expiry',
        store=True
    )
    
    expiry_alert = fields.Selection([
        ('ok', 'OK'),
        ('warning', 'Warning - Expires Soon'),
        ('critical', 'Critical - Near Expiry'),
        ('expired', 'Expired'),
    ], string='Expiry Alert', compute='_compute_expiry_alert', store=True)
    
    # Location
    location_id = fields.Many2one(
        'stock.location',
        string='Location',
        required=True,
        tracking=True,
        domain=[('usage', '=', 'internal')]
    )
    
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse',
        related='location_id.warehouse_id',
        store=True,
        readonly=True
    )
    
    storage_conditions = fields.Selection(
        related='medication_id.storage_requirements',
        store=True,
        readonly=True
    )
    
    # Supplier Information
    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        domain=[('supplier_rank', '>', 0)],
        tracking=True
    )
    
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order'
    )
    
    invoice_number = fields.Char(
        string='Invoice Number'
    )
    
    # Cost Information
    unit_cost = fields.Float(
        string='Unit Cost',
        digits='Product Price',
        tracking=True
    )
    
    total_value = fields.Float(
        string='Total Value',
        compute='_compute_total_value',
        store=True,
        digits='Product Price'
    )
    
    # Quality Control
    quality_check_done = fields.Boolean(
        string='Quality Check Done',
        default=False,
        tracking=True
    )
    
    quality_check_date = fields.Date(
        string='Quality Check Date'
    )
    
    quality_check_result = fields.Selection([
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('conditional', 'Conditional Pass'),
    ], string='Quality Result')
    
    quality_notes = fields.Text(
        string='Quality Notes'
    )
    
    # Recall Information
    is_recalled = fields.Boolean(
        string='Is Recalled',
        default=False,
        tracking=True
    )
    
    recall_date = fields.Date(
        string='Recall Date'
    )
    
    recall_reason = fields.Text(
        string='Recall Reason'
    )
    
    recall_reference = fields.Char(
        string='Recall Reference'
    )
    
    # Movement History
    stock_move_ids = fields.One2many(
        'stock.move',
        'medication_stock_id',
        string='Stock Movements'
    )
    
    dispensing_ids = fields.One2many(
        'clinic.medication.dispensing',
        'stock_id',
        string='Dispensing History'
    )
    
    # Temperature Monitoring
    temperature_monitored = fields.Boolean(
        string='Temperature Monitored',
        default=False
    )
    
    temperature_log_ids = fields.One2many(
        'clinic.temperature.log',
        'stock_id',
        string='Temperature Logs'
    )
    
    # Notes
    notes = fields.Text(
        string='Notes'
    )
    
    @api.depends('medication_id', 'lot_number')
    def _compute_display_name(self):
        for stock in self:
            if stock.medication_id and stock.lot_number:
                stock.display_name = f"{stock.medication_id.display_name} - Lot: {stock.lot_number}"
            else:
                stock.display_name = stock.lot_number or 'New'
    
    @api.depends('initial_quantity', 'dispensing_ids.quantity')
    def _compute_current_quantity(self):
        for stock in self:
            dispensed = sum(stock.dispensing_ids.mapped('quantity'))
            stock.current_quantity = stock.initial_quantity - dispensed
    
    @api.depends('dispensing_ids.state')
    def _compute_reserved_quantity(self):
        for stock in self:
            reserved_dispensings = stock.dispensing_ids.filtered(
                lambda d: d.state == 'reserved'
            )
            stock.reserved_quantity = sum(reserved_dispensings.mapped('quantity'))
    
    @api.depends('current_quantity', 'reserved_quantity')
    def _compute_available_quantity(self):
        for stock in self:
            stock.available_quantity = stock.current_quantity - stock.reserved_quantity
    
    @api.depends('dispensing_ids.state', 'dispensing_ids.quantity')
    def _compute_dispensed_quantity(self):
        for stock in self:
            dispensed = stock.dispensing_ids.filtered(
                lambda d: d.state == 'dispensed'
            )
            stock.dispensed_quantity = sum(dispensed.mapped('quantity'))
    
    @api.depends('expiration_date')
    def _compute_is_expired(self):
        today = fields.Date.today()
        for stock in self:
            stock.is_expired = stock.expiration_date < today
    
    @api.depends('expiration_date')
    def _compute_days_until_expiry(self):
        today = fields.Date.today()
        for stock in self:
            if stock.expiration_date:
                delta = stock.expiration_date - today
                stock.days_until_expiry = delta.days
            else:
                stock.days_until_expiry = 0
    
    @api.depends('days_until_expiry', 'is_expired')
    def _compute_expiry_alert(self):
        for stock in self:
            if stock.is_expired:
                stock.expiry_alert = 'expired'
            elif stock.days_until_expiry <= 30:
                stock.expiry_alert = 'critical'
            elif stock.days_until_expiry <= 90:
                stock.expiry_alert = 'warning'
            else:
                stock.expiry_alert = 'ok'
    
    @api.depends('current_quantity', 'is_expired', 'is_recalled', 'expiry_alert')
    def _compute_state(self):
        for stock in self:
            if stock.is_recalled:
                stock.state = 'recalled'
            elif stock.is_expired:
                stock.state = 'expired'
            elif stock.current_quantity <= 0:
                stock.state = 'depleted'
            elif stock.current_quantity < 10:  # Low stock threshold
                stock.state = 'low'
            else:
                stock.state = 'available'
    
    @api.depends('current_quantity', 'unit_cost')
    def _compute_total_value(self):
        for stock in self:
            stock.total_value = stock.current_quantity * stock.unit_cost
    
    @api.constrains('manufacturing_date', 'expiration_date')
    def _check_dates(self):
        for stock in self:
            if stock.manufacturing_date >= stock.expiration_date:
                raise ValidationError(_("Expiration date must be after manufacturing date."))
    
    @api.constrains('initial_quantity')
    def _check_quantity(self):
        for stock in self:
            if stock.initial_quantity <= 0:
                raise ValidationError(_("Initial quantity must be greater than zero."))
    
    @api.constrains('lot_number', 'medication_id')
    def _check_unique_lot(self):
        for stock in self:
            duplicate = self.search([
                ('lot_number', '=', stock.lot_number),
                ('medication_id', '=', stock.medication_id.id),
                ('id', '!=', stock.id)
            ])
            if duplicate:
                raise ValidationError(_(
                    "Lot number %s already exists for medication %s"
                ) % (stock.lot_number, stock.medication_id.name))
    
    @api.onchange('medication_id')
    def _onchange_medication_id(self):
        if self.medication_id:
            self.product_id = self.medication_id.product_id
    
    @api.onchange('quality_check_done')
    def _onchange_quality_check_done(self):
        if self.quality_check_done and not self.quality_check_date:
            self.quality_check_date = fields.Date.today()
    
    def action_quarantine(self):
        """Put stock in quarantine"""
        self.ensure_one()
        self.state = 'quarantine'
        
        # Create activity
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            summary=f'Stock quarantined: {self.display_name}',
            user_id=self.env.ref('base.user_admin').id
        )
        
        return True
    
    def action_recall(self):
        """Recall stock"""
        self.ensure_one()
        
        return {
            'name': _('Recall Stock'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.stock.recall.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_stock_id': self.id,
                'default_medication_id': self.medication_id.id,
                'default_lot_number': self.lot_number,
            }
        }
    
    def action_quality_check(self):
        """Perform quality check"""
        self.ensure_one()
        
        return {
            'name': _('Quality Check'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.quality.check.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_stock_id': self.id,
            }
        }
    
    def get_fefo_quantity(self, required_quantity):
        """
        Get available quantity from this stock based on FEFO
        Returns the quantity that can be taken from this stock
        """
        self.ensure_one()
        
        if self.state != 'available':
            return 0.0
        
        return min(required_quantity, self.available_quantity)
    
    def reserve_quantity(self, quantity, prescription_line_id):
        """Reserve quantity for dispensing"""
        self.ensure_one()
        
        if quantity > self.available_quantity:
            raise UserError(_(
                "Cannot reserve %s units. Only %s available in lot %s"
            ) % (quantity, self.available_quantity, self.lot_number))
        
        # Create reservation record
        self.env['clinic.medication.dispensing'].create({
            'stock_id': self.id,
            'prescription_line_id': prescription_line_id,
            'quantity': quantity,
            'state': 'reserved',
        })
        
        return True
    
    def dispense_quantity(self, quantity, prescription_line_id):
        """Dispense quantity from stock"""
        self.ensure_one()
        
        # Check for existing reservation
        reservation = self.env['clinic.medication.dispensing'].search([
            ('stock_id', '=', self.id),
            ('prescription_line_id', '=', prescription_line_id),
            ('state', '=', 'reserved')
        ], limit=1)
        
        if reservation:
            reservation.action_dispense()
        else:
            # Direct dispensing without reservation
            if quantity > self.available_quantity:
                raise UserError(_(
                    "Cannot dispense %s units. Only %s available in lot %s"
                ) % (quantity, self.available_quantity, self.lot_number))
            
            self.env['clinic.medication.dispensing'].create({
                'stock_id': self.id,
                'prescription_line_id': prescription_line_id,
                'quantity': quantity,
                'state': 'dispensed',
                'dispensed_date': fields.Datetime.now(),
            })
        
        return True
    
    @api.model
    def get_fefo_stocks(self, medication_id, required_quantity, location_id=None):
        """
        Get stocks for medication using FEFO principle
        Returns list of (stock, quantity) tuples
        """
        domain = [
            ('medication_id', '=', medication_id),
            ('state', '=', 'available'),
            ('available_quantity', '>', 0),
        ]
        
        if location_id:
            domain.append(('location_id', '=', location_id))
        
        # Order by expiration date (FEFO)
        stocks = self.search(domain, order='expiration_date')
        
        result = []
        remaining = required_quantity
        
        for stock in stocks:
            if remaining <= 0:
                break
            
            take_quantity = min(remaining, stock.available_quantity)
            result.append((stock, take_quantity))
            remaining -= take_quantity
        
        if remaining > 0:
            raise UserError(_(
                "Insufficient stock. Required: %s, Available: %s"
            ) % (required_quantity, required_quantity - remaining))
        
        return result
    
    @api.model
    def check_expiring_stocks(self):
        """Cron job to check for expiring stocks"""
        # Stocks expiring in next 30 days
        expiry_date = fields.Date.today() + timedelta(days=30)
        
        expiring_stocks = self.search([
            ('state', '=', 'available'),
            ('expiration_date', '<=', expiry_date),
            ('expiration_date', '>', fields.Date.today()),
        ])
        
        for stock in expiring_stocks:
            # Create activity for expiring stock
            stock.activity_schedule(
                'mail.mail_activity_data_warning',
                summary=f'Stock expiring soon: {stock.display_name}',
                note=f'Lot {stock.lot_number} expires on {stock.expiration_date}',
                date_deadline=stock.expiration_date,
                user_id=self.env.ref('base.user_admin').id
            )
    
    @api.model
    def auto_quarantine_expired(self):
        """Cron job to automatically quarantine expired stocks"""
        expired_stocks = self.search([
            ('state', '=', 'available'),
            ('expiration_date', '<', fields.Date.today()),
        ])
        
        for stock in expired_stocks:
            stock.action_quarantine()
            _logger.info(f"Auto-quarantined expired stock: {stock.display_name}")
    
    def name_get(self):
        return [(stock.id, stock.display_name) for stock in self]


class MedicationDispensing(models.Model):
    _name = 'clinic.medication.dispensing'
    _description = 'Medication Dispensing Record'
    _order = 'create_date desc'
    
    stock_id = fields.Many2one(
        'clinic.medication.stock',
        string='Stock',
        required=True,
        ondelete='restrict'
    )
    
    prescription_line_id = fields.Many2one(
        'clinic.prescription.line',
        string='Prescription Line',
        required=True,
        ondelete='restrict'
    )
    
    quantity = fields.Float(
        string='Quantity',
        required=True,
        digits='Product Unit of Measure'
    )
    
    state = fields.Selection([
        ('reserved', 'Reserved'),
        ('dispensed', 'Dispensed'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='reserved', required=True)
    
    reserved_date = fields.Datetime(
        string='Reserved Date',
        default=fields.Datetime.now
    )
    
    dispensed_date = fields.Datetime(
        string='Dispensed Date'
    )
    
    dispensed_by = fields.Many2one(
        'res.users',
        string='Dispensed By'
    )
    
    notes = fields.Text(
        string='Notes'
    )
    
    def action_dispense(self):
        """Mark as dispensed"""
        self.ensure_one()
        self.write({
            'state': 'dispensed',
            'dispensed_date': fields.Datetime.now(),
            'dispensed_by': self.env.user.id,
        })
        return True
    
    def action_cancel(self):
        """Cancel reservation"""
        self.ensure_one()
        if self.state == 'dispensed':
            raise UserError(_("Cannot cancel dispensed items."))
        self.state = 'cancelled'
        return True


class TemperatureLog(models.Model):
    _name = 'clinic.temperature.log'
    _description = 'Temperature Log for Medication Storage'
    _order = 'log_datetime desc'
    
    stock_id = fields.Many2one(
        'clinic.medication.stock',
        string='Stock',
        required=True,
        ondelete='cascade'
    )
    
    log_datetime = fields.Datetime(
        string='Date/Time',
        required=True,
        default=fields.Datetime.now
    )
    
    temperature = fields.Float(
        string='Temperature (°C)',
        required=True
    )
    
    humidity = fields.Float(
        string='Humidity (%)'
    )
    
    is_within_range = fields.Boolean(
        string='Within Range',
        compute='_compute_is_within_range',
        store=True
    )
    
    recorded_by = fields.Many2one(
        'res.users',
        string='Recorded By',
        default=lambda self: self.env.user
    )
    
    notes = fields.Text(
        string='Notes'
    )
    
    @api.depends('temperature', 'stock_id.storage_conditions')
    def _compute_is_within_range(self):
        for log in self:
            if not log.stock_id.storage_conditions:
                log.is_within_range = True
            elif log.stock_id.storage_conditions == 'refrigerate':
                log.is_within_range = 2 <= log.temperature <= 8
            elif log.stock_id.storage_conditions == 'freeze':
                log.is_within_range = log.temperature < 0
            elif log.stock_id.storage_conditions == 'cool':
                log.is_within_range = 8 <= log.temperature <= 15
            else:  # room_temp
                log.is_within_range = 15 <= log.temperature <= 25