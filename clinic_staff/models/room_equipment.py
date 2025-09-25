# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ClinicRoomEquipment(models.Model):
    """
    Medical equipment for rooms - internal implementation
    to avoid dependency on maintenance module
    """
    _name = 'clinic.room.equipment'
    _description = 'Medical Room Equipment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'name'

    name = fields.Char(
        string='Equipment Name',
        required=True,
        tracking=True
    )

    code = fields.Char(
        string='Equipment Code',
        required=True,
        index=True
    )

    equipment_type = fields.Selection([
        ('diagnostic', 'Diagnostic'),
        ('therapeutic', 'Therapeutic'),
        ('monitoring', 'Monitoring'),
        ('surgical', 'Surgical'),
        ('dental', 'Dental'),
        ('imaging', 'Imaging'),
        ('laboratory', 'Laboratory'),
        ('emergency', 'Emergency'),
        ('other', 'Other')
    ], string='Equipment Type', default='diagnostic', required=True)

    model = fields.Char(
        string='Model',
        help='Equipment model or version'
    )

    serial_no = fields.Char(
        string='Serial Number',
        help='Unique serial number'
    )

    manufacturer = fields.Char(
        string='Manufacturer'
    )

    purchase_date = fields.Date(
        string='Purchase Date'
    )

    warranty_date = fields.Date(
        string='Warranty Expiry'
    )

    room_ids = fields.Many2many(
        'clinic.room',
        'clinic_room_equipment_rel',
        'equipment_id',
        'room_id',
        string='Assigned Rooms'
    )

    branch_id = fields.Many2one(
        'clinic.branch',
        string='Branch',
        required=True,
        index=True
    )

    status = fields.Selection([
        ('available', 'Available'),
        ('in_use', 'In Use'),
        ('maintenance', 'Under Maintenance'),
        ('repair', 'Under Repair'),
        ('retired', 'Retired')
    ], string='Status', default='available', tracking=True)

    notes = fields.Text(
        string='Notes'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )