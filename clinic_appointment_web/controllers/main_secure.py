# -*- coding: utf-8 -*-

from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import json
import logging
import requests
import hashlib
import hmac
from werkzeug.exceptions import Forbidden

_logger = logging.getLogger(__name__)


class SecureAppointmentBookingController(http.Controller):
    """
    Enhanced appointment booking controller with security features:
    - Rate limiting
    - CAPTCHA validation
    - CSRF protection
    - Input validation
    """

    def _verify_recaptcha(self, response):
        """Verify Google reCAPTCHA response"""
        # Get reCAPTCHA secret from system parameters
        IrConfig = request.env['ir.config_parameter'].sudo()
        secret_key = IrConfig.get_param('clinic.recaptcha.secret_key')

        if not secret_key:
            _logger.warning("reCAPTCHA secret key not configured")
            return True  # Allow if not configured (for testing)

        # Verify with Google
        verify_url = 'https://www.google.com/recaptcha/api/siteverify'

        data = {
            'secret': secret_key,
            'response': response,
            'remoteip': request.httprequest.remote_addr
        }

        try:
            resp = requests.post(verify_url, data=data, timeout=5)
            result = resp.json()

            if not result.get('success'):
                _logger.warning(f"reCAPTCHA verification failed: {result.get('error-codes')}")
                return False

            # Check score for v3 (optional)
            score = result.get('score', 1.0)
            if score < 0.5:
                _logger.warning(f"reCAPTCHA score too low: {score}")
                return False

            return True

        except Exception as e:
            _logger.error(f"reCAPTCHA verification error: {str(e)}")
            return False

    def _check_rate_limit(self, resource='booking'):
        """Check rate limiting for current client"""
        RateLimit = request.env['clinic.rate_limit'].sudo()

        # Get client identifier
        client_id = self._get_client_id()

        # Check and update rate limit
        result = RateLimit.check_and_update_rate_limit(
            client_id=client_id,
            resource=resource,
            max_attempts=5,  # 5 attempts
            window_minutes=60  # per hour
        )

        if not result['allowed']:
            raise Forbidden(_("Too many requests. Please try again later."))

        # Add headers to response
        request.httprequest.headers['X-RateLimit-Remaining'] = str(result['remaining'])

        return result

    def _get_client_id(self):
        """Generate unique client identifier"""
        ip = request.httprequest.remote_addr or 'unknown'
        session_id = request.session.sid or 'anonymous'
        user_agent = request.httprequest.user_agent.string[:200] if request.httprequest.user_agent else ''

        # Create hash for privacy
        raw = f"{ip}:{session_id}:{user_agent}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _validate_booking_data(self, data):
        """Validate and sanitize booking form data"""
        errors = {}

        # Required fields
        required = ['first_name', 'last_name', 'email', 'phone', 'date', 'slot_id']
        for field in required:
            if not data.get(field):
                errors[field] = _("This field is required")

        # Email validation
        if data.get('email'):
            import re
            if not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
                errors['email'] = _("Invalid email format")

        # Phone validation
        if data.get('phone'):
            import re
            # Basic phone validation (customize as needed)
            if not re.match(r"^[\d\s\-\+\(\)]+$", data['phone']):
                errors['phone'] = _("Invalid phone format")

        # Date validation
        if data.get('date'):
            try:
                date_obj = datetime.strptime(data['date'], '%Y-%m-%d').date()
                min_date = datetime.now().date() + timedelta(days=7)
                if date_obj < min_date:
                    errors['date'] = _("Appointments must be booked at least one week in advance")
            except ValueError:
                errors['date'] = _("Invalid date format")

        return errors

    @http.route('/appointment/book', type='http', auth='public', website=True,
                sitemap=True, csrf=True)
    def appointment_book_page(self, **kw):
        """Main booking page with security features"""

        # Get reCAPTCHA site key
        IrConfig = request.env['ir.config_parameter'].sudo()
        site_key = IrConfig.get_param('clinic.recaptcha.site_key')

        # Get available services
        services = request.env['clinic.appointment.type'].sudo().search([
            ('available_online', '=', True)
        ])

        # Get branches
        branches = request.env['clinic.branch'].sudo().search([
            ('active', '=', True)
        ])

        # Get minimum booking date (next week)
        min_date = datetime.now().date() + timedelta(days=7)

        values = {
            'services': services,
            'branches': branches,
            'min_date': min_date.isoformat(),
            'recaptcha_site_key': site_key,
            'page_name': 'appointment_booking',
        }

        return request.render('clinic_appointment_web.booking_form_secure', values)

    @http.route('/appointment/submit', type='http', auth='public', website=True,
                methods=['POST'], csrf=True)
    def submit_booking(self, **post):
        """Submit appointment booking with full security"""

        # 1. Check rate limiting
        try:
            self._check_rate_limit('appointment_submit')
        except Forbidden as e:
            return request.render('clinic_appointment_web.rate_limit_error', {
                'message': str(e)
            })

        # 2. Verify CAPTCHA
        recaptcha_response = post.get('g-recaptcha-response')
        if not self._verify_recaptcha(recaptcha_response):
            return request.render('clinic_appointment_web.booking_form_secure', {
                'error': _('CAPTCHA verification failed. Please try again.'),
                'values': post
            })

        # 3. Validate input data
        errors = self._validate_booking_data(post)
        if errors:
            return request.render('clinic_appointment_web.booking_form_secure', {
                'errors': errors,
                'values': post
            })

        # 4. Create booking request
        try:
            BookingRequest = request.env['clinic.booking.request'].sudo()

            # Prepare values
            values = {
                'first_name': post.get('first_name'),
                'last_name': post.get('last_name'),
                'email': post.get('email'),
                'phone': post.get('phone'),
                'birth_date': post.get('birth_date') or False,
                'preferred_date': post.get('date'),
                'appointment_type_id': int(post.get('appointment_type_id')) if post.get('appointment_type_id') else False,
                'branch_id': int(post.get('branch_id')) if post.get('branch_id') else False,
                'staff_preference_id': int(post.get('staff_id')) if post.get('staff_id') else False,
                'service_type': post.get('service_type', 'medical'),
                'notes': post.get('notes', ''),
                'insurance_info': post.get('insurance_info', ''),
                'urgency': post.get('urgency', 'medium'),
                'session_id': request.session.sid,
                'ip_address': request.httprequest.remote_addr,
                'user_agent': request.httprequest.user_agent.string[:200] if request.httprequest.user_agent else '',
            }

            # Create booking
            booking = BookingRequest.create(values)

            # Send confirmation email
            booking._send_confirmation_email()

            # Log successful booking
            _logger.info(f"Booking created: {booking.id} for {booking.email}")

            # Redirect to success page
            return request.render('clinic_appointment_web.booking_success', {
                'booking': booking,
                'reference': booking.reference
            })

        except Exception as e:
            _logger.error(f"Booking creation error: {str(e)}")
            return request.render('clinic_appointment_web.booking_form_secure', {
                'error': _("An error occurred. Please try again later."),
                'values': post
            })

    @http.route('/appointment/slots/json', type='json', auth='public', website=True)
    def get_available_slots_json(self, date, branch_id=None, staff_id=None, **kw):
        """Get available slots with rate limiting"""

        # Check rate limit for slot queries
        RateLimit = request.env['clinic.rate_limit'].sudo()
        client_id = self._get_client_id()

        result = RateLimit.check_and_update_rate_limit(
            client_id=client_id,
            resource='slot_query',
            max_attempts=20,  # More lenient for AJAX calls
            window_minutes=1  # Per minute
        )

        if not result['allowed']:
            return {
                'error': _('Too many requests. Please wait a moment.'),
                'rate_limited': True
            }

        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return {'error': _('Invalid date format')}

        # Get available slots
        Appointment = request.env['clinic.appointment'].sudo()

        slots = []

        # Generate time slots (9 AM to 5 PM, 30 min intervals)
        start_time = datetime.combine(date_obj, datetime.min.time()).replace(hour=9)
        end_time = datetime.combine(date_obj, datetime.min.time()).replace(hour=17)

        current_time = start_time
        while current_time < end_time:
            # Check availability
            domain = [
                ('start', '>=', current_time),
                ('start', '<', current_time + timedelta(minutes=30)),
                ('state', 'not in', ['cancelled', 'no_show'])
            ]

            if branch_id:
                domain.append(('branch_id', '=', int(branch_id)))
            if staff_id:
                domain.append(('staff_id', '=', int(staff_id)))

            existing = Appointment.search_count(domain)

            if not existing:
                slots.append({
                    'time': current_time.strftime('%H:%M'),
                    'datetime': current_time.isoformat(),
                    'available': True
                })

            current_time += timedelta(minutes=30)

        return {
            'success': True,
            'slots': slots,
            'remaining_requests': result['remaining']
        }

    @http.route('/appointment/verify/<token>', type='http', auth='public', website=True)
    def verify_booking(self, token, **kw):
        """Verify email for booking confirmation"""

        BookingRequest = request.env['clinic.booking.request'].sudo()

        booking = BookingRequest.search([
            ('verification_token', '=', token),
            ('state', '=', 'pending')
        ], limit=1)

        if not booking:
            return request.render('clinic_appointment_web.verification_error', {
                'message': _('Invalid or expired verification link.')
            })

        # Mark as verified
        booking.write({
            'state': 'verified',
            'verified_date': fields.Datetime.now()
        })

        return request.render('clinic_appointment_web.verification_success', {
            'booking': booking
        })

    @http.route('/appointment/cancel/<token>', type='http', auth='public', website=True)
    def cancel_booking(self, token, **kw):
        """Cancel booking with token"""

        # Rate limit cancellations
        try:
            self._check_rate_limit('booking_cancel')
        except Forbidden:
            return request.render('clinic_appointment_web.rate_limit_error', {
                'message': _('Too many cancellation attempts.')
            })

        BookingRequest = request.env['clinic.booking.request'].sudo()

        booking = BookingRequest.search([
            ('cancellation_token', '=', token),
            ('state', 'not in', ['cancelled', 'done'])
        ], limit=1)

        if not booking:
            return request.render('clinic_appointment_web.cancellation_error', {
                'message': _('Invalid cancellation link or booking already processed.')
            })

        # Cancel booking
        booking.action_cancel()

        return request.render('clinic_appointment_web.cancellation_success', {
            'booking': booking
        })