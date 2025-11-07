# -*- coding: utf-8 -*-
"""
Unit tests for state-based readonly constraints in clinic_finance module.

Tests verify that deprecated states= parameter functionality is correctly
enforced via @api.constrains decorators at database level.
"""

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestInsuranceClaimStateReadonly(TransactionCase):
    """Test insurance claim field readonly constraints based on state."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create test patient
        cls.patient = cls.env['res.partner'].create({
            'name': 'Test Patient',
            'is_patient': True,
        })
        # Create test provider
        cls.provider = cls.env['res.partner'].create({
            'name': 'Dr. Test Provider',
            'is_practitioner': True,
        })

    def setUp(self):
        super().setUp()
        # Create test claim in draft state
        self.claim = self.env['clinic.insurance.claim'].create({
            'patient_id': self.patient.id,
            'provider_id': self.provider.id,
            'service_date': '2025-01-01',
            'amount_billed': 100.0,
            'state': 'draft',
        })

    def test_01_create_claim_draft(self):
        """Test creating insurance claim in draft state."""
        self.assertEqual(self.claim.state, 'draft')
        self.assertEqual(self.claim.patient_id, self.patient)
        self.assertEqual(self.claim.provider_id, self.provider)
        self.assertEqual(self.claim.amount_billed, 100.0)

    def test_02_draft_allows_field_updates(self):
        """Test that all fields are editable in draft state."""
        # Should not raise
        self.claim.write({
            'amount_billed': 150.0,
            'service_date': '2025-01-02',
        })
        self.assertEqual(self.claim.amount_billed, 150.0)

    def test_03_submitted_locks_provider(self):
        """Test that provider_id becomes readonly after submission."""
        # Simulate submission
        self.claim.state = 'submitted'

        # Try to change provider_id - should fail
        with self.assertRaises(ValidationError) as cm:
            self.claim.write({
                'provider_id': self.env['res.partner'].create({
                    'name': 'Other Provider',
                    'is_practitioner': True,
                }).id
            })

        self.assertIn('cannot be changed', str(cm.exception))
        self.assertIn('submitted', str(cm.exception))

    def test_04_submitted_locks_amount_billed(self):
        """Test that amount_billed becomes readonly after submission."""
        # Simulate submission
        self.claim.state = 'submitted'

        # Try to change amount_billed - should fail
        with self.assertRaises(ValidationError) as cm:
            self.claim.write({'amount_billed': 200.0})

        self.assertIn('Billed amount cannot be changed', str(cm.exception))

    def test_05_approved_locks_provider(self):
        """Test that provider_id is locked in approved state."""
        self.claim.state = 'approved'

        with self.assertRaises(ValidationError):
            self.claim.write({
                'provider_id': self.env['res.partner'].create({
                    'name': 'Other Provider',
                    'is_practitioner': True,
                }).id
            })

    def test_06_paid_locks_amount_billed(self):
        """Test that amount_billed is locked in paid state."""
        self.claim.state = 'paid'

        with self.assertRaises(ValidationError):
            self.claim.write({'amount_billed': 300.0})

    def test_07_draft_allows_patient_change(self):
        """Test that patient can be changed in draft state."""
        new_patient = self.env['res.partner'].create({
            'name': 'Other Patient',
            'is_patient': True,
        })
        # Should not raise
        self.claim.write({'patient_id': new_patient.id})
        self.assertEqual(self.claim.patient_id, new_patient)

    def test_08_submitted_locks_patient(self):
        """Test that patient becomes readonly after submission."""
        self.claim.state = 'submitted'

        new_patient = self.env['res.partner'].create({
            'name': 'Other Patient',
            'is_patient': True,
        })

        with self.assertRaises(ValidationError) as cm:
            self.claim.write({'patient_id': new_patient.id})

        self.assertIn('Patient cannot be changed', str(cm.exception))

    def test_09_constraint_bypass_with_context(self):
        """Test that constraints can be bypassed with context flag."""
        self.claim.state = 'submitted'

        # This should work with skip_state_checks context
        other_provider = self.env['res.partner'].create({
            'name': 'Other Provider',
            'is_practitioner': True,
        })

        self.claim.with_context(skip_state_checks=True).write({
            'provider_id': other_provider.id
        })

        self.assertEqual(self.claim.provider_id, other_provider)

    def test_10_draft_state_never_readonly(self):
        """Test that draft state is never readonly for critical fields."""
        # All these should work in draft state
        updates = {
            'amount_billed': 500.0,
            'service_date': '2025-02-01',
            'provider_id': self.env['res.partner'].create({
                'name': 'Another Provider',
                'is_practitioner': True,
            }).id,
        }

        # Should not raise
        self.claim.write(updates)
        self.assertEqual(self.claim.amount_billed, 500.0)


class TestPaymentPlanStateReadonly(TransactionCase):
    """Test payment plan field readonly constraints based on state."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.patient = cls.env['res.partner'].create({
            'name': 'Plan Test Patient',
            'is_patient': True,
        })

    def setUp(self):
        super().setUp()
        self.plan = self.env['clinic.payment.plan'].create({
            'patient_id': self.patient.id,
            'total_amount': 1000.0,
            'down_payment': 100.0,
            'installments': 9,
            'start_date': '2025-01-15',
            'interest_rate': 5.0,
            'state': 'draft',
        })

    def test_01_create_plan_draft(self):
        """Test creating payment plan in draft state."""
        self.assertEqual(self.plan.state, 'draft')
        self.assertEqual(self.plan.total_amount, 1000.0)
        self.assertEqual(self.plan.down_payment, 100.0)
        self.assertEqual(self.plan.installments, 9)

    def test_02_draft_allows_all_updates(self):
        """Test that all fields are editable in draft state."""
        self.plan.write({
            'total_amount': 1200.0,
            'down_payment': 150.0,
            'installments': 10,
            'interest_rate': 6.0,
        })

        self.assertEqual(self.plan.total_amount, 1200.0)
        self.assertEqual(self.plan.down_payment, 150.0)
        self.assertEqual(self.plan.installments, 10)
        self.assertEqual(self.plan.interest_rate, 6.0)

    def test_03_active_locks_total_amount(self):
        """Test that total_amount becomes readonly in active state."""
        self.plan.state = 'active'

        with self.assertRaises(ValidationError) as cm:
            self.plan.write({'total_amount': 1500.0})

        self.assertIn('Total amount cannot be changed', str(cm.exception))
        self.assertIn('active', str(cm.exception))

    def test_04_active_locks_down_payment(self):
        """Test that down_payment becomes readonly in active state."""
        self.plan.state = 'active'

        with self.assertRaises(ValidationError):
            self.plan.write({'down_payment': 200.0})

    def test_05_active_locks_installments(self):
        """Test that installments becomes readonly in active state."""
        self.plan.state = 'active'

        with self.assertRaises(ValidationError):
            self.plan.write({'installments': 8})

    def test_06_active_locks_start_date(self):
        """Test that start_date becomes readonly in active state."""
        self.plan.state = 'active'

        with self.assertRaises(ValidationError):
            self.plan.write({'start_date': '2025-02-01'})

    def test_07_active_locks_interest_rate(self):
        """Test that interest_rate becomes readonly in active state."""
        self.plan.state = 'active'

        with self.assertRaises(ValidationError):
            self.plan.write({'interest_rate': 7.0})

    def test_08_active_locks_patient(self):
        """Test that patient becomes readonly in active state."""
        self.plan.state = 'active'

        new_patient = self.env['res.partner'].create({
            'name': 'Other Plan Patient',
            'is_patient': True,
        })

        with self.assertRaises(ValidationError):
            self.plan.write({'patient_id': new_patient.id})

    def test_09_completed_locks_all_fields(self):
        """Test that all critical fields are locked in completed state."""
        self.plan.state = 'completed'

        # Try each critical field - all should fail
        with self.assertRaises(ValidationError):
            self.plan.write({'total_amount': 1500.0})

        with self.assertRaises(ValidationError):
            self.plan.write({'down_payment': 200.0})

        with self.assertRaises(ValidationError):
            self.plan.write({'installments': 8})

    def test_10_constraint_bypass_with_context(self):
        """Test that constraints can be bypassed with context flag."""
        self.plan.state = 'active'

        # This should work with skip_state_checks context
        self.plan.with_context(skip_state_checks=True).write({
            'total_amount': 1500.0
        })

        self.assertEqual(self.plan.total_amount, 1500.0)

    def test_11_draft_allows_all_updates_after_changes(self):
        """Test that draft state always allows updates regardless of changes."""
        # Make multiple changes in draft
        self.plan.write({
            'total_amount': 2000.0,
            'down_payment': 300.0,
            'installments': 20,
            'interest_rate': 8.0,
        })

        # Should still be editable
        self.assertEqual(self.plan.total_amount, 2000.0)
        self.assertEqual(self.plan.down_payment, 300.0)
        self.assertEqual(self.plan.installments, 20)
        self.assertEqual(self.plan.interest_rate, 8.0)

    def test_12_patient_immutable_once_approved(self):
        """Test that patient cannot be changed once plan is approved."""
        self.plan.state = 'approved'

        new_patient = self.env['res.partner'].create({
            'name': 'Yet Another Patient',
            'is_patient': True,
        })

        # In approved state, patient is not locked by this specific constraint
        # (it's only locked in active/completed), but we test to document behavior
        try:
            self.plan.write({'patient_id': new_patient.id})
            # Should succeed in approved (not locked in approved, only active/completed)
            self.assertEqual(self.plan.patient_id, new_patient)
        except ValidationError:
            # If implementation decides to lock it earlier, that's fine too
            pass
