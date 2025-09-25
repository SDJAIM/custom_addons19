# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResUsers(models.Model):
    """
    Extend res.users to add relationship with clinic staff
    """
    _inherit = 'res.users'

    staff_ids = fields.One2many(
        'clinic.staff',
        'user_id',
        string='Related Staff Members',
        help='Staff members linked to this user account'
    )

    staff_id = fields.Many2one(
        'clinic.staff',
        string='Current Staff Member',
        compute='_compute_staff_id',
        store=False,
        help='Current active staff member for this user'
    )

    @api.depends('staff_ids')
    def _compute_staff_id(self):
        """Get the first active staff member for the user"""
        for user in self:
            active_staff = user.staff_ids.filtered(lambda s: s.active)
            user.staff_id = active_staff[0] if active_staff else False

    @property
    def SELF_READABLE_FIELDS(self):
        """Allow users to read their own staff information"""
        return super().SELF_READABLE_FIELDS + ['staff_ids', 'staff_id']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        """Users cannot modify their staff assignment"""
        return super().SELF_WRITEABLE_FIELDS