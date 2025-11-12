# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AppointmentTelemed(models.Model):
    """
    Extend clinic.appointment with Discuss-based telemedicine integration
    """
    _inherit = 'clinic.appointment'

    # Telemedicine Session Link
    telemed_session_id = fields.Many2one(
        'clinic.telemed.session',
        string='Telemedicine Session',
        help='Link to telemedicine video consultation session',
        tracking=True
    )

    # Computed fields for UI
    has_telemed_session = fields.Boolean(
        string='Has Telemedicine Session',
        compute='_compute_has_telemed_session',
        store=True
    )

    is_telemedicine_appointment = fields.Boolean(
        string='Is Telemedicine',
        compute='_compute_is_telemedicine_appointment',
        store=True
    )

    telemed_session_state = fields.Selection(
        string='Video Call Status',
        related='telemed_session_id.state',
        store=True,
        readonly=True
    )

    telemed_channel_id = fields.Many2one(
        'discuss.channel',
        string='Video Channel',
        related='telemed_session_id.discuss_channel_id',
        store=True,
        readonly=True
    )

    @api.depends('telemed_session_id')
    def _compute_has_telemed_session(self):
        for appointment in self:
            appointment.has_telemed_session = bool(appointment.telemed_session_id)

    @api.depends('service_type')
    def _compute_is_telemedicine_appointment(self):
        for appointment in self:
            appointment.is_telemedicine_appointment = (appointment.service_type == 'telemed')

    def action_create_telemed_session(self):
        """Create a telemedicine session for this appointment"""
        self.ensure_one()

        if not self.is_telemedicine_appointment:
            raise UserError(_("This is not a telemedicine appointment. "
                            "Please change the service type to 'Telemedicine' first."))

        if self.telemed_session_id:
            raise UserError(_("A telemedicine session already exists for this appointment."))

        if not self.patient_id:
            raise UserError(_("Please assign a patient before creating telemedicine session."))

        if not self.staff_id:
            raise UserError(_("Please assign a doctor/staff before creating telemedicine session."))

        # Create telemedicine session
        session = self.env['clinic.telemed.session'].create({
            'appointment_id': self.id,
            'session_date': self.start,
            'duration_minutes': int(self.duration * 60) if self.duration else 30,
        })

        self.telemed_session_id = session.id

        # Auto-create video channel if configured
        config_helper = self.env['ir.config_parameter'].sudo()
        auto_create = config_helper.get_param('clinic.telemed.auto_create_channel', 'True')

        if auto_create == 'True':
            try:
                session.action_create_video_channel()
            except Exception as e:
                _logger.warning(f"Could not auto-create video channel: {str(e)}")

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.telemed.session',
            'res_id': session.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_telemed_session(self):
        """Open the telemedicine session form"""
        self.ensure_one()

        if not self.telemed_session_id:
            raise UserError(_("No telemedicine session exists for this appointment. "
                            "Please create one first."))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.telemed.session',
            'res_id': self.telemed_session_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_join_telemed_call(self):
        """Quick action to join the telemedicine video call"""
        self.ensure_one()

        if not self.telemed_session_id:
            raise UserError(_("No telemedicine session exists for this appointment."))

        return self.telemed_session_id.action_join_call()

    def action_setup_telemedicine(self):
        """Wizard to quickly set up telemedicine for this appointment"""
        self.ensure_one()

        # Change service type to telemedicine if needed
        if not self.is_telemedicine_appointment:
            self.write({'service_type': 'telemed'})

        # Create session and channel in one step
        if not self.telemed_session_id:
            action = self.action_create_telemed_session()
            # Session created, channel might be auto-created
            return action
        else:
            # Session exists, just open it
            return self.action_open_telemed_session()

    def write(self, vals):
        """Override to sync telemedicine session when appointment changes"""
        res = super(AppointmentTelemed, self).write(vals)

        # Sync session date/duration if changed
        if ('start' in vals or 'duration' in vals) and self.telemed_session_id:
            session_vals = {}
            if 'start' in vals:
                session_vals['session_date'] = vals['start']
            if 'duration' in vals:
                session_vals['duration_minutes'] = int(vals['duration'] * 60)

            if session_vals:
                self.telemed_session_id.write(session_vals)

        return res

    def unlink(self):
        """Clean up telemedicine sessions when appointment is deleted"""
        # Find sessions to delete
        sessions = self.mapped('telemed_session_id')

        # Call super first
        res = super(AppointmentTelemed, self).unlink()

        # Delete orphaned sessions (if not already deleted by cascade)
        if sessions:
            sessions.unlink()

        return res
