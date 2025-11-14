# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta


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
        """
        Reschedule the appointment with deadline enforcement (TASK-F2-007)

        Raises:
            UserError: If rescheduling deadline has passed
        """
        self.ensure_one()

        # ⚠️ DEADLINE ENFORCEMENT (TASK-F2-007)
        appointment = self.appointment_id
        appt_type = appointment.appointment_type_id

        # Check if rescheduling is allowed at all
        if not appt_type.allow_reschedule:
            raise UserError(
                _('Rescheduling is not allowed for this appointment type.\n\n'
                  'Appointment Type: %s\n\n'
                  'Please contact the clinic directly if you need to make changes.') % (
                      appt_type.name
                  )
            )

        # Calculate hours until appointment
        hours_until = (appointment.start - fields.Datetime.now()).total_seconds() / 3600

        # Check if within deadline
        if hours_until < appt_type.reschedule_limit_hours:
            raise UserError(
                _('Rescheduling deadline has passed.\n\n'
                  'This appointment requires rescheduling at least %d hours in advance.\n'
                  'Time remaining: %.1f hours\n'
                  'Current appointment: %s\n\n'
                  'Please contact the clinic directly to make changes.') % (
                      appt_type.reschedule_limit_hours,
                      hours_until,
                      appointment.start.strftime('%Y-%m-%d %H:%M') if appointment.start else 'N/A'
                  )
            )

        # ✅ Deadline check passed - proceed with reschedule
        # Calculate new end time based on current duration
        duration = appointment.stop - appointment.start
        new_stop = self.new_date + duration

        # Update appointment with new datetime and reason
        appointment.write({
            'start': self.new_date,
            'stop': new_stop,
            'notes': f"Rescheduled: {self.reason}\n{appointment.notes or ''}"
        })

        # Send notification if requested
        if self.notify_patient:
            # Send notification (implement notification logic)
            pass

        return {'type': 'ir.actions.act_window_close'}
