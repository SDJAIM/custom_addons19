# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta


class FollowUpWizard(models.TransientModel):
    _name = 'clinic.appointment.followup.wizard'
    _description = 'Follow-up Appointment Wizard'

    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Original Appointment',
        required=True,
        readonly=True
    )
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        related='appointment_id.patient_id',
        readonly=True
    )
    follow_up_date = fields.Datetime(
        string='Follow-up Date',
        required=True,
        default=lambda self: datetime.now() + timedelta(days=7)
    )
    follow_up_type = fields.Selection([
        ('routine', 'Routine Check-up'),
        ('treatment', 'Treatment Follow-up'),
        ('test', 'Test Results Review'),
        ('other', 'Other')
    ], string='Follow-up Type', required=True, default='routine')
    notes = fields.Text(string='Notes')

    def action_create_followup(self):
        """Create follow-up appointment"""
        self.ensure_one()

        # Calculate end time based on original appointment duration
        duration = self.appointment_id.stop - self.appointment_id.start
        follow_up_stop = self.follow_up_date + duration

        # Create new appointment
        new_appointment = self.env['clinic.appointment'].create({
            'patient_id': self.patient_id.id,
            'start': self.follow_up_date,
            'stop': follow_up_stop,
            'appointment_type_id': self.appointment_id.appointment_type_id.id,
            'staff_id': self.appointment_id.staff_id.id,
            'branch_id': self.appointment_id.branch_id.id,
            'service_type': self.appointment_id.service_type,
            'is_follow_up': True,
            'notes': f"Follow-up for #{self.appointment_id.name}: {self.notes or ''}"
        })

        # Return action to open the new appointment
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.appointment',
            'res_id': new_appointment.id,
            'view_mode': 'form',
            'target': 'current',
        }
