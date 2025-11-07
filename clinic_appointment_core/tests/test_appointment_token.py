# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from odoo.tests import TransactionCase


class TestAppointmentToken(TransactionCase):
    """Test token generation and validation"""

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

    def test_token_generation_on_create(self):
        """Test that token is generated when appointment is created with online booking"""
        appt = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date,
            'stop': self.base_date + timedelta(hours=1),
            'booking_method': 'online',
            'service_type': 'medical',
        })

        # Token should be generated
        self.assertTrue(appt.access_token)
        self.assertGreater(len(appt.access_token), 20)

    def test_token_generation_manual(self):
        """Test that token can be generated manually for non-online appointments"""
        appt = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date,
            'stop': self.base_date + timedelta(hours=1),
            'booking_method': 'manual',
            'service_type': 'medical',
        })

        # No token initially
        self.assertFalse(appt.access_token)

        # Generate token manually
        token = appt._generate_access_token()

        self.assertTrue(token)
        self.assertEqual(appt.access_token, token)

    def test_token_unique(self):
        """Test that each appointment gets a unique token"""
        appt1 = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date,
            'stop': self.base_date + timedelta(hours=1),
            'booking_method': 'online',
            'service_type': 'medical',
        })

        appt2 = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date + timedelta(hours=2),
            'stop': self.base_date + timedelta(hours=3),
            'booking_method': 'online',
            'service_type': 'medical',
        })

        # Tokens should be different
        self.assertNotEqual(appt1.access_token, appt2.access_token)

    def test_booking_url_generation(self):
        """Test that booking URL is generated correctly"""
        appt = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date,
            'stop': self.base_date + timedelta(hours=1),
            'booking_method': 'online',
            'service_type': 'medical',
        })

        booking_url = appt.get_booking_url('view')

        # URL should contain appointment ID and token
        self.assertIn(str(appt.id), booking_url)
        self.assertIn(appt.access_token, booking_url)
        self.assertIn('/appointment/view/', booking_url)

    def test_token_lookup(self):
        """Test that appointment can be found by token"""
        appt = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date,
            'stop': self.base_date + timedelta(hours=1),
            'booking_method': 'online',
            'service_type': 'medical',
        })

        # Find by token
        found = self.env['clinic.appointment'].search([
            ('id', '=', appt.id),
            ('access_token', '=', appt.access_token)
        ])

        self.assertEqual(len(found), 1)
        self.assertEqual(found.id, appt.id)

    def test_token_invalid_lookup(self):
        """Test that invalid token doesn't find appointment"""
        appt = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date,
            'stop': self.base_date + timedelta(hours=1),
            'booking_method': 'online',
            'service_type': 'medical',
        })

        # Try to find with invalid token
        found = self.env['clinic.appointment'].search([
            ('id', '=', appt.id),
            ('access_token', '=', 'invalid_token_xyz')
        ])

        self.assertEqual(len(found), 0)

    def test_token_copy_not_copied(self):
        """Test that token is not copied when duplicating appointment"""
        appt1 = self.env['clinic.appointment'].create({
            'appointment_type_id': self.appointment_type.id,
            'patient_id': self.patient.id,
            'staff_id': self.staff.id,
            'branch_id': self.branch.id,
            'start': self.base_date,
            'stop': self.base_date + timedelta(hours=1),
            'booking_method': 'online',
            'service_type': 'medical',
        })

        # Copy the appointment
        appt2 = appt1.copy()

        # Token should be different or empty
        if appt2.access_token:
            self.assertNotEqual(appt1.access_token, appt2.access_token)
        else:
            # This is acceptable - copy may reset token
            self.assertFalse(appt2.access_token)
