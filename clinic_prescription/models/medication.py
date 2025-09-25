# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class Medication(models.Model):
    _name = 'clinic.medication'
    _description = 'Medication'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'image.mixin']
    _order = 'name'
    _rec_name = 'display_name'
    
    # Basic Information
    name = fields.Char(
        string='Brand Name',
        required=True,
        tracking=True,
        index=True
    )
    
    generic_name = fields.Char(
        string='Generic Name',
        required=True,
        tracking=True,
        index=True
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    code = fields.Char(
        string='Code',
        index=True,
        copy=False
    )
    
    barcode = fields.Char(
        string='Barcode',
        copy=False,
        index=True
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    
    # Classification
    medication_type = fields.Selection([
        ('prescription', 'Prescription'),
        ('otc', 'Over-the-Counter'),
        ('controlled', 'Controlled Substance'),
        ('sample', 'Sample'),
        ('compound', 'Compound'),
    ], string='Type', default='prescription', required=True, tracking=True)
    
    controlled_schedule = fields.Selection([
        ('I', 'Schedule I'),
        ('II', 'Schedule II'),
        ('III', 'Schedule III'),
        ('IV', 'Schedule IV'),
        ('V', 'Schedule V'),
    ], string='Controlled Schedule', tracking=True)
    
    therapeutic_class = fields.Char(
        string='Therapeutic Class',
        help='e.g., Antibiotic, Analgesic, Antihypertensive'
    )
    
    drug_class = fields.Char(
        string='Drug Class',
        help='e.g., Beta Blocker, ACE Inhibitor, SSRI'
    )
    
    # Form and Strength
    medication_form = fields.Selection([
        ('tablet', 'Tablet'),
        ('capsule', 'Capsule'),
        ('liquid', 'Liquid/Syrup'),
        ('injection', 'Injection'),
        ('cream', 'Cream/Ointment'),
        ('gel', 'Gel'),
        ('patch', 'Patch'),
        ('drops', 'Drops'),
        ('inhaler', 'Inhaler'),
        ('suppository', 'Suppository'),
        ('powder', 'Powder'),
        ('spray', 'Spray'),
        ('other', 'Other'),
    ], string='Form', required=True, tracking=True)
    
    strength = fields.Char(
        string='Strength',
        required=True,
        help='e.g., 500mg, 10mg/5ml',
        tracking=True
    )
    
    strength_unit = fields.Char(
        string='Strength Unit',
        help='e.g., mg, ml, mcg'
    )
    
    # Dosage Information
    default_dose = fields.Float(
        string='Default Dose',
        help='Default dose amount'
    )
    
    default_dose_unit_id = fields.Many2one(
        'clinic.dose.unit',
        string='Default Dose Unit'
    )
    
    default_route_id = fields.Many2one(
        'clinic.medication.route',
        string='Default Route'
    )
    
    default_frequency_id = fields.Many2one(
        'clinic.frequency',
        string='Default Frequency'
    )
    
    max_dose = fields.Float(
        string='Maximum Dose',
        help='Maximum allowed dose'
    )
    
    max_daily_dose = fields.Float(
        string='Maximum Daily Dose',
        help='Maximum allowed daily dose'
    )
    
    # Manufacturer Information
    manufacturer = fields.Char(
        string='Manufacturer'
    )
    
    manufacturer_country = fields.Many2one(
        'res.country',
        string='Country of Origin'
    )
    
    ndc_code = fields.Char(
        string='NDC Code',
        help='National Drug Code'
    )
    
    # Storage Requirements
    storage_requirements = fields.Selection([
        ('room_temp', 'Room Temperature'),
        ('refrigerate', 'Refrigerate (2-8°C)'),
        ('freeze', 'Freeze (<0°C)'),
        ('cool', 'Cool (8-15°C)'),
        ('protect_light', 'Protect from Light'),
    ], string='Storage', default='room_temp')
    
    storage_instructions = fields.Text(
        string='Storage Instructions'
    )
    
    # Warnings and Contraindications
    warnings = fields.Text(
        string='Warnings',
        help='General warnings for this medication'
    )
    
    contraindications = fields.Text(
        string='Contraindications',
        help='Conditions where this medication should not be used'
    )
    
    black_box_warning = fields.Text(
        string='Black Box Warning',
        help='FDA black box warning if applicable'
    )
    
    pregnancy_category = fields.Selection([
        ('A', 'Category A - Safe'),
        ('B', 'Category B - Probably Safe'),
        ('C', 'Category C - Use with Caution'),
        ('D', 'Category D - Use in Life-Threatening'),
        ('X', 'Category X - Contraindicated'),
    ], string='Pregnancy Category')
    
    # Side Effects
    common_side_effects = fields.Text(
        string='Common Side Effects'
    )
    
    serious_side_effects = fields.Text(
        string='Serious Side Effects'
    )
    
    # Interactions
    drug_interactions = fields.Text(
        string='Drug Interactions',
        help='Known drug interactions'
    )
    
    food_interactions = fields.Text(
        string='Food Interactions',
        help='Known food interactions'
    )
    
    # Instructions
    administration_instructions = fields.Text(
        string='Administration Instructions',
        help='How to take/use this medication'
    )
    
    patient_counseling = fields.Text(
        string='Patient Counseling Points',
        help='Important points to discuss with patient'
    )
    
    # Pricing and Insurance
    list_price = fields.Float(
        string='List Price',
        digits='Product Price'
    )
    
    awp_price = fields.Float(
        string='AWP Price',
        help='Average Wholesale Price'
    )
    
    insurance_tier = fields.Selection([
        ('1', 'Tier 1 - Preferred Generic'),
        ('2', 'Tier 2 - Generic'),
        ('3', 'Tier 3 - Preferred Brand'),
        ('4', 'Tier 4 - Non-Preferred Brand'),
        ('5', 'Tier 5 - Specialty'),
    ], string='Insurance Tier')
    
    requires_prior_auth = fields.Boolean(
        string='Requires Prior Authorization',
        default=False
    )
    
    # Stock Integration
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        help='Link to inventory product'
    )
    
    track_inventory = fields.Boolean(
        string='Track Inventory',
        default=True
    )
    
    reorder_level = fields.Float(
        string='Reorder Level',
        help='Minimum stock level before reorder'
    )
    
    reorder_quantity = fields.Float(
        string='Reorder Quantity',
        help='Quantity to order when below reorder level'
    )
    
    # Alternatives
    alternative_medication_ids = fields.Many2many(
        'clinic.medication',
        'medication_alternative_rel',
        'medication_id',
        'alternative_id',
        string='Alternative Medications',
        domain=[('active', '=', True)]
    )
    
    generic_equivalent_ids = fields.Many2many(
        'clinic.medication',
        'medication_generic_rel',
        'brand_id',
        'generic_id',
        string='Generic Equivalents',
        domain=[('active', '=', True)]
    )
    
    # Package Information
    package_size = fields.Float(
        string='Package Size',
        help='Number of units per package'
    )
    
    package_unit = fields.Char(
        string='Package Unit',
        help='e.g., tablets, ml, vials'
    )
    
    # Regulatory
    fda_approval_date = fields.Date(
        string='FDA Approval Date'
    )
    
    patent_expiry_date = fields.Date(
        string='Patent Expiry Date'
    )
    
    is_generic_available = fields.Boolean(
        string='Generic Available',
        compute='_compute_generic_available',
        store=True
    )
    
    # Statistics
    prescription_count = fields.Integer(
        string='Times Prescribed',
        compute='_compute_prescription_count',
        store=True
    )
    
    last_prescribed_date = fields.Date(
        string='Last Prescribed',
        compute='_compute_last_prescribed',
        store=True
    )
    
    # Documents
    package_insert = fields.Binary(
        string='Package Insert',
        attachment=True
    )
    
    medication_guide = fields.Binary(
        string='Medication Guide',
        attachment=True
    )
    
    # Notes
    notes = fields.Text(
        string='Internal Notes'
    )
    
    @api.depends('name', 'generic_name', 'strength')
    def _compute_display_name(self):
        for med in self:
            parts = []
            if med.name:
                parts.append(med.name)
            if med.generic_name and med.generic_name != med.name:
                parts.append(f"({med.generic_name})")
            if med.strength:
                parts.append(med.strength)
            med.display_name = ' '.join(parts)
    
    @api.depends('generic_equivalent_ids', 'patent_expiry_date')
    def _compute_generic_available(self):
        for med in self:
            if med.generic_equivalent_ids:
                med.is_generic_available = True
            elif med.patent_expiry_date and med.patent_expiry_date < fields.Date.today():
                med.is_generic_available = True
            else:
                med.is_generic_available = False
    
    @api.depends('prescription_line_ids')
    def _compute_prescription_count(self):
        for med in self:
            med.prescription_count = len(med.prescription_line_ids)
    
    @api.depends('prescription_line_ids.create_date')
    def _compute_last_prescribed(self):
        for med in self:
            if med.prescription_line_ids:
                last_line = med.prescription_line_ids.sorted('create_date', reverse=True)[0]
                med.last_prescribed_date = last_line.create_date.date()
            else:
                med.last_prescribed_date = False
    
    prescription_line_ids = fields.One2many(
        'clinic.prescription.line',
        'medication_id',
        string='Prescription Lines'
    )
    
    @api.constrains('medication_type', 'controlled_schedule')
    def _check_controlled_schedule(self):
        for med in self:
            if med.medication_type == 'controlled' and not med.controlled_schedule:
                raise ValidationError(_("Controlled substances must have a schedule specified."))
            if med.medication_type != 'controlled' and med.controlled_schedule:
                raise ValidationError(_("Only controlled substances can have a schedule."))
    
    @api.constrains('max_dose', 'default_dose')
    def _check_doses(self):
        for med in self:
            if med.max_dose and med.default_dose and med.default_dose > med.max_dose:
                raise ValidationError(_("Default dose cannot exceed maximum dose."))
    
    @api.onchange('medication_type')
    def _onchange_medication_type(self):
        if self.medication_type != 'controlled':
            self.controlled_schedule = False
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.list_price = self.product_id.list_price
            if not self.barcode:
                self.barcode = self.product_id.barcode
    
    def action_view_prescriptions(self):
        """View all prescriptions containing this medication"""
        self.ensure_one()
        
        prescription_ids = self.prescription_line_ids.mapped('prescription_id')
        
        return {
            'name': _('Prescriptions'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.prescription',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', prescription_ids.ids)],
            'context': {'create': False}
        }
    
    def action_view_stock(self):
        """View stock information for this medication"""
        self.ensure_one()
        
        if not self.product_id:
            raise ValidationError(_("No product linked to this medication."))
        
        return {
            'name': _('Stock Information'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant',
            'view_mode': 'tree,form',
            'domain': [('product_id', '=', self.product_id.id)],
            'context': {'create': False}
        }
    
    def action_check_interactions(self):
        """Check drug interactions for this medication"""
        self.ensure_one()
        
        return {
            'name': _('Check Drug Interactions'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.drug.interaction.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_medication_id': self.id,
            }
        }
    
    def check_stock_availability(self, quantity):
        """Check if sufficient stock is available"""
        self.ensure_one()
        
        if not self.track_inventory:
            return True
        
        if not self.product_id:
            return False
        
        available_qty = self.product_id.qty_available
        return available_qty >= quantity
    
    def get_fefo_lot(self, quantity):
        """Get the lot to use based on FEFO (First Expired, First Out)"""
        self.ensure_one()
        
        if not self.product_id:
            return False
        
        # Get all lots with available quantity, ordered by expiry date
        lots = self.env['stock.lot'].search([
            ('product_id', '=', self.product_id.id),
            ('product_qty', '>', 0),
        ]).sorted('expiration_date')
        
        for lot in lots:
            if lot.product_qty >= quantity:
                return lot
        
        return False
    
    @api.model
    def check_reorder_levels(self):
        """Cron job to check reorder levels"""
        medications = self.search([
            ('track_inventory', '=', True),
            ('product_id', '!=', False),
            ('reorder_level', '>', 0),
        ])
        
        for med in medications:
            if med.product_id.qty_available <= med.reorder_level:
                # Create activity for reorder
                med.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=f'Reorder {med.name}',
                    note=f'Stock level ({med.product_id.qty_available}) is below reorder level ({med.reorder_level})',
                    user_id=self.env.ref('base.user_admin').id
                )
    
    @api.model
    def import_drug_database(self):
        """Import medications from external drug database"""
        # This would connect to an external drug database API
        # For example: RxNorm, FDA Orange Book, etc.
        pass

    @api.model
    def create(self, vals):
        """Override create to ensure product integration"""
        # If no product is specified but track_inventory is True, we'll create one
        if vals.get('track_inventory', True) and not vals.get('product_id'):
            # We'll create the product after the medication is created
            pass

        medication = super(Medication, self).create(vals)

        # Create linked product if needed
        if medication.track_inventory and not medication.product_id:
            medication._create_linked_product()

        return medication

    def _create_linked_product(self):
        """Create a linked product for this medication"""
        self.ensure_one()

        if self.product_id:
            return self.product_id

        # Get or create medication product category
        category = self.env.ref('clinic_prescription.product_category_medication', raise_if_not_found=False)
        if not category:
            category = self.env['product.category'].create({
                'name': 'Medications',
                'property_cost_method': 'fifo',
            })

        product_vals = {
            'name': self.display_name,
            'type': 'product',
            'tracking': 'lot',
            'list_price': self.list_price or 0.0,
            'default_code': self.code,
            'barcode': self.barcode,
            'categ_id': category.id,
            'detailed_type': 'product',
            'is_storable': True,
        }

        if self.use_expiration_date:
            product_vals.update({
                'use_expiration_date': True,
                'expiration_time': self.expiration_time,
            })

        if self.use_best_before_date:
            product_vals['use_best_before_date'] = True

        if self.use_removal_date:
            product_vals['use_removal_date'] = True

        if self.use_alert_date:
            product_vals.update({
                'use_alert_date': True,
                'alert_time': self.alert_time,
            })

        product = self.env['product.product'].create(product_vals)
        self.product_id = product

        return product

    def name_get(self):
        return [(med.id, med.display_name) for med in self]
    
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|',
                     ('name', operator, name),
                     ('generic_name', operator, name),
                     ('code', operator, name)]
        return self.search(domain + args, limit=limit).name_get()