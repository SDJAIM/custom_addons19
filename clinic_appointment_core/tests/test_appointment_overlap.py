# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestAppointmentOverlap(TransactionCase):
    """Test overlap detection in appointments"""

    def setUp(self):
        super().setUp()

        # Create test patient
        self.patient = self.env['clinic.patient'].create({
            'name': 'Test Patient',
            'email': 'patient@test.com',
            'mobile': '1234567890',
        })

        # Create test staff
        self.staff = self.env['clinic.staff'].create({
            'name': 'Dr. Test',
            'user_id': self.env.uid,
            'state': 'active',
        })

        # Create test branch
        self.branch = self.env['clinic.branch'].create({
            'name': 'Test Branch',
            'code': 'TEST',
        })

        # Create appointment type
        self.appointment_type = self.env['clinic.appointment.type'].create({
            'name': 'General Consultation',
            'default_duration': 1.0,
            'allow_online_booking': True,
        })

        # Base datetime for testing
        self.base_date = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    def test_appointment_no_overlap_different_staff(self):
        """Test that appointments with different staff don't cause overlap"""
        # Create first appointment
        appt1 = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date,
            'stop': self.base_date + timedelta(hours=1),
            'booking_method': 'manual',
            'service_type': 'medical',
        })

        # Create second staff member
        staff2 = self.env['clinic.staff'].create({
            'name': 'Dr. Test 2',
            'user_id': self.env.uid,
            'state': 'active',
        })

        # Create second appointment with different staff at same time - should succeed
        appt2 = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': staff2.id,
            'branch_id': self.branch.id,
            'start': self.base_date,
            'stop': self.base_date + timedelta(hours=1),
            'booking_method': 'manual',
            'service_type': 'medical',
        })

        self.assertTrue(appt1.id)
        self.assertTrue(appt2.id)

    def test_appointment_overlap_same_staff(self):
        """Test that overlapping appointments with same staff raise error"""
        # Create first appointment
        appt1 = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date,
            'stop': self.base_date + timedelta(hours=1),
            'booking_method': 'manual',
            'service_type': 'medical',
        })

        # Try to create overlapping appointment with same staff - should fail
        with self.assertRaises(ValidationError) as context:
            self.env['clinic.appointment'].create({
                'appointment_type_id': self.appointment_type.id,
                'patient_id': self.patient.id,
                'staff_id': self.staff.id,
                'branch_id': self.branch.id,
                'start': self.base_date + timedelta(minutes=30),
                'stop': self.base_date + timedelta(hours=1, minutes=30),
                'booking_method': 'manual',
                'service_type': 'medical',
            })

        self.assertIn('overlaps', str(context.exception).lower())

    def test_appointment_overlap_cancelled_excluded(self):
        """Test that cancelled appointments are excluded from overlap check"""
        # Create and cancel first appointment
        appt1 = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date,
            'stop': self.base_date + timedelta(hours=1),
            'booking_method': 'manual',
            'service_type': 'medical',
        })

        # Cancel it
        appt1.action_cancel()

        # Create overlapping appointment - should succeed since first is cancelled
        appt2 = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date,
            'stop': self.base_date + timedelta(hours=1),
            'booking_method': 'manual',
            'service_type': 'medical',
        })

        self.assertTrue(appt2.id)

    def test_appointment_partial_overlap(self):
        """Test that partially overlapping appointments are detected"""
        # Create first appointment
        appt1 = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date,
            'stop': self.base_date + timedelta(hours=1),
            'booking_method': 'manual',
            'service_type': 'medical',
        })

        # Try to create appointment starting 30 min after first one starts - should fail
        with self.assertRaises(ValidationError) as context:
            self.env['clinic.appointment'].create({
                'appointment_type_id': self.appointment_type.id,
                'patient_id': self.patient.id,
                'staff_id': self.staff.id,
                'branch_id': self.branch.id,
                'start': self.base_date + timedelta(minutes=30),
                'stop': self.base_date + timedelta(hours=1, minutes=30),
                'booking_method': 'manual',
                'service_type': 'medical',
            })

        self.assertIn('overlaps', str(context.exception).lower())

    def test_appointment_adjacent_no_overlap(self):
        """Test that adjacent (non-overlapping) appointments are allowed"""
        # Create first appointment
        appt1 = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date,
            'stop': self.base_date + timedelta(hours=1),
            'booking_method': 'manual',
            'service_type': 'medical',
        })

        # Create appointment starting exactly when first one ends - should succeed
        appt2 = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date + timedelta(hours=1),
            'stop': self.base_date + timedelta(hours=2),
            'booking_method': 'manual',
            'service_type': 'medical',
        })

        self.assertTrue(appt2.id)
