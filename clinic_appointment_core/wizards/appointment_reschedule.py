# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AppointmentRescheduleWizard(models.TransientModel):
    _name = 'clinic.appointment.reschedule.wizard'
    _description = 'Appointment Reschedule Wizard'

    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Appointment',
        required=True,
        readonly=True
    )
    current_date = fields.Datetime(
        string='Current Date',
        related='appointment_id.start',
        readonly=True
    )
    new_date = fields.Datetime(
        string='New Date & Time',
        required=True
    )
    reason = fields.Text(string='Reason for Rescheduling', required=True)
    notify_patient = fields.Boolean(
        string='Notify Patient',
        default=True
    )

    @api.constrains('new_date')
    def _check_new_date(self):
        for wizard in self:
            if wizard.new_date <= fields.Datetime.now():
                raise ValidationError("New appointment date must be in the future.")

    def action_reschedule(self):
        """Reschedule the appointment"""
        self.ensure_one()
        # Calculate new end time based on current duration
        duration = self.appointment_id.stop - self.appointment_id.start
        new_stop = self.new_date + duration
        self.appointment_id.write({
            'start': self.new_date,
            'stop': new_stop,
            'notes': f"Rescheduled: {self.reason}\n{self.appointment_id.notes or ''}"
        })

        if self.notify_patient:
            # Send notification (implement notification logic)
            pass

        return {'type': 'ir.actions.act_window_close'}
