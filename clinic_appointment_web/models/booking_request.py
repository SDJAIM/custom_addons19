# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import uuid
import logging

_logger = logging.getLogger(__name__)


class BookingRequest(models.Model):
    _name = 'clinic.booking.request'
    _description = 'Online Booking Request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'create_date desc'
    _rec_name = 'reference'
    
    # Reference
    reference = fields.Char(
        string='Reference',
        required=True,
        readonly=True,
        copy=False,
        default='New',
        tracking=True
    )
    
    booking_token = fields.Char(
        string='Booking Token',
        readonly=True,
        copy=False,
        default=lambda self: str(uuid.uuid4()),
        help='Unique token for booking validation'
    )
    
    # Patient Information
    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        tracking=True
    )
    
    is_new_patient = fields.Boolean(
        string='New Patient',
        default=False,
        tracking=True
    )
    
    # Contact Information (for new patients)
    patient_name = fields.Char(
        string='Full Name',
        required=True,
        tracking=True
    )
    
    patient_email = fields.Char(
        string='Email',
        required=True,
        tracking=True
    )
    
    patient_phone = fields.Char(
        string='Phone',
        required=True,
        tracking=True
    )
    
    patient_dob = fields.Date(
        string='Date of Birth'
    )
    
    patient_gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ], string='Gender')
    
    # Service Selection
    service_type = fields.Selection([
        ('consultation', 'General Consultation'),
        ('dental', 'Dental'),
        ('specialist', 'Specialist'),
        ('emergency', 'Emergency'),
        ('checkup', 'Health Checkup'),
        ('vaccination', 'Vaccination'),
        ('laboratory', 'Laboratory'),
        ('imaging', 'Imaging/X-ray'),
        ('procedure', 'Medical Procedure'),
    ], string='Service Type', required=True, tracking=True)
    
    service_id = fields.Many2one(
        'clinic.service',
        string='Specific Service',
        domain="[('service_type', '=', service_type)]"
    )
    
    # Provider Selection
    preferred_doctor_id = fields.Many2one(
        'clinic.staff',
        string='Preferred Doctor',
        domain=[('is_practitioner', '=', True)],
        tracking=True
    )
    
    any_doctor = fields.Boolean(
        string='Any Available Doctor',
        default=True
    )
    
    # Date and Time
    preferred_date = fields.Date(
        string='Preferred Date',
        required=True,
        tracking=True
    )
    
    preferred_time = fields.Selection([
        ('morning', 'Morning (8:00 - 12:00)'),
        ('afternoon', 'Afternoon (12:00 - 17:00)'),
        ('evening', 'Evening (17:00 - 20:00)'),
        ('any', 'Any Time'),
    ], string='Preferred Time', default='any', required=True)
    
    selected_slot_id = fields.Many2one(
        'clinic.appointment.slot',
        string='Selected Slot',
        tracking=True
    )
    
    appointment_datetime = fields.Datetime(
        string='Appointment Date/Time',
        tracking=True
    )
    
    # Insurance Information
    has_insurance = fields.Boolean(
        string='Has Insurance',
        default=False,
        tracking=True
    )
    
    insurance_company = fields.Char(
        string='Insurance Company'
    )
    
    insurance_policy_number = fields.Char(
        string='Policy Number'
    )
    
    insurance_documents = fields.Many2many(
        'ir.attachment',
        'booking_insurance_doc_rel',
        string='Insurance Documents'
    )
    
    requires_authorization = fields.Boolean(
        string='Requires Prior Authorization',
        default=False
    )
    
    authorization_number = fields.Char(
        string='Authorization Number'
    )
    
    # Payment
    payment_method = fields.Selection([
        ('cash', 'Cash on Arrival'),
        ('insurance', 'Insurance Only'),
        ('online', 'Pay Online Now'),
        ('insurance_copay', 'Insurance + Co-pay'),
    ], string='Payment Method', default='cash', required=True, tracking=True)
    
    estimated_cost = fields.Float(
        string='Estimated Cost',
        digits='Product Price'
    )
    
    copay_amount = fields.Float(
        string='Co-pay Amount',
        digits='Product Price'
    )
    
    payment_status = fields.Selection([
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('failed', 'Payment Failed'),
    ], string='Payment Status', default='pending', tracking=True)
    
    payment_reference = fields.Char(
        string='Payment Reference'
    )
    
    # Chief Complaint
    chief_complaint = fields.Text(
        string='Reason for Visit',
        required=True,
        help='Please describe your symptoms or reason for booking'
    )
    
    urgency = fields.Selection([
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency'),
    ], string='Urgency', default='routine', tracking=True)
    
    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('scheduled', 'Scheduled'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ], string='Status', default='draft', required=True, tracking=True, index=True)
    
    # Approval
    requires_approval = fields.Boolean(
        string='Requires Approval',
        compute='_compute_requires_approval',
        store=True
    )
    
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        tracking=True
    )
    
    approval_date = fields.Datetime(
        string='Approval Date',
        readonly=True,
        tracking=True
    )
    
    rejection_reason = fields.Text(
        string='Rejection Reason',
        tracking=True
    )
    
    # Related Appointment
    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Created Appointment',
        readonly=True,
        tracking=True
    )
    
    # Additional Information
    special_requirements = fields.Text(
        string='Special Requirements',
        help='Any special needs or requirements (wheelchair access, interpreter, etc.)'
    )
    
    marketing_consent = fields.Boolean(
        string='Marketing Consent',
        default=False,
        help='I agree to receive promotional communications'
    )
    
    terms_accepted = fields.Boolean(
        string='Terms Accepted',
        required=True,
        help='I accept the terms and conditions'
    )
    
    # Tracking
    ip_address = fields.Char(
        string='IP Address',
        readonly=True
    )
    
    user_agent = fields.Text(
        string='User Agent',
        readonly=True
    )
    
    booking_source = fields.Selection([
        ('website', 'Website'),
        ('mobile', 'Mobile App'),
        ('portal', 'Patient Portal'),
        ('kiosk', 'Self-Service Kiosk'),
    ], string='Booking Source', default='website', readonly=True)
    
    @api.depends('service_type', 'urgency', 'payment_method')
    def _compute_requires_approval(self):
        for request in self:
            # Require approval for certain conditions
            request.requires_approval = (
                request.urgency == 'emergency' or
                request.service_type in ['emergency', 'procedure'] or
                request.payment_method == 'insurance' or
                request.is_new_patient
            )
    
    @api.model
    def create(self, vals):
        if vals.get('reference', 'New') == 'New':
            vals['reference'] = self.env['ir.sequence'].next_by_code('clinic.booking.request') or 'New'
        
        # Validate next-week rule
        if vals.get('preferred_date'):
            preferred_date = fields.Date.from_string(vals['preferred_date'])
            min_date = fields.Date.today() + timedelta(days=7)
            
            # Allow urgent/emergency bookings within a week
            if vals.get('urgency', 'routine') == 'routine' and preferred_date < min_date:
                raise ValidationError(_(
                    "Appointments must be booked at least one week in advance. "
                    "For urgent appointments, please call our clinic."
                ))
        
        return super().create(vals)
    
    @api.constrains('preferred_date')
    def _check_preferred_date(self):
        for request in self:
            if request.preferred_date and request.urgency == 'routine':
                min_date = fields.Date.today() + timedelta(days=7)
                if request.preferred_date < min_date:
                    raise ValidationError(_(
                        "Routine appointments must be booked at least one week in advance."
                    ))
    
    def action_submit(self):
        """Submit booking request"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_("Only draft requests can be submitted."))
        
        if not self.terms_accepted:
            raise UserError(_("Please accept the terms and conditions."))
        
        # Check slot availability
        if self.selected_slot_id and not self.selected_slot_id.is_available:
            raise UserError(_("The selected slot is no longer available."))
        
        self.state = 'submitted'
        
        # Move to approval if required
        if self.requires_approval:
            self.state = 'pending_approval'
            
            # Create activity for secretary
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary='Booking approval required',
                user_id=self.env.ref('clinic_appointment_web.group_booking_secretary').users[0].id
                        if self.env.ref('clinic_appointment_web.group_booking_secretary').users 
                        else self.env.user.id
            )
        else:
            # Auto-approve if no approval needed
            self.action_approve()
        
        # Send confirmation email
        self._send_confirmation_email()
        
        return True
    
    def action_approve(self):
        """Approve booking request"""
        self.ensure_one()
        
        if self.state not in ['submitted', 'pending_approval']:
            raise UserError(_("Request cannot be approved in current state."))
        
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Datetime.now(),
        })
        
        # Create appointment
        self._create_appointment()
        
        # Send approval email
        self._send_approval_email()
        
        return True
    
    def action_reject(self):
        """Reject booking request"""
        self.ensure_one()
        
        if self.state not in ['submitted', 'pending_approval', 'approved']:
            raise UserError(_("Request cannot be rejected in current state."))
        
        return {
            'name': _('Reject Booking'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.booking.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_booking_id': self.id,
            }
        }
    
    def action_cancel(self):
        """Cancel booking request"""
        self.ensure_one()
        
        if self.state in ['scheduled', 'rejected', 'cancelled', 'expired']:
            raise UserError(_("Request cannot be cancelled in current state."))
        
        self.state = 'cancelled'
        
        # Cancel related appointment if exists
        if self.appointment_id and self.appointment_id.state == 'draft':
            self.appointment_id.action_cancel()
        
        # Send cancellation email
        self._send_cancellation_email()
        
        return True
    
    def action_reschedule(self):
        """Reschedule booking"""
        self.ensure_one()
        
        if self.state != 'scheduled':
            raise UserError(_("Only scheduled bookings can be rescheduled."))
        
        return {
            'name': _('Reschedule Booking'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.booking.reschedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_booking_id': self.id,
                'default_current_date': self.appointment_datetime,
            }
        }
    
    def _create_appointment(self):
        """Create appointment from approved booking"""
        self.ensure_one()
        
        if self.appointment_id:
            return self.appointment_id
        
        # Create or find patient
        if not self.patient_id:
            if self.is_new_patient:
                # Create new patient
                patient_vals = {
                    'name': self.patient_name,
                    'email': self.patient_email,
                    'phone': self.patient_phone,
                    'date_of_birth': self.patient_dob,
                    'gender': self.patient_gender,
                }
                self.patient_id = self.env['clinic.patient'].create(patient_vals)
            else:
                # Try to find existing patient
                patient = self.env['clinic.patient'].search([
                    '|',
                    ('email', '=', self.patient_email),
                    ('phone', '=', self.patient_phone),
                ], limit=1)
                
                if patient:
                    self.patient_id = patient
                else:
                    # Create new patient
                    patient_vals = {
                        'name': self.patient_name,
                        'email': self.patient_email,
                        'phone': self.patient_phone,
                        'date_of_birth': self.patient_dob,
                        'gender': self.patient_gender,
                    }
                    self.patient_id = self.env['clinic.patient'].create(patient_vals)
        
        # Prepare appointment values
        appointment_vals = {
            'patient_id': self.patient_id.id,
            'appointment_date': self.appointment_datetime or 
                               datetime.combine(self.preferred_date, datetime.min.time()),
            'doctor_id': self.preferred_doctor_id.id if not self.any_doctor else False,
            'service_type': self.service_type,
            'chief_complaint': self.chief_complaint,
            'urgency': self.urgency,
            'state': 'draft',
            'booking_request_id': self.id,
            'is_online_booking': True,
        }
        
        # Add slot if selected
        if self.selected_slot_id:
            appointment_vals.update({
                'slot_id': self.selected_slot_id.id,
                'appointment_date': self.selected_slot_id.start_datetime,
                'doctor_id': self.selected_slot_id.staff_id.id,
            })
        
        # Create appointment
        appointment = self.env['clinic.appointment'].create(appointment_vals)
        
        # Link appointment
        self.appointment_id = appointment
        self.state = 'scheduled'
        
        # Reserve slot
        if self.selected_slot_id:
            self.selected_slot_id.action_reserve()
        
        _logger.info(f"Appointment {appointment.name} created from booking request {self.reference}")
        
        return appointment
    
    def _send_confirmation_email(self):
        """Send booking confirmation email"""
        template = self.env.ref('clinic_appointment_web.email_booking_confirmation', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
    
    def _send_approval_email(self):
        """Send booking approval email"""
        template = self.env.ref('clinic_appointment_web.email_booking_approved', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
    
    def _send_cancellation_email(self):
        """Send booking cancellation email"""
        template = self.env.ref('clinic_appointment_web.email_booking_cancelled', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
    
    @api.model
    def check_expired_bookings(self):
        """Cron job to expire old pending bookings"""
        expire_date = fields.Datetime.now() - timedelta(hours=24)
        
        expired_bookings = self.search([
            ('state', 'in', ['draft', 'submitted', 'pending_approval']),
            ('create_date', '<', expire_date),
        ])
        
        for booking in expired_bookings:
            booking.state = 'expired'
            
            # Release slot if reserved
            if booking.selected_slot_id and booking.selected_slot_id.state == 'reserved':
                booking.selected_slot_id.action_release()
        
        _logger.info(f"Expired {len(expired_bookings)} booking requests")
    
    def get_portal_url(self):
        """Get portal URL for this booking"""
        self.ensure_one()
        return f'/my/bookings/{self.id}?token={self.booking_token}'
    
    def name_get(self):
        result = []
        for booking in self:
            name = booking.reference
            if booking.patient_name:
                name = f"{name} - {booking.patient_name}"
            result.append((booking.id, name))
        return result