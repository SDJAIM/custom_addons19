# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from datetime import datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)


class AppointmentBookingController(http.Controller):

    @http.route('/appointments/<int:type_id>/book', type='http', auth='public', website=True, sitemap=True, csrf=False)
    def book_appointment_type(self, type_id, **kwargs):
        """
        TASK-F1-002: Shareable booking link for specific appointment type
        Public URL that allows direct booking without login
        """
        # Get appointment type
        appt_type = request.env['clinic.appointment.type'].sudo().browse(type_id)

        # Check if appointment type exists and allows online booking
        if not appt_type.exists():
            return request.render('website.404')

        if not appt_type.allow_online_booking or not appt_type.active:
            return request.render('clinic_appointment_web.booking_disabled', {
                'appointment_type': appt_type,
            })

        # Get available staff for this appointment type
        available_staff = request.env['clinic.staff'].sudo().search([
            ('state', '=', 'active'),
            ('id', 'in', appt_type.allowed_staff_ids.ids) if appt_type.allowed_staff_ids else ('id', '!=', False),
        ])

        # TASK-F3-005: Get Open Graph data for social sharing
        og_data = appt_type.get_og_data()

        values = {
            'appointment_type': appt_type,
            'available_staff': available_staff,
            'min_date': (datetime.now() + timedelta(hours=appt_type.min_notice_hours)).date().isoformat(),
            'max_date': (datetime.now() + timedelta(days=appt_type.max_days_ahead)).date().isoformat(),
            'page_name': 'shareable_booking',
            'og_data': og_data,  # TASK-F3-005: Open Graph metadata
        }

        return request.render('clinic_appointment_web.shareable_booking_wizard', values)

    @http.route('/appointment/book', type='http', auth='public', website=True, sitemap=True, csrf=True)
    def appointment_book(self, **kw):
        """Main booking page with stepper UI"""

        # Get available appointment types - use sudo only for public access to limited public data
        # Note: clinic.appointment.type should have proper ir.model.access for public users
        AppointmentType = request.env['clinic.appointment.type'].sudo()
        services = AppointmentType.search([
            ('available_online', '=', True),
            ('active', '=', True)
        ])

        # Get service types - no sudo needed for field definition access
        service_types = dict(request.env['clinic.booking.request']._fields['service_type'].selection)

        # Get minimum booking date (next week)
        min_date = datetime.now().date() + timedelta(days=7)

        values = {
            'services': services,
            'service_types': service_types,
            'min_date': min_date.isoformat(),
            'page_name': 'appointment_booking',
        }

        return request.render('clinic_appointment_web.booking_form', values)
    
    @http.route('/appointment/slots', type='jsonrpc', auth='public', website=True, csrf=True)
    def get_available_slots(self, date, service_type=None, doctor_id=None, **kw):
        """Get available slots for a specific date"""
        
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return {'error': _('Invalid date format')}
        
        # Check next-week rule
        min_date = datetime.now().date() + timedelta(days=7)
        if date_obj < min_date:
            return {'error': _('Appointments must be booked at least one week in advance')}
        
        domain = [
            ('date', '=', date),
            ('is_available', '=', True),
        ]
        
        if doctor_id:
            domain.append(('staff_id', '=', int(doctor_id)))
        
        slots = request.env['clinic.appointment.slot'].sudo().search(domain)
        
        # Group slots by time
        slot_data = {}
        for slot in slots:
            time_str = slot.start_datetime.strftime('%H:%M')
            if time_str not in slot_data:
                slot_data[time_str] = []
            
            slot_data[time_str].append({
                'id': slot.id,
                'time': time_str,
                'doctor': slot.staff_id.name,
                'doctor_id': slot.staff_id.id,
                'specialty': slot.staff_id.specialization_ids[0].name if slot.staff_id.specialization_ids else '',
                'duration': slot.duration,
            })
        
        return {
            'success': True,
            'slots': slot_data,
            'date': date,
        }
    
    @http.route('/appointment/doctors', type='jsonrpc', auth='public', website=True, csrf=True)
    def get_available_doctors(self, service_type=None, date=None, **kw):
        """Get available doctors for a service type"""
        
        domain = [
            ('is_practitioner', '=', True),
            ('active', '=', True),
        ]
        
        if service_type:
            # Filter by service type specialization
            domain.append(('service_types', 'in', [service_type]))
        
        doctors = request.env['clinic.staff'].sudo().search(domain)
        
        doctor_data = []
        for doctor in doctors:
            available_dates = []
            
            # Check availability for next 30 days
            if date:
                # Check specific date
                date_obj = datetime.strptime(date, '%Y-%m-%d').date()
                slots = request.env['clinic.appointment.slot'].sudo().search([
                    ('staff_id', '=', doctor.id),
                    ('date', '=', date),
                    ('is_available', '=', True),
                ], limit=1)
                
                if slots:
                    available_dates.append(date)
            
            doctor_data.append({
                'id': doctor.id,
                'name': doctor.name,
                'title': doctor.professional_title or '',
                'specializations': ', '.join(doctor.specialization_ids.mapped('name')),
                'image': f'/web/image/clinic.staff/{doctor.id}/image_128',
                'available_dates': available_dates,
                'rating': doctor.rating or 0,
            })
        
        return {
            'success': True,
            'doctors': doctor_data,
        }
    
    @http.route('/appointment/submit', type='jsonrpc', auth='public', website=True, csrf=True)
    def submit_booking(self, **post):
        """Submit booking request"""
        
        # Validate required fields
        required_fields = ['patient_name', 'patient_email', 'patient_phone', 
                          'service_type', 'preferred_date', 'chief_complaint']
        
        for field in required_fields:
            if not post.get(field):
                return {'error': _('Missing required field: %s') % field}
        
        # Check if user is logged in
        if request.env.user._is_public():
            # Check if patient exists
            patient = request.env['clinic.patient'].sudo().search([
                '|',
                ('email', '=', post.get('patient_email')),
                ('phone', '=', post.get('patient_phone')),
            ], limit=1)
            
            is_new_patient = not bool(patient)
        else:
            # Get patient from logged in user
            patient = request.env.user.partner_id.patient_id
            is_new_patient = not bool(patient)
        
        # Create booking request
        booking_vals = {
            'patient_id': patient.id if patient else False,
            'is_new_patient': is_new_patient,
            'patient_name': post.get('patient_name'),
            'patient_email': post.get('patient_email'),
            'patient_phone': post.get('patient_phone'),
            'patient_dob': post.get('patient_dob') or False,
            'patient_gender': post.get('patient_gender') or False,
            'service_type': post.get('service_type'),
            'service_id': int(post.get('service_id')) if post.get('service_id') else False,
            'preferred_doctor_id': int(post.get('doctor_id')) if post.get('doctor_id') else False,
            'any_doctor': post.get('any_doctor', True),
            'preferred_date': post.get('preferred_date'),
            'preferred_time': post.get('preferred_time', 'any'),
            'selected_slot_id': int(post.get('slot_id')) if post.get('slot_id') else False,
            'chief_complaint': post.get('chief_complaint'),
            'urgency': post.get('urgency', 'routine'),
            'has_insurance': post.get('has_insurance', False),
            'insurance_company': post.get('insurance_company') or False,
            'insurance_policy_number': post.get('insurance_policy_number') or False,
            'payment_method': post.get('payment_method', 'cash'),
            'special_requirements': post.get('special_requirements') or False,
            'marketing_consent': post.get('marketing_consent', False),
            'terms_accepted': post.get('terms_accepted', False),
            'ip_address': request.httprequest.remote_addr,
            'user_agent': request.httprequest.user_agent.string,
            'booking_source': 'website',
        }
        
        try:
            booking = request.env['clinic.booking.request'].sudo().create(booking_vals)
            
            # Submit the booking
            booking.action_submit()
            
            return {
                'success': True,
                'booking_id': booking.id,
                'reference': booking.reference,
                'confirmation_url': f'/appointment/confirmation/{booking.id}?token={booking.booking_token}',
                'message': _('Your booking request has been submitted successfully!'),
            }
            
        except Exception as e:
            _logger.error(f"Booking submission error: {str(e)}")
            return {
                'error': _('An error occurred while processing your request. Please try again.'),
            }
    
    @http.route('/appointment/confirmation/<int:booking_id>', type='http', auth='public', website=True, csrf=True)
    def booking_confirmation(self, booking_id, token=None, **kw):
        """Booking confirmation page"""
        
        booking = request.env['clinic.booking.request'].sudo().browse(booking_id)
        
        if not booking.exists() or (token and booking.booking_token != token):
            return request.render('website.404')
        
        values = {
            'booking': booking,
            'page_name': 'booking_confirmation',
        }
        
        return request.render('clinic_appointment_web.booking_confirmation', values)
    
    @http.route('/appointment/upload-insurance', type='http', auth='public', methods=['POST'], csrf=True)
    def upload_insurance_document(self, booking_id, token, **post):
        """Upload insurance documents"""
        
        booking = request.env['clinic.booking.request'].sudo().browse(int(booking_id))
        
        if not booking.exists() or booking.booking_token != token:
            return json.dumps({'error': 'Invalid booking'})
        
        # Handle file upload
        for file_field in request.httprequest.files:
            file = request.httprequest.files[file_field]
            
            if file:
                attachment = request.env['ir.attachment'].sudo().create({
                    'name': file.filename,
                    'type': 'binary',
                    'datas': base64.b64encode(file.read()),
                    'res_model': 'clinic.booking.request',
                    'res_id': booking.id,
                })
                
                booking.insurance_documents = [(4, attachment.id)]
        
        return json.dumps({'success': True})
    
    @http.route('/appointment/check-patient', type='jsonrpc', auth='public', website=True, csrf=True)
    def check_patient_exists(self, email=None, phone=None, **kw):
        """Check if patient exists"""
        
        if not email and not phone:
            return {'exists': False}
        
        domain = []
        if email:
            domain.append(('email', '=', email))
        if phone:
            domain.append(('phone', '=', phone))
        
        if len(domain) > 1:
            domain = ['|'] + domain
        
        patient = request.env['clinic.patient'].sudo().search(domain, limit=1)
        
        if patient:
            return {
                'exists': True,
                'patient_id': patient.id,
                'name': patient.name,
                'message': _('Welcome back! We found your records.'),
            }
        else:
            return {
                'exists': False,
                'message': _('Looks like you are a new patient. Please complete the registration.'),
            }

    @http.route('/appointment/book', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def appointment_book_snippet_submit(self, **post):
        """
        TASK-F1-007: Handle form submission from website builder snippet
        Simplified booking for snippet-based appointments
        """
        # Validate required fields
        required_fields = ['appointment_type_id', 'preferred_date', 'patient_name',
                          'patient_email', 'patient_phone']

        for field in required_fields:
            if not post.get(field):
                return request.render('clinic_appointment_web.booking_error', {
                    'error_message': _('Please fill in all required fields: %s') % field,
                })

        # Validate terms acceptance
        if not post.get('accept_terms'):
            return request.render('clinic_appointment_web.booking_error', {
                'error_message': _('You must accept the privacy policy to continue.'),
            })

        try:
            # Find or create patient
            patient = request.env['clinic.patient'].sudo().search([
                '|',
                ('email', '=', post.get('patient_email')),
                ('mobile', '=', post.get('patient_phone')),
            ], limit=1)

            if not patient:
                # Create new patient
                patient_vals = {
                    'name': post.get('patient_name'),
                    'email': post.get('patient_email'),
                    'mobile': post.get('patient_phone'),
                    'date_of_birth': post.get('patient_dob') if post.get('patient_dob') else False,
                }
                patient = request.env['clinic.patient'].sudo().create(patient_vals)

            # Create appointment or booking request
            appointment_vals = {
                'patient_id': patient.id,
                'appointment_type_id': int(post.get('appointment_type_id')),
                'staff_id': int(post.get('staff_id')) if post.get('staff_id') else False,
                'start': post.get('preferred_date'),  # Will need to be enhanced with time selection
                'notes': post.get('notes', ''),
                'state': 'draft',  # Start as draft, requires confirmation
                'booking_source': 'website_snippet',
            }

            # For now, create a draft appointment that requires secretary approval
            appointment = request.env['clinic.appointment'].sudo().create(appointment_vals)

            # Send notification email to patient
            template = request.env.ref('clinic_appointment_core.email_template_appointment_confirmation',
                                      raise_if_not_found=False)
            if template:
                template.sudo().send_mail(appointment.id, force_send=True)

            # Render success page
            return request.render('clinic_appointment_web.booking_success', {
                'appointment': appointment,
                'patient': patient,
            })

        except Exception as e:
            _logger.error("Snippet booking error: %s", str(e), exc_info=True)
            return request.render('clinic_appointment_web.booking_error', {
                'error_message': _('An error occurred while processing your appointment. Please try again or contact us directly.'),
                'technical_error': str(e) if request.env.user.has_group('base.group_system') else None,
            })

    # TASK-F3-001: Flexible Times Booking Routes
    @http.route('/appointment/flexible-times/<string:token>', type='http', auth='public', website=True, csrf=False)
    def book_flexible_time(self, token, **kwargs):
        """Allow patient to view and book from flexible time options"""
        try:
            from odoo import fields as odoo_fields
            # Find share record by token
            share = request.env['clinic.appointment.flexible.share'].sudo().search([
                ('access_token', '=', token),
                ('state', '=', 'pending')
            ], limit=1)

            if not share:
                return request.render('clinic_appointment_web.flexible_times_invalid', {
                    'message': _('This link is invalid or has already been used.')
                })

            # Check if expired
            if share.token_expires_at < odoo_fields.Datetime.now():
                share.state = 'expired'
                return request.render('clinic_appointment_web.flexible_times_expired', {
                    'message': _('This link has expired. Please contact the clinic for new options.')
                })

            # Increment view count
            share.views_count += 1
            share.last_viewed_at = odoo_fields.Datetime.now()

            # Get available slots
            available_slots = share.slot_ids.filtered(lambda s: s.status == 'available')

            return request.render('clinic_appointment_web.flexible_times_selection', {
                'share': share,
                'slots': available_slots,
                'patient': share.patient_id,
                'appointment_type': share.appointment_type_id,
            })

        except Exception as e:
            _logger.error(f"Error in flexible times booking: {str(e)}", exc_info=True)
            return request.render('clinic_appointment_web.flexible_times_error', {
                'error': str(e)
            })

    @http.route('/appointment/flexible-times/<string:token>/confirm/<int:slot_id>',
                type='http', auth='public', website=True, csrf=False)
    def confirm_flexible_time(self, token, slot_id, **kwargs):
        """Confirm booking of a specific slot from flexible options"""
        try:
            share = request.env['clinic.appointment.flexible.share'].sudo().search([
                ('access_token', '=', token),
                ('state', '=', 'pending')
            ], limit=1)

            if not share:
                return request.render('clinic_appointment_web.flexible_times_invalid')

            slot = request.env['clinic.appointment.slot'].sudo().browse(slot_id)

            if not slot.exists() or slot.id not in share.slot_ids.ids:
                return request.render('clinic_appointment_web.flexible_times_invalid', {
                    'message': _('Invalid slot selection.')
                })

            if slot.status != 'available':
                return request.render('clinic_appointment_web.flexible_times_unavailable', {
                    'message': _('This time slot is no longer available.')
                })

            # Create appointment
            start_datetime = datetime.combine(slot.date, datetime.min.time())
            start_datetime = start_datetime.replace(hour=int(slot.start_time),
                                                   minute=int((slot.start_time % 1) * 60))

            end_datetime = datetime.combine(slot.date, datetime.min.time())
            end_datetime = end_datetime.replace(hour=int(slot.end_time),
                                               minute=int((slot.end_time % 1) * 60))

            appointment = request.env['clinic.appointment'].sudo().create({
                'patient_id': share.patient_id.id,
                'appointment_type_id': share.appointment_type_id.id,
                'staff_id': slot.staff_id.id,
                'branch_id': slot.branch_id.id,
                'room_id': slot.room_id.id if slot.room_id else False,
                'start': start_datetime,
                'stop': end_datetime,
                'booking_method': 'online',
                'notes': f"Booked via flexible times link (token: {token[:8]}...)",
            })

            # Update slot status
            slot.status = 'booked'
            slot.appointment_id = appointment.id

            # Update share record
            share.write({
                'state': 'selected',
                'selected_slot_id': slot.id,
                'appointment_id': appointment.id,
            })

            # Send confirmation
            appointment._send_confirmation_email()

            return request.render('clinic_appointment_web.flexible_times_success', {
                'appointment': appointment,
                'patient': share.patient_id,
            })

        except Exception as e:
            _logger.error(f"Error confirming flexible time: {str(e)}", exc_info=True)
            return request.render('clinic_appointment_web.flexible_times_error', {
                'error': str(e)
            })