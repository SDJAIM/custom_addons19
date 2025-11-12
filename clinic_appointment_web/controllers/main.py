# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from datetime import datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)


class AppointmentBookingController(http.Controller):
    
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