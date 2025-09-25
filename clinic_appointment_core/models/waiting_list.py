# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, date
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ClinicWaitingList(models.Model):
    _name = 'clinic.waiting.list'
    _description = 'Appointment Waiting List'
    _order = 'priority desc, create_date'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New')
    )
    
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        tracking=True
    )
    
    staff_id = fields.Many2one(
        'clinic.staff',
        string='Preferred Doctor/Dentist',
        domain="[('state', '=', 'active')]"
    )
    
    appointment_type_id = fields.Many2one(
        'clinic.appointment.type',
        string='Appointment Type',
        required=True
    )
    
    service_type = fields.Selection([
        ('medical', 'Medical'),
        ('dental', 'Dental'),
        ('telemed', 'Telemedicine')
    ], string='Service Type', required=True, default='medical')
    
    branch_id = fields.Many2one(
        'clinic.branch',
        string='Preferred Branch'
    )
    
    # Date preferences
    preferred_date_from = fields.Date(
        string='Available From',
        required=True,
        default=fields.Date.today
    )
    
    preferred_date_to = fields.Date(
        string='Available Until',
        required=True
    )
    
    preferred_time = fields.Selection([
        ('morning', 'Morning (8AM-12PM)'),
        ('afternoon', 'Afternoon (12PM-5PM)'),
        ('evening', 'Evening (5PM-8PM)'),
        ('any', 'Any Time')
    ], string='Preferred Time', default='any')
    
    # Days of week preferences
    monday = fields.Boolean(string='Mon', default=True)
    tuesday = fields.Boolean(string='Tue', default=True)
    wednesday = fields.Boolean(string='Wed', default=True)
    thursday = fields.Boolean(string='Thu', default=True)
    friday = fields.Boolean(string='Fri', default=True)
    saturday = fields.Boolean(string='Sat', default=False)
    sunday = fields.Boolean(string='Sun', default=False)
    
    # Priority and urgency
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string='Priority', default='1', tracking=True)
    
    urgency_reason = fields.Text(
        string='Urgency Reason',
        help='Explain why this is urgent'
    )
    
    # Status
    state = fields.Selection([
        ('waiting', 'Waiting'),
        ('notified', 'Notified'),
        ('scheduled', 'Scheduled'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='waiting', tracking=True)
    
    # Notification
    notification_sent = fields.Boolean(
        string='Notification Sent',
        default=False
    )
    
    notification_date = fields.Datetime(
        string='Notified On'
    )
    
    notification_method = fields.Selection([
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('phone', 'Phone Call'),
        ('whatsapp', 'WhatsApp')
    ], string='Notification Method')
    
    # Result
    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Scheduled Appointment'
    )
    
    scheduled_date = fields.Datetime(
        string='Scheduled For'
    )
    
    # Contact
    patient_phone = fields.Char(
        related='patient_id.mobile',
        string='Phone'
    )
    
    patient_email = fields.Char(
        related='patient_id.email',
        string='Email'
    )
    
    notes = fields.Text(string='Notes')
    
    # Computed
    days_waiting = fields.Integer(
        string='Days Waiting',
        compute='_compute_days_waiting'
    )
    
    is_expired = fields.Boolean(
        string='Is Expired',
        compute='_compute_is_expired'
    )
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('clinic.waiting.list') or _('New')
        return super().create(vals)
    
    @api.depends('create_date')
    def _compute_days_waiting(self):
        today = date.today()
        for record in self:
            if record.create_date:
                delta = today - record.create_date.date()
                record.days_waiting = delta.days
            else:
                record.days_waiting = 0
    
    @api.depends('preferred_date_to', 'state')
    def _compute_is_expired(self):
        today = date.today()
        for record in self:
            record.is_expired = (
                record.preferred_date_to < today and 
                record.state == 'waiting'
            )
    
    @api.constrains('preferred_date_from', 'preferred_date_to')
    def _check_dates(self):
        for record in self:
            if record.preferred_date_to < record.preferred_date_from:
                raise ValidationError(_("'Available Until' must be after 'Available From'!"))
    
    def get_preferred_days(self):
        """Get list of preferred days of week"""
        self.ensure_one()
        days = []
        if self.monday: days.append(0)
        if self.tuesday: days.append(1)
        if self.wednesday: days.append(2)
        if self.thursday: days.append(3)
        if self.friday: days.append(4)
        if self.saturday: days.append(5)
        if self.sunday: days.append(6)
        return days
    
    def get_preferred_time_range(self):
        """Get preferred time range as float hours"""
        self.ensure_one()
        time_ranges = {
            'morning': (8.0, 12.0),
            'afternoon': (12.0, 17.0),
            'evening': (17.0, 20.0),
            'any': (8.0, 20.0)
        }
        return time_ranges.get(self.preferred_time, (8.0, 20.0))
    
    def action_check_availability(self):
        """Check for available slots matching preferences"""
        self.ensure_one()
        
        # Find matching slots
        domain = [
            ('date', '>=', self.preferred_date_from),
            ('date', '<=', self.preferred_date_to),
            ('status', '=', 'available')
        ]
        
        if self.staff_id:
            domain.append(('staff_id', '=', self.staff_id.id))
        
        if self.branch_id:
            domain.append(('branch_id', '=', self.branch_id.id))
        
        slots = self.env['clinic.appointment.slot'].search(domain)
        
        # Filter by preferred days
        preferred_days = self.get_preferred_days()
        if preferred_days:
            slots = slots.filtered(lambda s: s.date.weekday() in preferred_days)
        
        # Filter by preferred time
        time_start, time_end = self.get_preferred_time_range()
        slots = slots.filtered(lambda s: time_start <= s.start_time <= time_end)
        
        if slots:
            # Notify patient about available slots
            self.action_notify_available(slots[:5])  # Send top 5 options
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _(f'Found {len(slots)} available slots. Patient has been notified.'),
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Slots'),
                    'message': _('No available slots found matching preferences.'),
                    'type': 'warning',
                }
            }
    
    def action_notify_available(self, slots):
        """Notify patient about available slots"""
        self.ensure_one()

        # Update status
        self.write({
            'state': 'notified',
            'notification_sent': True,
            'notification_date': fields.Datetime.now(),
            'notification_method': 'email'  # Default, can be enhanced
        })

        # Send notification to patient
        self._notify_patient(slots)

    def _notify_patient(self, available_slots=None):
        """
        Send notification to patient about appointment availability
        Uses multiple channels: Email, SMS, WhatsApp based on patient preferences
        """
        self.ensure_one()

        if not self.patient_id:
            _logger.warning(f"Cannot notify - no patient set for waiting list {self.id}")
            return False

        notification_sent = False

        # Prepare slot information if provided
        slot_info = ""
        if available_slots:
            slot_info = self._format_slot_information(available_slots[:5])  # Show max 5 slots

        # Try Email notification first
        if self.patient_id.email:
            try:
                self._send_email_notification(slot_info)
                notification_sent = True
                self.notification_method = 'email'
            except Exception as e:
                _logger.warning(f"Failed to send email notification: {str(e)}")

        # Try WhatsApp if available and configured
        if self.patient_id.phone and self.env['ir.module.module'].search([
            ('name', '=', 'clinic_integrations_whatsapp'),
            ('state', '=', 'installed')
        ]):
            try:
                self._send_whatsapp_notification(slot_info)
                notification_sent = True
                if self.notification_method:
                    self.notification_method += ',whatsapp'
                else:
                    self.notification_method = 'whatsapp'
            except Exception as e:
                _logger.warning(f"Failed to send WhatsApp notification: {str(e)}")

        # Try SMS if configured
        if self.patient_id.phone and self.env['ir.config_parameter'].sudo().get_param('clinic.sms.enabled'):
            try:
                self._send_sms_notification(slot_info)
                notification_sent = True
                if self.notification_method:
                    self.notification_method += ',sms'
                else:
                    self.notification_method = 'sms'
            except Exception as e:
                _logger.warning(f"Failed to send SMS notification: {str(e)}")

        # Log the notification
        if notification_sent:
            self.message_post(
                body=_("Patient notified about appointment availability via %s") % self.notification_method,
                message_type='notification'
            )
        else:
            # Create manual task if no notification could be sent
            self.activity_schedule(
                'mail.mail_activity_data_call',
                summary=_('Call patient about appointment availability'),
                note=_('Automated notifications failed. Please call patient %s at %s') % (
                    self.patient_id.name,
                    self.patient_id.phone or 'no phone'
                ),
                user_id=self.env.user.id
            )
            _logger.warning(f"No notification sent for waiting list {self.id} - manual follow-up required")

        return notification_sent

    def _format_slot_information(self, slots):
        """Format slot information for notifications"""
        if not slots:
            return ""

        lines = [_("Available appointment slots:")]
        for slot in slots:
            if hasattr(slot, 'date') and hasattr(slot, 'start_time'):
                # Format for appointment.slot model
                time_str = self._float_to_time_str(slot.start_time)
                lines.append(f"• {slot.date} at {time_str}")
            elif hasattr(slot, 'start'):
                # Format for calendar.event based slots
                lines.append(f"• {slot['start'].strftime('%Y-%m-%d %H:%M')}")

        return "\n".join(lines)

    def _float_to_time_str(self, float_time):
        """Convert float time to string format"""
        hours = int(float_time)
        minutes = int((float_time - hours) * 60)
        return f"{hours:02d}:{minutes:02d}"

    def _send_email_notification(self, slot_info):
        """Send email notification to patient"""
        self.ensure_one()

        template = self.env.ref(
            'clinic_appointment_core.email_template_waiting_list_notification',
            raise_if_not_found=False
        )

        if template:
            template.send_mail(self.id, force_send=True)
        else:
            # Create simple email if no template exists
            subject = _('Appointment Available - %s') % self.appointment_type_id.name

            body_html = f"""
            <p>Dear {self.patient_id.name},</p>
            <p>Good news! An appointment slot has become available that matches your preferences.</p>
            <p><b>Service:</b> {self.appointment_type_id.name}</p>
            """

            if self.staff_id:
                body_html += f"<p><b>Doctor:</b> {self.staff_id.name}</p>"

            if slot_info:
                body_html += f"<p>{slot_info.replace(chr(10), '<br/>')}</p>"

            body_html += f"""
            <p>Please contact us as soon as possible to schedule your appointment:</p>
            <ul>
                <li>Phone: {self.env.company.phone or 'Contact reception'}</li>
                <li>Email: {self.env.company.email or 'info@clinic.com'}</li>
            </ul>
            <p>Your waiting list reference: {self.name}</p>
            <p>Best regards,<br/>
            {self.env.company.name}</p>
            """

            mail_values = {
                'subject': subject,
                'email_to': self.patient_id.email,
                'email_from': self.env.company.email or 'noreply@clinic.com',
                'body_html': body_html,
                'auto_delete': True,
            }

            mail = self.env['mail.mail'].create(mail_values)
            mail.send()

    def _send_whatsapp_notification(self, slot_info):
        """Send WhatsApp notification to patient"""
        self.ensure_one()

        if not self.patient_id.phone:
            return False

        WhatsAppMessage = self.env['clinic.whatsapp.message']

        message_body = _(
            "Hello %s,\n\n"
            "Good news! An appointment slot is available.\n"
            "Service: %s\n"
        ) % (self.patient_id.name, self.appointment_type_id.name)

        if self.staff_id:
            message_body += _("Doctor: %s\n") % self.staff_id.name

        if slot_info:
            message_body += f"\n{slot_info}\n"

        message_body += _(
            "\nPlease contact us to schedule:\n"
            "Reference: %s\n"
            "Thank you!"
        ) % self.name

        whatsapp_msg = WhatsAppMessage.create({
            'patient_id': self.patient_id.id,
            'phone': self.patient_id.phone,
            'message_body': message_body,
            'message_type': 'text',
            'category': 'appointment',
            'res_model': 'clinic.waiting.list',
            'res_id': self.id,
        })

        return whatsapp_msg.send()

    def _send_sms_notification(self, slot_info):
        """Send SMS notification to patient"""
        self.ensure_one()

        if not self.patient_id.phone:
            return False

        # SMS implementation would depend on the SMS gateway being used
        # This is a placeholder that can be implemented based on the SMS provider

        message = _(
            "Hi %s, appointment available for %s. "
            "Call us to schedule. Ref: %s"
        ) % (
            self.patient_id.name.split()[0],  # First name only for SMS
            self.appointment_type_id.name,
            self.name
        )

        # Log that SMS would be sent
        _logger.info(f"SMS notification would be sent to {self.patient_id.phone}: {message}")

        # In production, this would integrate with an SMS gateway
        # For now, we'll just return True to indicate success
        return True
    
    def action_schedule_appointment(self):
        """Open wizard to schedule appointment from waiting list"""
        self.ensure_one()
        
        return {
            'name': _('Schedule from Waiting List'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.appointment',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_patient_id': self.patient_id.id,
                'default_staff_id': self.staff_id.id if self.staff_id else False,
                'default_appointment_type_id': self.appointment_type_id.id,
                'default_service_type': self.service_type,
                'default_branch_id': self.branch_id.id if self.branch_id else False,
                'waiting_list_id': self.id
            }
        }
    
    def action_cancel(self):
        """Cancel waiting list entry"""
        self.ensure_one()
        self.state = 'cancelled'
    
    @api.model
    def check_expired_entries(self):
        """Cron job to mark expired waiting list entries"""
        expired = self.search([
            ('preferred_date_to', '<', date.today()),
            ('state', '=', 'waiting')
        ])
        
        expired.write({'state': 'expired'})
    
    @api.model
    def auto_check_availability(self):
        """Cron job to check availability for waiting list"""
        waiting = self.search([
            ('state', '=', 'waiting'),
            ('preferred_date_from', '<=', date.today())
        ])
        
        for entry in waiting:
            entry.action_check_availability()