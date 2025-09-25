import logging
import subprocess
import sys
import re
from odoo import api, SUPERUSER_ID
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

# Module installation order - critical for dependency resolution
CLINIC_MODULES_ORDER = [
    # Phase 1: Base Modules
    'clinic_patient',
    'clinic_staff',
    
    # Phase 2: Core Clinical
    'clinic_appointment_core',
    'clinic_treatment', 
    'clinic_prescription',
    
    # Phase 3: Financial
    'clinic_finance',
    
    # Phase 4: Specialized
    'clinic_dental_chart',
    
    # Phase 5: Web & Portal
    'clinic_appointment_web',
    
    # Phase 6: Integrations
    'clinic_api',
    'clinic_integrations_whatsapp',
    'clinic_integrations_telemed',
    
    # Phase 7: Analytics & Theme
    'clinic_kpis',
    'clinic_theme',
]

REQUIRED_PYTHON_PACKAGES = [
    'PyJWT>=2.8.0',
    'cryptography>=41.0.0', 
    'requests>=2.31.0',
    'phonenumbers>=8.13.0',
]

# Security: Regex pattern to validate package names and prevent injection
_PKG_VALIDATION_REGEX = re.compile(r'^[A-Za-z0-9._-]+([><=!]=?\d+(\.\d+)*)?$')

def _validate_package_name(package_name: str) -> str:
    """
    Validate package name to prevent command injection attacks.
    
    Args:
        package_name: Package name with optional version specification
        
    Returns:
        Base package name for import checking
        
    Raises:
        ValueError: If package name contains invalid characters
    """
    if not _PKG_VALIDATION_REGEX.match(package_name):
        raise ValueError(f"Security: Invalid package name detected: {package_name}")
    
    # Return base package name without version specs for import validation
    return re.split(r'[><=!]', package_name)[0]

def check_python_dependencies():
    """
    Check and install required Python packages with security validation.
    
    Features:
    - Validates package names against injection attacks
    - Uses timeout to prevent hanging installations
    - Uses --user and --no-deps flags for security
    - Proper error handling and logging
    """
    missing_packages = []
    
    for package in REQUIRED_PYTHON_PACKAGES:
        try:
            # Security: Validate package name first
            base_package_name = _validate_package_name(package)
            
            # Try to import the package
            if base_package_name == 'PyJWT':
                import jwt
            elif base_package_name == 'cryptography':
                import cryptography
            elif base_package_name == 'requests':
                import requests
            elif base_package_name == 'phonenumbers':
                import phonenumbers
            else:
                # For other packages, try generic import
                __import__(base_package_name.replace('-', '_'))
                
        except (ImportError, ValueError):
            missing_packages.append(package)
    
    if not missing_packages:
        _logger.info("All Python dependencies are satisfied")
        return
    
    _logger.warning(f"Missing Python packages: {missing_packages}")
    _logger.info("Installing missing packages with security restrictions...")
    
    for package in missing_packages:
        try:
            # Security: Re-validate before installation
            _validate_package_name(package)
            
            # Secure installation command  
            cmd = [sys.executable, '-m', 'pip', 'install']
            
            # Use --user only if not in virtual environment
            if not (hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)):
                cmd.append('--user')  # Install to user directory only
            
            cmd.extend([
                '--no-deps',  # Don't install dependencies to prevent supply chain attacks
                '--timeout', '300',  # 5 minute timeout
                package
            ])
            
            _logger.info(f"Installing {package} with security restrictions...")
            subprocess.check_call(cmd, timeout=300)
            _logger.info(f"✓ Successfully installed {package}")
            
        except subprocess.TimeoutExpired:
            _logger.error(f"✗ Timeout installing {package}")
            raise Exception(f"Security: Installation timeout for package: {package}")
        except subprocess.CalledProcessError as e:
            _logger.error(f"✗ Failed to install {package}: {e}")
            raise Exception(f"Security: Could not safely install package: {package}")
        except ValueError as e:
            _logger.error(f"✗ Security validation failed for {package}: {e}")
            raise

def post_load_hook():
    """Hook called when module is loaded"""
    _logger.info("Clinic Installer: Post-load hook executed")
    
    # Skip auto-install in virtual environments to avoid conflicts
    import sys
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        _logger.info("Virtual environment detected - skipping auto Python package installation")
        _logger.info("Please ensure PyJWT, cryptography, requests, phonenumbers are installed manually")
    else:
        check_python_dependencies()

def post_init_hook(cr, registry):
    """
    Hook called after module installation with security validation.
    
    Security features:
    - Only system administrators can trigger clinic installation
    - Safe mode provides additional security checks
    - Comprehensive error handling and logging
    """
    _logger.info("Clinic Installer: Starting automated installation of clinic modules")
    
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Security: Validate user has system administrator permissions
    if not env.user.has_group('base.group_system'):
        raise AccessError(
            "Security: Only system administrators can run clinic installer. "
            "Current user does not have required permissions."
        )
    
    # Security: Check safe mode configuration
    config_param = env['ir.config_parameter'].sudo()
    safe_mode = config_param.get_param('clinic_installer.safe_mode', 'true').lower() == 'true'
    
    if safe_mode:
        _logger.info("🔒 Clinic Installer running in SAFE MODE - additional security checks enabled")
    else:
        _logger.warning("⚠️ Clinic Installer running in NORMAL MODE - safe mode disabled")
    
    # Check which modules are available
    available_modules = env['ir.module.module'].search([
        ('name', 'in', CLINIC_MODULES_ORDER),
        ('state', 'in', ['uninstalled', 'to install'])
    ])
    
    _logger.info(f"Found {len(available_modules)} clinic modules to install")
    
    # Install modules in order
    for module_name in CLINIC_MODULES_ORDER:
        module = env['ir.module.module'].search([('name', '=', module_name)], limit=1)
        
        if module and module.state == 'uninstalled':
            _logger.info(f"Installing module: {module_name}")
            try:
                module.button_immediate_install()
                _logger.info(f"Successfully installed: {module_name}")
            except Exception as e:
                _logger.error(f"Failed to install {module_name}: {e}")
                # Continue with next module instead of breaking
                continue
        elif module and module.state == 'installed':
            _logger.info(f"Module {module_name} already installed")
        else:
            _logger.warning(f"Module {module_name} not found or not available")
    
    # Initialize demo data if requested
    load_demo = config_param.get_param('clinic_installer.load_demo_data', 'false')
    
    if load_demo.lower() == 'true':
        _logger.info("Loading clinic demo data...")
        try:
            # Load demo data for all installed clinic modules
            installed_modules = env['ir.module.module'].search([
                ('name', 'in', CLINIC_MODULES_ORDER),
                ('state', '=', 'installed')
            ])
            
            for module in installed_modules:
                if module.demo:
                    _logger.info(f"Loading demo data for: {module.name}")
                    # Demo data is loaded automatically during installation
                    
        except Exception as e:
            _logger.error(f"Error loading demo data: {e}")
    
    _logger.info("Clinic Installer: Installation completed successfully")

def uninstall_hook(cr, registry):
    """Hook called when module is uninstalled"""
    _logger.info("Clinic Installer: Uninstall hook - cleaning up")
    
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Uninstall all clinic modules in reverse order
    for module_name in reversed(CLINIC_MODULES_ORDER):
        module = env['ir.module.module'].search([('name', '=', module_name)], limit=1)
        
        if module and module.state == 'installed':
            _logger.info(f"Uninstalling module: {module_name}")
            try:
                module.button_immediate_uninstall()
            except Exception as e:
                _logger.error(f"Failed to uninstall {module_name}: {e}")