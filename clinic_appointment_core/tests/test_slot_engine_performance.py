# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from datetime import datetime, timedelta, date
import time


@tagged('post_install', '-at_install', 'performance')
class TestSlotEnginePerformance(TransactionCase):
    """
    Performance Tests for Slot Engine (P0-002, P0-003)

    Tests verify:
    - N+1 query optimization (P0-002)
    - Cache effectiveness (P0-003)
    - Acceptable response times for slot generation
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test company
        cls.company = cls.env['res.company'].create({
            'name': 'Test Clinic Performance',
        })

        # Create branch
        cls.branch = cls.env['clinic.branch'].create({
            'name': 'Performance Test Branch',
            'company_id': cls.company.id,
        })

        # Create 10 staff members
        cls.staff_list = cls.env['clinic.staff']
        for i in range(10):
            staff = cls.env['clinic.staff'].create({
                'name': f'Dr. Performance {i}',
                'branch_ids': [(6, 0, [cls.branch.id])],
                'company_id': cls.company.id,
            })
            cls.staff_list |= staff

        # Create appointment type
        cls.appointment_type = cls.env['clinic.appointment.type'].create({
            'name': 'Performance Test Type',
            'default_duration': 0.5,  # 30 minutes
            'buffer_before': 0.0,
            'buffer_after': 0.0,
            'capacity_per_slot': 1,
            'allowed_staff_ids': [(6, 0, cls.staff_list.ids)],
        })

        # Create appointment rules (Mon-Fri, 8AM-5PM)
        for weekday in range(5):  # Monday to Friday
            cls.env['clinic.appointment.rule'].create({
                'name': f'Performance Rule Day {weekday}',
                'type_id': cls.appointment_type.id,
                'weekday': str(weekday),
                'hour_from': 8.0,
                'hour_to': 17.0,
                'timezone': 'UTC',
                'active': True,
            })

        # Create patient for appointments
        cls.patient = cls.env['clinic.patient'].sudo().create({
            'name': 'Performance Test Patient',
            'company_id': cls.company.id,
        })

    def test_01_query_count_without_appointments(self):
        """
        Test N+1 query prevention - baseline (no appointments)

        Verifies that adding more staff doesn't increase query count
        """
        start_date = date.today()
        end_date = start_date + timedelta(days=7)

        # Warm up cache
        self.env['clinic.appointment.slot.engine'].generate_slots(
            self.appointment_type.id,
            start_date,
            end_date,
            timezone='UTC'
        )

        # Clear cache to get accurate query count
        self.env['clinic.appointment.slot.engine']._invalidate_slot_cache()

        # Count queries
        with self.assertQueryCount(__limit=30):  # Should be low even with 10 staff
            slots = self.env['clinic.appointment.slot.engine'].generate_slots(
                self.appointment_type.id,
                start_date,
                end_date,
                timezone='UTC'
            )

        # Verify slots generated
        self.assertGreater(len(slots), 0, "Should generate slots")

    def test_02_query_count_with_many_appointments(self):
        """
        Test N+1 query prevention - with 50 appointments (P0-002)

        CRITICAL: Query count should remain constant regardless of appointment count
        """
        start_date = date.today() + timedelta(days=1)
        end_date = start_date + timedelta(days=7)

        # Create 50 appointments across different staff and times
        for i in range(50):
            staff = self.staff_list[i % len(self.staff_list)]
            appt_datetime = datetime.combine(
                start_date + timedelta(days=i % 7),
                datetime.min.time()
            ).replace(hour=9 + (i % 8))

            self.env['clinic.appointment'].create({
                'patient_id': self.patient.id,
                'staff_id': staff.id,
                'branch_id': self.branch.id,
                'appointment_type_id': self.appointment_type.id,
                'service_type': 'medical',
                'start': appt_datetime,
                'stop': appt_datetime + timedelta(hours=0.5),
            })

        # Clear cache
        self.env['clinic.appointment.slot.engine']._invalidate_slot_cache()

        # Count queries - should be similar to test_01 despite 50 appointments
        with self.assertQueryCount(__limit=35):  # Allow slight increase, but not N+1
            slots = self.env['clinic.appointment.slot.engine'].generate_slots(
                self.appointment_type.id,
                start_date,
                end_date,
                timezone='UTC'
            )

        # Verify some slots are unavailable due to appointments
        unavailable_slots = [s for s in slots if not s['available']]
        self.assertGreater(len(unavailable_slots), 0, "Some slots should be unavailable")

    def test_03_cache_effectiveness(self):
        """
        Test cache effectiveness (P0-003)

        Second call should be MUCH faster than first call
        """
        start_date = date.today()
        end_date = start_date + timedelta(days=30)  # 30 days

        # Clear cache
        self.env['clinic.appointment.slot.engine']._invalidate_slot_cache()

        # First call (cold cache)
        start_time = time.time()
        slots_1 = self.env['clinic.appointment.slot.engine'].generate_slots(
            self.appointment_type.id,
            start_date,
            end_date,
            timezone='UTC'
        )
        first_duration = time.time() - start_time

        # Second call (warm cache) - should hit @ormcache
        start_time = time.time()
        slots_2 = self.env['clinic.appointment.slot.engine'].generate_slots(
            self.appointment_type.id,
            start_date,
            end_date,
            timezone='UTC'
        )
        second_duration = time.time() - start_time

        # Verify cache hit
        self.assertEqual(len(slots_1), len(slots_2), "Same slots should be returned")

        # Second call should be at least 5x faster (cached)
        self.assertLess(
            second_duration,
            first_duration / 5,
            f"Cached call ({second_duration:.4f}s) should be much faster than first call ({first_duration:.4f}s)"
        )

    def test_04_cache_invalidation_on_appointment_create(self):
        """
        Test cache invalidation when appointment is created (P0-003)

        Verifies that new appointments invalidate the cache
        """
        start_date = date.today()
        end_date = start_date + timedelta(days=7)

        # Generate slots (populate cache)
        slots_before = self.env['clinic.appointment.slot.engine'].generate_slots(
            self.appointment_type.id,
            start_date,
            end_date,
            timezone='UTC'
        )

        available_before = [s for s in slots_before if s['available']]

        # Create appointment
        appt_datetime = datetime.combine(start_date, datetime.min.time()).replace(hour=10)
        self.env['clinic.appointment'].create({
            'patient_id': self.patient.id,
            'staff_id': self.staff_list[0].id,
            'branch_id': self.branch.id,
            'appointment_type_id': self.appointment_type.id,
            'service_type': 'medical',
            'start': appt_datetime,
            'stop': appt_datetime + timedelta(hours=0.5),
        })

        # Generate slots again (should reflect new appointment)
        slots_after = self.env['clinic.appointment.slot.engine'].generate_slots(
            self.appointment_type.id,
            start_date,
            end_date,
            timezone='UTC'
        )

        available_after = [s for s in slots_after if s['available']]

        # At least one slot should become unavailable
        self.assertLess(
            len(available_after),
            len(available_before),
            "Creating appointment should reduce available slots"
        )

    def test_05_cache_invalidation_on_rule_change(self):
        """
        Test cache invalidation when rule is modified (P0-003)

        Verifies that rule changes invalidate the cache
        """
        start_date = date.today()
        end_date = start_date + timedelta(days=7)

        # Generate slots (populate cache)
        slots_before = self.env['clinic.appointment.slot.engine'].generate_slots(
            self.appointment_type.id,
            start_date,
            end_date,
            timezone='UTC'
        )

        # Modify rule (change hours)
        rule = self.env['clinic.appointment.rule'].search([
            ('type_id', '=', self.appointment_type.id),
            ('weekday', '=', '0')  # Monday
        ], limit=1)

        rule.write({'hour_to': 12.0})  # Change end time to noon

        # Generate slots again (should reflect new hours)
        slots_after = self.env['clinic.appointment.slot.engine'].generate_slots(
            self.appointment_type.id,
            start_date,
            end_date,
            timezone='UTC'
        )

        # Fewer slots should be available (shorter day)
        self.assertLess(
            len(slots_after),
            len(slots_before),
            "Reducing hours should reduce total slots"
        )

    def test_06_response_time_30_days(self):
        """
        Test response time for 30-day slot generation

        Should complete in reasonable time (< 2 seconds without cache)
        """
        start_date = date.today()
        end_date = start_date + timedelta(days=30)

        # Clear cache
        self.env['clinic.appointment.slot.engine']._invalidate_slot_cache()

        # Time the generation
        start_time = time.time()
        slots = self.env['clinic.appointment.slot.engine'].generate_slots(
            self.appointment_type.id,
            start_date,
            end_date,
            timezone='UTC'
        )
        duration = time.time() - start_time

        # Verify slots generated
        self.assertGreater(len(slots), 0, "Should generate slots")

        # Should complete in reasonable time
        self.assertLess(
            duration,
            2.0,
            f"30-day slot generation took {duration:.3f}s (should be < 2s)"
        )

    def test_07_memory_efficiency_large_dataset(self):
        """
        Test memory efficiency with large appointment dataset

        Verifies that pre-loading doesn't cause memory issues
        """
        start_date = date.today() + timedelta(days=1)
        end_date = start_date + timedelta(days=30)

        # Create 200 appointments (stress test)
        for i in range(200):
            staff = self.staff_list[i % len(self.staff_list)]
            appt_datetime = datetime.combine(
                start_date + timedelta(days=i % 30),
                datetime.min.time()
            ).replace(hour=8 + (i % 9))

            self.env['clinic.appointment'].create({
                'patient_id': self.patient.id,
                'staff_id': staff.id,
                'branch_id': self.branch.id,
                'appointment_type_id': self.appointment_type.id,
                'service_type': 'medical',
                'start': appt_datetime,
                'stop': appt_datetime + timedelta(hours=0.5),
            })

        # Clear cache
        self.env['clinic.appointment.slot.engine']._invalidate_slot_cache()

        # Should handle large dataset without issues
        start_time = time.time()
        slots = self.env['clinic.appointment.slot.engine'].generate_slots(
            self.appointment_type.id,
            start_date,
            end_date,
            timezone='UTC'
        )
        duration = time.time() - start_time

        # Should still complete in reasonable time
        self.assertLess(
            duration,
            3.0,
            f"Generation with 200 appointments took {duration:.3f}s (should be < 3s)"
        )

        # Verify slots generated
        self.assertGreater(len(slots), 0, "Should generate slots")
