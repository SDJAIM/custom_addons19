# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase
from datetime import date, timedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class TestCronExpiringLots(TransactionCase):
    """Test clinic.medication cron jobs for expiring lots and reorder levels."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create medication category
        cls.category = cls.env['product.category'].create({
            'name': 'Prescription Drugs'
        })

    def test_check_expiring_lots_within_window(self):
        """Test check_expiring_lots finds lots expiring within alert window."""
        # Create stock lot expiring in 15 days
        product = self.env['product.product'].create({
            'name': 'Test Medication 500mg',
            'type': 'product',
            'tracking': 'lot',
        })

        expiration_date = date.today() + timedelta(days=15)

        lot = self.env['stock.production.lot'].create({
            'name': 'LOT-2025-001',
            'product_id': product.id,
            'company_id': self.env.company.id,
            'expiration_date': expiration_date,
        })

        # Call cron with 30-day window
        expiring_lots = self.env['clinic.medication'].check_expiring_lots(days_before=30)

        # Verify lot was found
        self.assertIn(lot.id, expiring_lots.ids)

    def test_check_expiring_lots_outside_window(self):
        """Test check_expiring_lots ignores lots expiring after alert window."""
        product = self.env['product.product'].create({
            'name': 'Test Medication 200mg',
            'type': 'product',
            'tracking': 'lot',
        })

        # Create lot expiring in 45 days (outside 30-day window)
        expiration_date = date.today() + timedelta(days=45)

        lot = self.env['stock.production.lot'].create({
            'name': 'LOT-2025-002',
            'product_id': product.id,
            'company_id': self.env.company.id,
            'expiration_date': expiration_date,
        })

        # Call cron with 30-day window
        expiring_lots = self.env['clinic.medication'].check_expiring_lots(days_before=30)

        # Verify lot was NOT found
        self.assertNotIn(lot.id, expiring_lots.ids)

    def test_check_expiring_lots_already_expired(self):
        """Test check_expiring_lots ignores already-expired lots."""
        product = self.env['product.product'].create({
            'name': 'Test Medication 100mg',
            'type': 'product',
            'tracking': 'lot',
        })

        # Create already-expired lot
        expiration_date = date.today() - timedelta(days=10)

        lot = self.env['stock.production.lot'].create({
            'name': 'LOT-2024-999',
            'product_id': product.id,
            'company_id': self.env.company.id,
            'expiration_date': expiration_date,
        })

        expiring_lots = self.env['clinic.medication'].check_expiring_lots(days_before=30)

        # Verify lot was NOT found (it's already expired)
        self.assertNotIn(lot.id, expiring_lots.ids)

    def test_check_reorder_levels(self):
        """Test check_reorder_levels creates activity for low stock."""
        # Create medication with reorder level
        category = self.env['product.category'].create({
            'name': 'Test Meds'
        })

        product = self.env['product.product'].create({
            'name': 'Test Med for Reorder',
            'type': 'product',
            'categ_id': category.id,
        })

        med = self.env['clinic.medication'].create({
            'name': 'Test Reorder Med',
            'generic_name': 'Generic Test',
            'code': 'REORDER-001',
            'medication_form': 'tablet',
            'strength': '500mg',
            'track_inventory': True,
            'product_id': product.id,
            'reorder_level': 50.0,
        })

        # Mock low stock
        self.env['stock.quant'].create({
            'product_id': product.id,
            'location_id': self.env.ref('stock.stock_location_stock').id,
            'quantity': 30.0,
        })

        # Run cron
        low_stock = self.env['clinic.medication'].check_reorder_levels()

        # Verify medication was found or activity was created
        # (check_reorder_levels creates activities, not necessarily returns recordset)
        activities = self.env['mail.activity'].search([
            ('res_model_id.model', '=', 'clinic.medication'),
            ('res_id', '=', med.id),
        ])

        self.assertTrue(len(activities) > 0 or med.id in low_stock.ids)

    def test_cron_execution_idempotent(self):
        """Test that cron can be executed multiple times safely WITHOUT creating duplicate activities."""
        # Create medication and expiring lot
        product = self.env['product.product'].create({
            'name': 'Test Medication - Idempotency',
            'type': 'product',
            'tracking': 'lot',
        })

        expiration_date = date.today() + timedelta(days=15)

        lot = self.env['stock.production.lot'].create({
            'name': 'LOT-IDEMPOTENT-001',
            'product_id': product.id,
            'company_id': self.env.company.id,
            'expiration_date': expiration_date,
        })

        # First cron execution
        result1 = self.env['clinic.medication'].check_expiring_lots(days_before=30)
        self.assertIn(lot.id, result1.ids)

        # Count activities created for this lot
        activities_after_first_run = self.env['mail.activity'].search([
            ('res_model_id.model', '=', 'stock.production.lot'),
            ('res_id', '=', lot.id),
            ('state', '!=', 'done'),
        ])
        count_after_first = len(activities_after_first_run)
        self.assertGreater(count_after_first, 0, "First cron run should create activities")

        # Second cron execution (should NOT create duplicates)
        result2 = self.env['clinic.medication'].check_expiring_lots(days_before=30)
        self.assertIn(lot.id, result2.ids)

        # Count activities again - should be SAME as before (no new duplicates)
        activities_after_second_run = self.env['mail.activity'].search([
            ('res_model_id.model', '=', 'stock.production.lot'),
            ('res_id', '=', lot.id),
            ('state', '!=', 'done'),
        ])
        count_after_second = len(activities_after_second_run)

        self.assertEqual(
            count_after_first,
            count_after_second,
            "Second cron run should NOT create duplicate activities (idempotent)"
        )

    def test_medication_code_uniqueness_constraint(self):
        """Test that medication code must be unique (_sql_constraints)."""
        # Create first medication with code
        med1 = self.env['clinic.medication'].create({
            'name': 'Test Med Unique 1',
            'generic_name': 'Generic Test 1',
            'code': 'UNIQUE-TEST-001',
            'medication_form': 'tablet',
            'strength': '500mg',
        })
        self.assertEqual(med1.code, 'UNIQUE-TEST-001')

        # Try to create second medication with same code (should fail at DB level)
        from odoo.exceptions import IntegrityError
        with self.assertRaises(IntegrityError):
            self.env['clinic.medication'].create({
                'name': 'Test Med Unique 2',
                'generic_name': 'Generic Test 2',
                'code': 'UNIQUE-TEST-001',  # Duplicate!
                'medication_form': 'tablet',
                'strength': '250mg',
            })
            self.env.cr.commit()  # Force constraint check
