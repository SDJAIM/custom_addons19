# -*- coding: utf-8 -*-
from odoo import models, fields, api


class WhatsAppBroadcastWizard(models.TransientModel):
    _name = 'clinic.whatsapp.broadcast.wizard'
    _description = 'WhatsApp Broadcast Wizard'

    name = fields.Char(string='Campaign Name', required=True)
    recipient_filter = fields.Selection([
        ('all_patients', 'All Patients'),
        ('upcoming', 'Patients with Upcoming Appointments'),
        ('overdue', 'Patients with Overdue Appointments'),
        ('custom', 'Custom Selection')
    ], string='Recipients', required=True, default='all_patients')

    patient_ids = fields.Many2many(
        'clinic.patient',
        string='Selected Patients'
    )

    template_id = fields.Many2one(
        'clinic.whatsapp.template',
        string='Message Template',
        required=True
    )
    message = fields.Text(
        string='Message',
        related='template_id.body',
        readonly=False
    )

    schedule_time = fields.Datetime(
        string='Schedule Time',
        help='Leave empty to send immediately'
    )

    @api.onchange('recipient_filter')
    def _onchange_recipient_filter(self):
        if self.recipient_filter == 'all_patients':
            self.patient_ids = self.env['clinic.patient'].search([])
        elif self.recipient_filter == 'upcoming':
            # Get patients with upcoming appointments
            appointments = self.env['clinic.appointment'].search([
                ('appointment_date', '>', fields.Datetime.now()),
                ('state', '=', 'confirmed')
            ])
            self.patient_ids = appointments.mapped('patient_id')
        elif self.recipient_filter == 'overdue':
            # Get patients with overdue appointments
            appointments = self.env['clinic.appointment'].search([
                ('appointment_date', '<', fields.Datetime.now()),
                ('state', '=', 'no_show')
            ])
            self.patient_ids = appointments.mapped('patient_id')

    def action_broadcast(self):
        """Send broadcast messages"""
        self.ensure_one()

        for patient in self.patient_ids:
            if patient.mobile or patient.phone:
                self.env['clinic.whatsapp.message'].create({
                    'phone': patient.mobile or patient.phone,
                    'message': self.message,
                    'status': 'pending' if not self.schedule_time else 'scheduled',
                    'patient_id': patient.id,
                    'scheduled_date': self.schedule_time,
                })

        return {'type': 'ir.actions.act_window_close'}
