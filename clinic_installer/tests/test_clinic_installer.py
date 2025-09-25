# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError
from unittest.mock import patch, MagicMock


@tagged("post_install", "-at_install")
class TestClinicInstaller(TransactionCase):
    """Test suite for clinic installer functionality"""

    def setUp(self):
        super().setUp()
        self.Installer = self.env["clinic.installer"]
        self.admin_user = self.env.ref('base.user_admin')

    def test_create_requires_admin_access(self):
        """Test that only clinic installer admins can create installation records"""
        # Create demo user without admin rights
        demo_user = self.env["res.users"].create({
            "name": "Demo User",
            "login": "demo_test_user",
            "email": "demo@example.com",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])]
        })
        
        # Should raise AccessError for non-admin user
        with self.assertRaises(AccessError):
            self.Installer.sudo(demo_user).create({
                'load_demo_data': True
            })

    def test_admin_can_create_installer_record(self):
        """Test that admin users can create installation records"""
        installer = self.Installer.create({
            'load_demo_data': False,
            'install_optional_modules': True
        })
        
        self.assertEqual(installer.state, 'start')
        self.assertEqual(installer.progress, 0)
        self.assertFalse(installer.load_demo_data)
        self.assertTrue(installer.install_optional_modules)

    def test_state_transition_validation(self):
        """Test that state transitions are properly validated"""
        installer = self.Installer.create({})
        
        # Valid transition: start -> checking
        installer.write({'state': 'checking'})
        self.assertEqual(installer.state, 'checking')
        
        # Valid transition: checking -> installing
        installer.write({'state': 'installing'})
        self.assertEqual(installer.state, 'installing')
        
        # Invalid transition: installing -> done (should go through configuring)
        with self.assertRaises(ValidationError):
            installer.write({'state': 'done'})

    def test_error_state_can_restart(self):
        """Test that error state can transition back to start"""
        installer = self.Installer.create({'state': 'error'})
        
        # Should be able to restart from error
        installer.write({'state': 'start'})
        self.assertEqual(installer.state, 'start')

    def test_progress_field_constraints(self):
        """Test progress field accepts valid values"""
        installer = self.Installer.create({})
        
        # Valid progress values
        installer.write({'progress': 0})
        installer.write({'progress': 50})
        installer.write({'progress': 100})
        
        # Progress should be within expected range
        self.assertGreaterEqual(installer.progress, 0)
        self.assertLessEqual(installer.progress, 100)

    def test_log_messages_html_sanitization(self):
        """Test that log messages are properly sanitized"""
        installer = self.Installer.create({})
        
        # Test with potentially malicious HTML
        malicious_html = "<script>alert('xss')</script><p>Safe content</p>"
        installer.write({'log_messages': malicious_html})
        
        # Should sanitize the script tag but keep safe HTML
        self.assertNotIn('<script>', installer.log_messages)
        self.assertIn('<p>Safe content</p>', installer.log_messages)

    def test_log_step_method(self):
        """Test the _log_step method functionality"""
        installer = self.Installer.create({})
        
        test_message = "Test installation step"
        installer._log_step(test_message)
        
        # Should contain timestamp and message
        self.assertIn(test_message, installer.log_messages)
        self.assertIn('<p>', installer.log_messages)  # HTML formatting

    @patch('odoo.addons.clinic_installer.models.clinic_installer.fields.Datetime.now')
    def test_log_step_with_timestamp(self, mock_datetime):
        """Test that log steps include proper timestamps"""
        # Mock datetime to control timestamp
        mock_datetime.return_value.strftime.return_value = "12:34:56"
        
        installer = self.Installer.create({})
        installer._log_step("Test message")
        
        self.assertIn("[12:34:56]", installer.log_messages)
        self.assertIn("Test message", installer.log_messages)

    def test_multiple_log_steps_accumulate(self):
        """Test that multiple log steps accumulate properly"""
        installer = self.Installer.create({})
        
        installer._log_step("First step")
        installer._log_step("Second step")
        installer._log_step("Third step")
        
        # All messages should be present
        self.assertIn("First step", installer.log_messages)
        self.assertIn("Second step", installer.log_messages)
        self.assertIn("Third step", installer.log_messages)
        
        # Should have 3 paragraph tags
        self.assertEqual(installer.log_messages.count('<p>'), 3)

    def test_install_module_list_empty_input(self):
        """Test _install_module_list handles empty input gracefully"""
        installer = self.Installer.create({})
        
        # Should not raise exception with empty list
        result = installer._install_module_list([])
        self.assertIsNone(result)

    @patch('odoo.addons.clinic_installer.models.clinic_installer.ClinicInstaller._log_step')
    def test_install_module_list_with_modules(self, mock_log_step):
        """Test _install_module_list processes modules correctly"""
        installer = self.Installer.create({})
        
        # Mock module search to return empty (no modules to install)
        with patch.object(self.env['ir.module.module'], 'search') as mock_search:
            mock_search.return_value = self.env['ir.module.module']
            
            installer._install_module_list(['test_module'])
            
            # Should have searched for modules
            mock_search.assert_called_once()

    def test_current_step_translation(self):
        """Test that current_step field supports translation"""
        installer = self.Installer.create({})
        
        # Set a step message
        installer.write({'current_step': 'Installing modules...'})
        
        # Should accept translated strings
        self.assertEqual(installer.current_step, 'Installing modules...')

    def test_default_values(self):
        """Test that model has proper default values"""
        installer = self.Installer.create({})
        
        # Check defaults
        self.assertEqual(installer.state, 'start')
        self.assertEqual(installer.progress, 0)
        self.assertFalse(installer.log_messages)
        self.assertFalse(installer.current_step)

    def tearDown(self):
        """Clean up after each test"""
        super().tearDown()
        
        # Clean up any test users created
        demo_users = self.env['res.users'].search([
            ('login', 'like', 'demo_test_%')
        ])
        if demo_users:
            demo_users.unlink()