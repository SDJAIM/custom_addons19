# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError


@tagged('post_install', '-at_install', 'security')
class TestPatientSecurity(TransactionCase):
    """Test Patient Record Rules - P0-001"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test companies
        cls.company_1 = cls.env['res.company'].create({
            'name': 'Test Clinic 1',
        })
        cls.company_2 = cls.env['res.company'].create({
            'name': 'Test Clinic 2',
        })

        # Create branches
        cls.branch_1 = cls.env['clinic.branch'].create({
            'name': 'Branch 1',
            'code': 'BR1',
            'company_id': cls.company_1.id,
        })
        cls.branch_2 = cls.env['clinic.branch'].create({
            'name': 'Branch 2',
            'code': 'BR2',
            'company_id': cls.company_1.id,
        })

        # Create test users
        cls.user_with_staff = cls.env['res.users'].create({
            'name': 'Doctor User',
            'login': 'doctor_user',
            'email': 'doctor@test.com',
            'company_id': cls.company_1.id,
            'company_ids': [(6, 0, [cls.company_1.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('clinic_patient.group_clinic_patient_user').id,
                cls.env.ref('base.group_user').id,
            ])],
        })

        cls.user_without_staff = cls.env['res.users'].create({
            'name': 'User Without Staff',
            'login': 'no_staff_user',
            'email': 'nostaff@test.com',
            'company_id': cls.company_1.id,
            'company_ids': [(6, 0, [cls.company_1.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('clinic_patient.group_clinic_patient_user').id,
                cls.env.ref('base.group_user').id,
            ])],
        })

        cls.manager_user = cls.env['res.users'].create({
            'name': 'Manager User',
            'login': 'manager_user',
            'email': 'manager@test.com',
            'company_id': cls.company_1.id,
            'company_ids': [(6, 0, [cls.company_1.id])],
            'groups_id': [(6, 0, [
                cls.env.ref('clinic_patient.group_clinic_patient_manager').id,
                cls.env.ref('base.group_user').id,
            ])],
        })

        # Create staff record for user_with_staff
        cls.staff = cls.env['clinic.staff'].create({
            'name': 'Dr. Test',
            'user_id': cls.user_with_staff.id,
            'branch_ids': [(6, 0, [cls.branch_1.id])],
            'company_id': cls.company_1.id,
        })

        # Link staff to user
        cls.user_with_staff.write({'staff_id': cls.staff.id})

        # Create test patients
        cls.patient_branch_1 = cls.env['clinic.patient'].sudo().create({
            'name': 'Patient Branch 1',
            'company_id': cls.company_1.id,
            'branch_ids': [(6, 0, [cls.branch_1.id])],
        })

        cls.patient_branch_2 = cls.env['clinic.patient'].sudo().create({
            'name': 'Patient Branch 2',
            'company_id': cls.company_1.id,
            'branch_ids': [(6, 0, [cls.branch_2.id])],
        })

        cls.patient_no_branch = cls.env['clinic.patient'].sudo().create({
            'name': 'Patient No Branch',
            'company_id': cls.company_1.id,
            'branch_ids': [(6, 0, [])],
        })

        cls.patient_company_2 = cls.env['clinic.patient'].sudo().create({
            'name': 'Patient Company 2',
            'company_id': cls.company_2.id,
            'branch_ids': [(6, 0, [])],
        })

    def test_01_user_with_staff_sees_own_branch_patients(self):
        """User WITH staff_id can see patients from their branches"""
        patients = self.env['clinic.patient'].with_user(self.user_with_staff).search([])

        # Should see: patient_branch_1 (own branch) + patient_no_branch (no branch restriction)
        self.assertIn(self.patient_branch_1, patients,
                     "User should see patients from own branch")
        self.assertIn(self.patient_no_branch, patients,
                     "User should see patients with no branch restriction")

    def test_02_user_with_staff_cannot_see_other_branch(self):
        """User WITH staff_id CANNOT see patients from other branches"""
        patients = self.env['clinic.patient'].with_user(self.user_with_staff).search([])

        self.assertNotIn(self.patient_branch_2, patients,
                        "User should NOT see patients from other branches")

    def test_03_user_without_staff_sees_nothing(self):
        """User WITHOUT staff_id sees NOTHING (fail-closed)"""
        patients = self.env['clinic.patient'].with_user(self.user_without_staff).search([])

        self.assertEqual(len(patients), 0,
                        "User without staff_id should see ZERO patients (fail-closed)")

    def test_04_manager_sees_all_patients(self):
        """Manager can see ALL patients"""
        patients = self.env['clinic.patient'].with_user(self.manager_user).search([])

        # Manager should see all patients from same company
        self.assertIn(self.patient_branch_1, patients)
        self.assertIn(self.patient_branch_2, patients)
        self.assertIn(self.patient_no_branch, patients)

    def test_05_multi_company_isolation(self):
        """Users CANNOT see patients from other companies"""
        # user_with_staff is in company_1, should NOT see company_2 patients
        patients = self.env['clinic.patient'].with_user(self.user_with_staff).search([])

        self.assertNotIn(self.patient_company_2, patients,
                        "User should NOT see patients from other companies")

    def test_06_user_without_staff_cannot_write(self):
        """User WITHOUT staff_id CANNOT write to patients"""
        with self.assertRaises(AccessError, msg="User without staff should not be able to write"):
            self.patient_no_branch.with_user(self.user_without_staff).write({'name': 'New Name'})

    def test_07_user_with_staff_can_write_own_branch(self):
        """User WITH staff_id CAN write to patients from own branch"""
        # Should succeed
        self.patient_branch_1.with_user(self.user_with_staff).write({'name': 'Updated Name'})
        self.assertEqual(self.patient_branch_1.name, 'Updated Name')

    def test_08_user_with_staff_cannot_write_other_branch(self):
        """User WITH staff_id CANNOT write to patients from other branches"""
        with self.assertRaises(AccessError, msg="User should not be able to write to other branch"):
            self.patient_branch_2.with_user(self.user_with_staff).write({'name': 'Hack Attempt'})

    def test_09_manager_has_unlink_permission(self):
        """Manager has unlink permission"""
        test_patient = self.env['clinic.patient'].sudo().create({
            'name': 'Test Unlink',
            'company_id': self.company_1.id,
        })

        # Manager should be able to unlink
        test_patient.with_user(self.manager_user).unlink()

    def test_10_user_cannot_unlink(self):
        """Regular user CANNOT unlink patients"""
        with self.assertRaises(AccessError, msg="User should not be able to unlink"):
            self.patient_branch_1.with_user(self.user_with_staff).unlink()

    def test_11_company_ids_context_works(self):
        """Test that user.company_ids.ids pattern works correctly"""
        # This tests the fix for P0-001 (company_ids → user.company_ids.ids)

        # Add company_2 to user_with_staff
        self.user_with_staff.write({
            'company_ids': [(6, 0, [self.company_1.id, self.company_2.id])]
        })

        # User should now be able to access company_2 records
        # (if their staff allows branch access)
        patients = self.env['clinic.patient'].with_user(self.user_with_staff).search([
            ('company_id', 'in', [self.company_1.id, self.company_2.id])
        ])

        # Should work without error (previous bug would cause company_ids undefined)
        self.assertGreater(len(patients), 0, "Should be able to search across user's companies")
