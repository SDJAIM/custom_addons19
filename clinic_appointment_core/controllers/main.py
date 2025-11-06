# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import ValidationError, AccessError
from datetime import datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)


class AppointmentBookingController(http.Controller):
    """
    Public appointment booking controller
    Replicates Odoo Enterprise Appointments booking flow
    """

    # ========================
    # Public Booking Pages
    # ========================

    @http.route('/appointment/book/<int:type_id>', type='http', auth='public', website=True)
    def appointment_booking_start(self, type_id, **kwargs):
        """Start booking flow - show appointment type details"""
        AppointmentType = request.env['clinic.appointment.type'].sudo()

        appt_type = AppointmentType.browse(type_id)

        if not appt_type.exists() or not appt_type.allow_online_booking:
            return request.render('clinic_appointment_core.appointment_not_available', {
                'message': _('This appointment type is not available for online booking.')
            })

        return request.render('clinic_appointment_core.appointment_booking_start', {
            'appointment_type': appt_type,
        })

    @http.route('/appointment/book/<int:type_id>/slots', type='http', auth='public', website=True)
    def appointment_booking_slots(self, type_id, timezone='UTC', staff_id=None, **kwargs):
        """Show available slots for booking"""
        AppointmentType = request.env['clinic.appointment.type'].sudo()
        SlotEngine = request.env['clinic.appointment.slot.engine'].sudo()

        appt_type = AppointmentType.browse(type_id)

        if not appt_type.exists() or not appt_type.allow_online_booking:
            return request.redirect('/appointment/book/%s' % type_id)

        # Get user timezone (from browser or default)
        user_timezone = timezone or request.env.context.get('tz') or 'UTC'

        # Calculate date range
        today = datetime.now().date()
        start_date = today + timedelta(hours=appt_type.min_notice_hours / 24)
        end_date = today + timedelta(days=appt_type.max_days_ahead)

        # Generate slots
        try:
            staff_id_int = int(staff_id) if staff_id else None
            slots = SlotEngine.generate_slots(
                type_id,
                start_date,
                end_date,
                timezone=user_timezone,
                staff_id=staff_id_int
            )

            # Group slots by date
            slots_by_date = {}
            for slot in slots:
                if slot['available']:
                    slot_date = slot['start'].date()
                    if slot_date not in slots_by_date:
                        slots_by_date[slot_date] = []
                    slots_by_date[slot_date].append(slot)

        except Exception as e:
            _logger.error("Error generating slots: %s", str(e))
            slots_by_date = {}

        # Get staff list for selection
        staff_list = appt_type.allowed_staff_ids if appt_type.assign_mode == 'customer_choice' else []

        return request.render('clinic_appointment_core.appointment_booking_slots', {
            'appointment_type': appt_type,
            'slots_by_date': slots_by_date,
            'timezone': user_timezone,
            'staff_list': staff_list,
            'selected_staff_id': staff_id_int if staff_id else None,
        })

    @http.route('/appointment/book/<int:type_id>/info', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def appointment_booking_info(self, type_id, slot_start, slot_end, staff_id, **kwargs):
        """Collect customer information"""
        AppointmentType = request.env['clinic.appointment.type'].sudo()

        appt_type = AppointmentType.browse(type_id)

        if not appt_type.exists():
            return request.redirect('/appointment/book/%s' % type_id)

        # Parse slot times
        try:
            start_dt = datetime.fromisoformat(slot_start)
            end_dt = datetime.fromisoformat(slot_end)
        except ValueError:
            return request.redirect('/appointment/book/%s/slots' % type_id)

        # Get questionnaire
        questionnaire_lines = request.env['clinic.appointment.questionnaire.line'].sudo().search([
            ('type_id', '=', type_id),
            ('active', '=', True)
        ], order='sequence')

        if request.httprequest.method == 'POST':
            # Process form submission
            return self._process_booking_info(type_id, slot_start, slot_end, staff_id, questionnaire_lines, **kwargs)

        return request.render('clinic_appointment_core.appointment_booking_info', {
            'appointment_type': appt_type,
            'slot_start': start_dt,
            'slot_end': end_dt,
            'staff_id': int(staff_id),
            'staff_name': request.env['hr.employee'].sudo().browse(int(staff_id)).name,
            'questionnaire_lines': questionnaire_lines,
        })

    def _process_booking_info(self, type_id, slot_start, slot_end, staff_id, questionnaire_lines, **kwargs):
        """Process booking form and create appointment"""
        Appointment = request.env['clinic.appointment'].sudo()
        Patient = request.env['clinic.patient'].sudo()

        try:
            # Parse dates
            start_dt = datetime.fromisoformat(slot_start)
            end_dt = datetime.fromisoformat(slot_end)

            # Get or create patient
            patient_name = kwargs.get('patient_name')
            patient_email = kwargs.get('patient_email')
            patient_phone = kwargs.get('patient_phone')

            if not all([patient_name, patient_email]):
                raise ValidationError(_('Name and email are required'))

            # Search for existing patient by email
            patient = Patient.search([('email', '=', patient_email)], limit=1)

            if not patient:
                # Create new patient
                patient = Patient.create({
                    'name': patient_name,
                    'email': patient_email,
                    'mobile': patient_phone or '',
                })

            # Get default branch and type
            branch = request.env['clinic.branch'].sudo().search([], limit=1)
            if not branch:
                raise ValidationError(_('No branch configured'))

            # Create appointment
            appointment_vals = {
                'appointment_type_id': int(type_id),
                'patient_id': patient.id,
                'staff_id': int(staff_id),
                'branch_id': branch.id,
                'start': start_dt,
                'stop': end_dt,
                'booking_method': 'online',
                'service_type': 'medical',  # Default
                'name': f"{patient_name} - Online Booking",
            }

            appointment = Appointment.create(appointment_vals)

            # Save questionnaire answers
            QuestionnaireAnswer = request.env['clinic.appointment.questionnaire.answer'].sudo()
            for line in questionnaire_lines:
                answer_key = f'question_{line.id}'
                if answer_key in kwargs:
                    QuestionnaireAnswer.create({
                        'appointment_id': appointment.id,
                        'question_id': line.id,
                        'answer_text': kwargs[answer_key],
                    })

            # Redirect to confirmation page
            return request.redirect('/appointment/confirm/%s/%s' % (appointment.id, appointment.access_token))

        except Exception as e:
            _logger.error("Error creating appointment: %s", str(e))
            return request.render('clinic_appointment_core.appointment_booking_error', {
                'error_message': str(e),
                'type_id': type_id,
            })

    @http.route('/appointment/confirm/<int:appointment_id>/<string:token>', type='http', auth='public', website=True)
    def appointment_confirm(self, appointment_id, token, **kwargs):
        """Confirmation page after booking"""
        Appointment = request.env['clinic.appointment'].sudo()

        appointment = Appointment.search([
            ('id', '=', appointment_id),
            ('access_token', '=', token)
        ], limit=1)

        if not appointment:
            return request.render('clinic_appointment_core.appointment_not_found')

        # Mark as confirmed by customer
        if not appointment.confirmed_by_customer:
            appointment.write({
                'confirmed_by_customer': True,
                'confirmation_date': datetime.now(),
            })
            # Move to confirmed stage
            appointment.action_confirm()

        return request.render('clinic_appointment_core.appointment_confirm', {
            'appointment': appointment,
        })

    # ========================
    # Token-based Actions (Reschedule, Cancel)
    # ========================

    @http.route('/appointment/view/<int:appointment_id>/<string:token>', type='http', auth='public', website=True)
    def appointment_view(self, appointment_id, token, **kwargs):
        """View appointment details via token"""
        Appointment = request.env['clinic.appointment'].sudo()

        appointment = Appointment.search([
            ('id', '=', appointment_id),
            ('access_token', '=', token)
        ], limit=1)

        if not appointment:
            return request.render('clinic_appointment_core.appointment_not_found')

        return request.render('clinic_appointment_core.appointment_view', {
            'appointment': appointment,
        })

    @http.route('/appointment/reschedule/<int:appointment_id>/<string:token>', type='http', auth='public', website=True)
    def appointment_reschedule(self, appointment_id, token, **kwargs):
        """Reschedule appointment via token"""
        Appointment = request.env['clinic.appointment'].sudo()

        appointment = Appointment.search([
            ('id', '=', appointment_id),
            ('access_token', '=', token)
        ], limit=1)

        if not appointment:
            return request.render('clinic_appointment_core.appointment_not_found')

        # Check if rescheduling is allowed
        if not appointment.appointment_type_id.allow_reschedule:
            return request.render('clinic_appointment_core.appointment_action_not_allowed', {
                'message': _('Rescheduling is not allowed for this appointment type.')
            })

        # Check time limit
        hours_until = (appointment.start - datetime.now()).total_seconds() / 3600
        if hours_until < appointment.appointment_type_id.reschedule_limit_hours:
            return request.render('clinic_appointment_core.appointment_action_not_allowed', {
                'message': _('Rescheduling is only allowed %s hours before the appointment.') %
                           appointment.appointment_type_id.reschedule_limit_hours
            })

        # Show available slots for rescheduling
        SlotEngine = request.env['clinic.appointment.slot.engine'].sudo()

        today = datetime.now().date()
        end_date = today + timedelta(days=appointment.appointment_type_id.max_days_ahead)

        slots = SlotEngine.generate_slots(
            appointment.appointment_type_id.id,
            datetime.now(),
            end_date,
            timezone=request.env.context.get('tz', 'UTC'),
            staff_id=appointment.staff_id.id
        )

        slots_by_date = {}
        for slot in slots:
            if slot['available']:
                slot_date = slot['start'].date()
                if slot_date not in slots_by_date:
                    slots_by_date[slot_date] = []
                slots_by_date[slot_date].append(slot)

        return request.render('clinic_appointment_core.appointment_reschedule', {
            'appointment': appointment,
            'slots_by_date': slots_by_date,
        })

    @http.route('/appointment/reschedule/<int:appointment_id>/<string:token>/confirm', type='http', auth='public', website=True, methods=['POST'])
    def appointment_reschedule_confirm(self, appointment_id, token, new_start, new_end, **kwargs):
        """Confirm reschedule"""
        Appointment = request.env['clinic.appointment'].sudo()

        appointment = Appointment.search([
            ('id', '=', appointment_id),
            ('access_token', '=', token)
        ], limit=1)

        if not appointment:
            return request.render('clinic_appointment_core.appointment_not_found')

        try:
            new_start_dt = datetime.fromisoformat(new_start)
            new_end_dt = datetime.fromisoformat(new_end)

            appointment.write({
                'start': new_start_dt,
                'stop': new_end_dt,
            })

            return request.redirect('/appointment/view/%s/%s' % (appointment_id, token))

        except Exception as e:
            _logger.error("Error rescheduling appointment: %s", str(e))
            return request.render('clinic_appointment_core.appointment_booking_error', {
                'error_message': str(e),
            })

    @http.route('/appointment/cancel/<int:appointment_id>/<string:token>', type='http', auth='public', website=True, methods=['GET', 'POST'])
    def appointment_cancel(self, appointment_id, token, **kwargs):
        """Cancel appointment via token"""
        Appointment = request.env['clinic.appointment'].sudo()

        appointment = Appointment.search([
            ('id', '=', appointment_id),
            ('access_token', '=', token)
        ], limit=1)

        if not appointment:
            return request.render('clinic_appointment_core.appointment_not_found')

        # Check if cancellation is allowed
        if not appointment.appointment_type_id.allow_cancel:
            return request.render('clinic_appointment_core.appointment_action_not_allowed', {
                'message': _('Cancellation is not allowed for this appointment type.')
            })

        # Check time limit
        hours_until = (appointment.start - datetime.now()).total_seconds() / 3600
        if hours_until < appointment.appointment_type_id.cancel_limit_hours:
            return request.render('clinic_appointment_core.appointment_action_not_allowed', {
                'message': _('Cancellation is only allowed %s hours before the appointment.') %
                           appointment.appointment_type_id.cancel_limit_hours
            })

        if request.httprequest.method == 'POST':
            # Confirm cancellation
            appointment.action_cancel()
            return request.render('clinic_appointment_core.appointment_cancelled', {
                'appointment': appointment,
            })

        return request.render('clinic_appointment_core.appointment_cancel_confirm', {
            'appointment': appointment,
        })

    # ========================
    # JSON API for AJAX calls
    # ========================

    @http.route('/appointment/api/slots', type='json', auth='public')
    def api_get_slots(self, type_id, start_date, end_date, timezone='UTC', staff_id=None):
        """JSON API to get available slots"""
        SlotEngine = request.env['clinic.appointment.slot.engine'].sudo()

        try:
            slots = SlotEngine.generate_slots(
                type_id,
                start_date,
                end_date,
                timezone=timezone,
                staff_id=staff_id
            )

            # Filter only available slots
            available_slots = [slot for slot in slots if slot['available']]

            return {
                'success': True,
                'slots': available_slots,
            }
        except Exception as e:
            _logger.error("Error getting slots: %s", str(e))
            return {
                'success': False,
                'error': str(e),
            }

    @http.route('/appointment/api/check_availability', type='json', auth='public')
    def api_check_availability(self, type_id, slot_start, slot_end, staff_id):
        """Check if specific slot is still available"""
        SlotEngine = request.env['clinic.appointment.slot.engine'].sudo()
        AppointmentType = request.env['clinic.appointment.type'].sudo()
        Staff = request.env['hr.employee'].sudo()

        try:
            appt_type = AppointmentType.browse(type_id)
            staff = Staff.browse(staff_id)

            start_dt = datetime.fromisoformat(slot_start)
            end_dt = datetime.fromisoformat(slot_end)

            is_available = SlotEngine._check_slot_availability(
                appt_type,
                start_dt,
                end_dt,
                staff
            )

            return {
                'success': True,
                'available': is_available,
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
