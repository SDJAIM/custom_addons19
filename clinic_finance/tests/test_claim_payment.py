# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta


class TestClaimPaymentFlow(TransactionCase):
    """Test clinic.insurance.claim payment workflow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test data
        cls.patient = cls.env['clinic.patient'].create({
            'name': 'Test Patient',
            'date_of_birth': '1990-01-01',
        })

        cls.insurance_company = cls.env['clinic.insurance.company'].create({
            'name': 'Test Insurance',
        })

        cls.policy = cls.env['clinic.insurance.policy'].create({
            'patient_id': cls.patient.id,
            'insurance_company_id': cls.insurance_company.id,
            'is_active': True,
        })

        cls.staff = cls.env['clinic.staff'].create({
            'name': 'Test Doctor',
            'is_practitioner': True,
        })

        cls.diagnosis = cls.env['clinic.diagnosis'].create({
            'name': 'Test Diagnosis',
        })

        cls.currency = cls.env.company.currency_id

        # Create a claim in draft state
        cls.claim = cls.env['clinic.insurance.claim'].create({
            'patient_id': cls.patient.id,
            'policy_id': cls.policy.id,
            'claim_type': 'medical',
            'service_date': date.today(),
            'provider_id': cls.staff.id,
            'primary_diagnosis_id': cls.diagnosis.id,
            'amount_billed': 1000.00,
            'currency_id': cls.currency.id,
        })

    def test_claim_workflow_happy_path(self):
        """Test complete workflow: draft -> submitted -> approved -> paid."""
        claim = self.claim

        # Assert initial state
        self.assertEqual(claim.state, 'draft')

        # Submit claim
        claim.action_submit()
        self.assertEqual(claim.state, 'submitted')
        self.assertIsNotNone(claim.submission_date)

        # Approve claim
        claim.amount_approved = 900.00
        claim.action_approve()
        self.assertEqual(claim.state, 'approved')
        self.assertIsNotNone(claim.response_date)

        # Mark as paid
        claim.action_mark_paid()
        self.assertEqual(claim.state, 'paid')
        self.assertEqual(claim.payment_date, date.today())
        self.assertEqual(claim.amount_paid, 900.00)

    def test_action_mark_paid_wrong_state(self):
        """Test action_mark_paid() raises error when not in 'approved' state."""
        claim = self.claim
        claim.amount_approved = 900.00

        # Try to mark as paid from draft state
        with self.assertRaises(UserError) as cm:
            claim.action_mark_paid()

        self.assertIn('Only approved claims', str(cm.exception))

    def test_action_mark_paid_no_approved_amount(self):
        """Test action_mark_paid() raises error when approved_amount is 0 or empty."""
        claim = self.claim
        claim.action_submit()
        claim.action_approve()  # amount_approved still 0

        claim.amount_approved = 0

        with self.assertRaises(UserError) as cm:
            claim.action_mark_paid()

        self.assertIn('greater than 0', str(cm.exception))

    def test_action_submit_no_lines(self):
        """Test action_submit() raises error when no claim lines."""
        claim = self.claim

        with self.assertRaises(UserError) as cm:
            claim.action_submit()

        self.assertIn('claim lines', str(cm.exception))

    def test_action_submit_requires_authorization(self):
        """Test action_submit() requires auth number if policy requires pre-auth."""
        claim = self.claim
        claim.policy_id.requires_preauth = True
        claim.requires_authorization = True

        with self.assertRaises(UserError) as cm:
            claim.action_submit()

        self.assertIn('Authorization number', str(cm.exception))

    def test_chatter_audit_trail(self):
        """Test that transitions create chatter messages for audit."""
        claim = self.claim
        claim.action_submit()

        # Check that message was posted
        messages = claim.message_ids
        self.assertTrue(any('submitted' in msg.body.lower() for msg in messages))

    def test_constraint_approved_amount_exceeds_billed(self):
        """Test constraint: approved amount cannot exceed billed amount."""
        claim = self.claim

        with self.assertRaises(ValidationError):
            claim.amount_approved = 1500.00

    def test_constraint_paid_exceeds_approved(self):
        """Test constraint: paid amount cannot exceed approved amount."""
        claim = self.claim
        claim.action_submit()
        claim.amount_approved = 900.00
        claim.action_approve()

        with self.assertRaises(ValidationError):
            claim.amount_paid = 950.00

    def test_action_cancel_from_draft(self):
        """Test action_cancel() from draft state."""
        claim = self.claim
        claim.action_cancel()
        self.assertEqual(claim.state, 'cancelled')

    def test_action_cancel_from_approved(self):
        """Test action_cancel() from approved state."""
        claim = self.claim
        claim.action_submit()
        claim.amount_approved = 900.00
        claim.action_approve()

        claim.action_cancel()
        self.assertEqual(claim.state, 'cancelled')

    def test_action_cancel_from_paid_raises(self):
        """Test action_cancel() from paid state raises error."""
        claim = self.claim
        claim.action_submit()
        claim.amount_approved = 900.00
        claim.action_approve()
        claim.action_mark_paid()

        with self.assertRaises(UserError):
            claim.action_cancel()

    def test_monetary_fields_use_currency(self):
        """Test that Monetary fields correctly use the currency_field attribute.

        Monetary fields in Odoo are stored as float in the database but rendered
        with currency context via the currency_field='currency_id' attribute.
        """
        claim = self.claim
        # Currency field is correctly set on the claim record
        self.assertEqual(claim.currency_id, self.currency)
        # Monetary field values are float-type in ORM, currency is via the record
        self.assertTrue(isinstance(claim.amount_billed, (int, float)))
        self.assertTrue(isinstance(claim.amount_approved, (int, float)))
        self.assertTrue(isinstance(claim.amount_paid, (int, float)))

    def test_action_register_partial_payment_approved(self):
        """Test action_register_partial_payment from approved state."""
        claim = self.claim
        claim.action_submit()
        claim.amount_approved = 900.00
        claim.action_approve()

        # Register first partial payment (400 of 900)
        claim.action_register_partial_payment(
            amount_paid=400.00,
            payment_reference='CHK-001'
        )

        self.assertEqual(claim.state, 'partially_paid')
        self.assertEqual(claim.amount_paid, 400.00)

        # Register second partial payment (500 of 900) -> should transition to paid
        claim.action_register_partial_payment(
            amount_paid=500.00,
            payment_reference='CHK-002'
        )

        self.assertEqual(claim.state, 'paid')
        self.assertEqual(claim.amount_paid, 900.00)

    def test_action_register_partial_payment_exceeds_approved(self):
        """Test action_register_partial_payment cannot exceed approved amount."""
        claim = self.claim
        claim.action_submit()
        claim.amount_approved = 900.00
        claim.action_approve()

        # Try to pay more than approved
        with self.assertRaises(UserError) as cm:
            claim.action_register_partial_payment(amount_paid=950.00)

        self.assertIn('cannot exceed approved', str(cm.exception).lower())

    def test_action_register_partial_payment_invalid_state(self):
        """Test action_register_partial_payment only works in approved/partially_paid states."""
        claim = self.claim

        # Try from draft
        with self.assertRaises(UserError) as cm:
            claim.action_register_partial_payment(amount_paid=100.00)

        self.assertIn('approved', str(cm.exception).lower())

    def test_write_restriction_patient_after_submit(self):
        """Test write() prevents patient_id change after submission."""
        claim = self.claim
        claim.action_submit()

        new_patient = self.env['clinic.patient'].create({
            'name': 'New Patient',
            'date_of_birth': '1995-01-01',
        })

        with self.assertRaises(UserError) as cm:
            claim.write({'patient_id': new_patient.id})

        self.assertIn('cannot change patient', str(cm.exception).lower())

    def test_write_restriction_provider_after_submit(self):
        """Test write() prevents provider_id change after submission."""
        claim = self.claim
        claim.action_submit()

        new_provider = self.env['clinic.staff'].create({
            'name': 'Another Doctor',
            'is_practitioner': True,
        })

        with self.assertRaises(UserError) as cm:
            claim.write({'provider_id': new_provider.id})

        self.assertIn('provider cannot be changed', str(cm.exception).lower())

    def test_write_restriction_amount_billed_after_submit(self):
        """Test write() prevents amount_billed change after submission."""
        claim = self.claim
        claim.action_submit()

        with self.assertRaises(UserError) as cm:
            claim.write({'amount_billed': 2000.00})

        self.assertIn('billed amount cannot be changed', str(cm.exception).lower())

    def test_write_restriction_direct_amount_paid_update(self):
        """Test write() prevents direct amount_paid modifications."""
        claim = self.claim
        claim.action_submit()
        claim.amount_approved = 900.00
        claim.action_approve()

        # Try to directly set amount_paid (should fail)
        with self.assertRaises(UserError) as cm:
            claim.write({'amount_paid': 700.00})

        self.assertIn('cannot be updated directly', str(cm.exception).lower())

    def test_patient_responsibility_computed_from_components(self):
        """Test patient_responsibility is computed from copay/deductible/coinsurance."""
        claim = self.claim
        claim.write({
            'copay_amount': 50.00,
            'deductible_amount': 200.00,
            'coinsurance_amount': 150.00,
        })

        # Flush to trigger compute
        claim.flush()

        expected = 50.00 + 200.00 + 150.00
        self.assertEqual(claim.patient_responsibility, expected)

    def test_days_outstanding_computation(self):
        """Test days_outstanding computation."""
        claim = self.claim
        claim.action_submit()

        # Move submission_date back 35 days
        old_date = date.today() - timedelta(days=35)
        claim.write({'submission_date': old_date})

        claim.flush()
        self.assertGreater(claim.days_outstanding, 30)
