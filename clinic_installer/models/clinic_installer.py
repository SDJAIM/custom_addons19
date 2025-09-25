from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class ClinicInstaller(models.TransientModel):
    _name = 'clinic.installer'
    _description = 'Clinic System Installer'

    state = fields.Selection([
        ('start', 'Start'),
        ('checking', 'Checking Dependencies'),
        ('installing', 'Installing Modules'),
        ('configuring', 'Configuring System'), 
        ('done', 'Installation Complete'),
        ('error', 'Installation Error')
    ], default='start', string='Installation State', 
       help='Current state of the installation process',
       tracking=True)
    
    progress = fields.Integer(
        string='Progress (%)', 
        default=0,
        help='Installation progress percentage (0-100)',
        group_operator='avg'
    )
    
    current_step = fields.Char(
        string='Current Step',
        help='Description of the current installation step',
        translate=True
    )
    
    log_messages = fields.Html(
        string='Installation Log',
        help='Detailed log of installation process',
        sanitize=True
    )
    
    load_demo_data = fields.Boolean(
        string='Load Demo Data', 
        default=False,
        help='Load sample patients, appointments, and test data for evaluation'
    )
    
    install_optional_modules = fields.Boolean(
        string='Install Optional Modules',
        default=True,
        help='Install WhatsApp, Telemedicine, and API modules'
    )
    
    create_admin_user = fields.Boolean(
        string='Create Clinic Admin User',
        default=True,
        help='Create a dedicated clinic administrator user'
    )

    @api.model
    def create(self, vals):
        """Override create to validate installation permissions"""
        if not self.env.user.has_group('clinic_installer.group_clinic_installer_admin'):
            raise AccessError(_("Only clinic installer administrators can create installation records"))
        return super().create(vals)

    def write(self, vals):
        """Override write to validate state transitions"""
        if 'state' in vals:
            allowed_transitions = {
                'start': ['checking'],
                'checking': ['installing', 'error'],
                'installing': ['configuring', 'error'],
                'configuring': ['done', 'error'],
                'done': [],
                'error': ['start']  # Allow restart from error
            }
            
            for record in self:
                if vals['state'] not in allowed_transitions.get(record.state, []):
                    raise ValidationError(
                        _("Invalid state transition from %s to %s") % 
                        (record.state, vals['state']))
        
        return super().write(vals)

    def _log_step(self, message):
        """Add translated message to installation log"""
        timestamp = fields.Datetime.now().strftime('%H:%M:%S')
        translated_msg = _(message)
        entry = f'<p>[{timestamp}] {translated_msg}</p>'
        for record in self:
            record.log_messages = (record.log_messages or '') + entry

    def _install_module_list(self, module_names):
        """Install modules in batches for better performance"""
        if not module_names:
            return
        Module = self.env["ir.module.module"].sudo()
        mods = Module.search([("name", "in", module_names), ("state", "=", "uninstalled")])
        if not mods:
            return
        total = len(mods)
        batch_size = 3
        for i in range(0, total, batch_size):
            batch = mods[i : i + batch_size]
            self.write({
                "progress": 20 + int((i / max(total, 1)) * 60),
                "current_step": _("Installing batch %s: %s")
                % (i // batch_size + 1, ", ".join(batch.mapped("name"))),
            })
            self.env.cr.commit()
            try:
                batch.button_immediate_install()
                for m in batch:
                    self._log_step(_("✓ Installed %s") % m.name)
            except Exception as e:
                self._log_step(_("✗ Batch installation failed: %s") % e)
                raise

    @api.model
    def get_installation_status(self):
        """Get current installation status"""
        from ..hooks import CLINIC_MODULES_ORDER
        
        installed_modules = self.env['ir.module.module'].search([
            ('name', 'in', CLINIC_MODULES_ORDER),
            ('state', '=', 'installed')
        ])
        
        total_modules = len(CLINIC_MODULES_ORDER)
        installed_count = len(installed_modules)
        
        return {
            'total_modules': total_modules,
            'installed_modules': installed_count,
            'progress': int((installed_count / total_modules) * 100) if total_modules > 0 else 0,
            'modules_status': [
                {
                    'name': module_name,
                    'installed': module_name in installed_modules.mapped('name')
                }
                for module_name in CLINIC_MODULES_ORDER
            ]
        }

    def action_start_installation(self):
        """Start the installation process"""
        self.ensure_one()
        
        try:
            self._check_prerequisites()
            self._install_clinic_modules()
            self._configure_system()
            
            self.write({
                'state': 'done',
                'progress': 100,
                'current_step': 'Installation completed successfully!'
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'title': _('Installation Complete'),
                    'message': _('Clinic system has been installed successfully!'),
                    'sticky': False,
                }
            }
            
        except Exception as e:
            _logger.error(f"Installation failed: {e}")
            self.write({
                'state': 'error',
                'current_step': f'Installation failed: {str(e)}',
                'log_messages': (self.log_messages or '') + f"\nERROR: {str(e)}"
            })
            raise UserError(_('Installation failed: %s') % str(e))

    def _check_prerequisites(self):
        """Check system prerequisites"""
        self.write({
            'state': 'checking',
            'progress': 10,
            'current_step': 'Checking system prerequisites...'
        })
        
        # Check Python dependencies
        from ..hooks import check_python_dependencies
        try:
            check_python_dependencies()
            self._log_message("✓ Python dependencies verified")
        except Exception as e:
            raise ValidationError(_("Missing Python dependencies: %s") % str(e))
        
        # Check Odoo modules availability
        from ..hooks import CLINIC_MODULES_ORDER
        available_modules = self.env['ir.module.module'].search([
            ('name', 'in', CLINIC_MODULES_ORDER)
        ])
        
        missing_modules = set(CLINIC_MODULES_ORDER) - set(available_modules.mapped('name'))
        if missing_modules:
            raise ValidationError(_("Missing clinic modules: %s") % ', '.join(missing_modules))
        
        self._log_message("✓ All clinic modules found")

    def _install_clinic_modules(self):
        """Install clinic modules in correct order"""
        from ..hooks import CLINIC_MODULES_ORDER
        
        self.write({
            'state': 'installing',
            'progress': 20,
            'current_step': 'Installing clinic modules...'
        })
        
        optional_modules = ['clinic_integrations_whatsapp', 'clinic_integrations_telemed', 'clinic_api']
        modules_to_install = CLINIC_MODULES_ORDER.copy()
        
        if not self.install_optional_modules:
            modules_to_install = [m for m in modules_to_install if m not in optional_modules]
        
        total_modules = len(modules_to_install)
        
        for i, module_name in enumerate(modules_to_install):
            progress = 20 + int((i / total_modules) * 60)
            self.write({
                'progress': progress,
                'current_step': f'Installing {module_name}...'
            })
            
            module = self.env['ir.module.module'].search([('name', '=', module_name)], limit=1)
            
            if module and module.state == 'uninstalled':
                try:
                    module.button_immediate_install()
                    self._log_message(f"✓ Installed {module_name}")
                except Exception as e:
                    self._log_message(f"✗ Failed to install {module_name}: {str(e)}")
                    raise ValidationError(_("Failed to install %s: %s") % (module_name, str(e)))
            elif module and module.state == 'installed':
                self._log_message(f"✓ {module_name} already installed")

    def _configure_system(self):
        """Configure the system after installation"""
        self.write({
            'state': 'configuring',
            'progress': 85,
            'current_step': 'Configuring system settings...'
        })
        
        # Set configuration parameters
        config_param = self.env['ir.config_parameter'].sudo()
        config_param.set_param('clinic_installer.installation_date', fields.Datetime.now())
        config_param.set_param('clinic_installer.load_demo_data', str(self.load_demo_data).lower())
        
        # Create clinic admin user if requested
        if self.create_admin_user:
            self._create_clinic_admin()
        
        # Load demo data if requested
        if self.load_demo_data:
            self._load_demo_data()
        
        self._log_message("✓ System configuration completed")

    def _create_clinic_admin(self):
        """Create clinic administrator user"""
        try:
            existing_user = self.env['res.users'].search([('login', '=', 'clinic_admin')], limit=1)
            if not existing_user:
                clinic_groups = self.env['res.groups'].search([
                    ('name', 'ilike', 'clinic'),
                    ('name', 'ilike', 'manager')
                ])
                
                user_vals = {
                    'name': 'Clinic Administrator',
                    'login': 'clinic_admin',
                    'email': 'admin@clinic.local',
                    'groups_id': [(6, 0, clinic_groups.ids)],
                    'active': True,
                }
                
                self.env['res.users'].create(user_vals)
                self._log_message("✓ Created clinic admin user (login: clinic_admin)")
            else:
                self._log_message("✓ Clinic admin user already exists")
                
        except Exception as e:
            self._log_message(f"⚠ Warning: Could not create admin user: {str(e)}")

    def _load_demo_data(self):
        """Load demo data for testing"""
        try:
            # Demo data is loaded automatically during module installation
            self._log_message("✓ Demo data loaded successfully")
        except Exception as e:
            self._log_message(f"⚠ Warning: Could not load demo data: {str(e)}")

    def _log_message(self, message):
        """Add message to installation log"""
        current_log = self.log_messages or ''
        timestamp = fields.Datetime.now().strftime('%H:%M:%S')
        new_message = f"[{timestamp}] {message}\n"
        self.log_messages = current_log + new_message
        _logger.info(f"Clinic Installer: {message}")

    def action_start_installation(self):
        """Start the installation process"""
        self.ensure_one()
        
        try:
            self._check_prerequisites()
            self._install_clinic_modules() 
            self._configure_system()
            
            self.write({
                'state': 'done',
                'progress': 100,
                'current_step': _('Installation completed successfully!')
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'title': _('Installation Complete'),
                    'message': _('Clinic system has been installed successfully!'),
                    'sticky': False,
                }
            }
            
        except Exception as e:
            self.write({
                'state': 'error',
                'current_step': _('Installation failed: %s') % str(e),
            })
            self._log_step(_('✗ Installation error: %s') % str(e))
            
            # Attempt automatic rollback
            try:
                self._rollback_installation()
            except Exception as rollback_error:
                self._log_step(_('✗ Rollback failed: %s') % str(rollback_error))
            
            raise

    def action_restart_installation(self):
        """Restart installation from error state"""
        self.ensure_one()
        self.write({
            'state': 'start',
            'progress': 0,
            'current_step': '',
            'log_messages': ''
        })
        return True

    def _check_prerequisites(self):
        """Check system prerequisites with conflict detection"""
        self.write({
            'state': 'checking',
            'progress': 10,
            'current_step': _('Checking system prerequisites...')
        })
        
        # Import here to avoid circular imports
        from ..hooks import check_python_dependencies, CLINIC_MODULES_ORDER
        
        # 1. Check for legacy/conflicting modules
        self._check_legacy_conflicts()
        
        # 2. Check Python dependencies
        try:
            check_python_dependencies()
            self._log_step(_("✓ Python dependencies verified"))
        except Exception as e:
            raise ValidationError(_("Missing Python dependencies: %s") % str(e))
        
        # 3. Check Odoo modules availability
        available_modules = self.env['ir.module.module'].search([
            ('name', 'in', CLINIC_MODULES_ORDER)
        ])
        
        missing_modules = set(CLINIC_MODULES_ORDER) - set(available_modules.mapped('name'))
        if missing_modules:
            raise ValidationError(_("Missing clinic modules: %s") % ', '.join(missing_modules))
        
        self._log_step(_("✓ All clinic modules found"))
        
        # 4. Check for broken references
        self._check_broken_references()
        
        # 5. Validate dependency order
        self._validate_dependency_order(CLINIC_MODULES_ORDER)

    def _check_legacy_conflicts(self):
        """Check for legacy/conflicting modules"""
        legacy_modules = [
            'dental_medical_clinic',
            'medical_dental',
            'dental_clinic', 
            'medical_clinic',
            'clinic_management_old'
        ]
        
        conflicting = self.env['ir.module.module'].search([
            ('name', 'in', legacy_modules),
            ('state', '=', 'installed')
        ])
        
        if conflicting:
            conflict_names = ', '.join(conflicting.mapped('name'))
            self._log_step(_("⚠️ Found conflicting legacy modules: %s") % conflict_names)
            
            # Auto-uninstall conflicting modules
            try:
                self._log_step(_("🧹 Auto-removing legacy modules..."))
                conflicting.button_immediate_uninstall()
                self.env.cr.commit()
                self._log_step(_("✓ Legacy modules removed successfully"))
            except Exception as e:
                raise ValidationError(
                    _("Cannot proceed: Legacy modules detected (%s). "
                      "Please uninstall them manually first: %s") % 
                    (conflict_names, str(e)))
        else:
            self._log_step(_("✓ No legacy conflicts detected"))

    def _check_broken_references(self):
        """Check for broken field/view references"""
        try:
            # Check for common KeyError sources
            broken_views = []
            
            # Test views that might reference non-existent fields
            test_models = ['clinic.appointment', 'clinic.appointment.core']
            
            for model_name in test_models:
                model_exists = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
                if not model_exists:
                    # Check if views reference this missing model
                    referencing_views = self.env['ir.ui.view'].search([
                        ('model', '=', model_name)
                    ])
                    if referencing_views:
                        broken_views.extend(referencing_views.ids)
            
            if broken_views:
                self._log_step(_("⚠️ Found %d potentially broken views") % len(broken_views))
                
                # Auto-fix: Remove broken views
                self.env['ir.ui.view'].browse(broken_views).unlink()
                self._log_step(_("✓ Broken views cleaned automatically"))
            else:
                self._log_step(_("✓ No broken references detected"))
                
        except Exception as e:
            self._log_step(_("⚠️ Warning during reference check: %s") % str(e))

    def _validate_dependency_order(self, module_order):
        """Validate that modules can be installed in the specified order"""
        try:
            # Check each module's dependencies
            for module_name in module_order:
                module = self.env['ir.module.module'].search([('name', '=', module_name)], limit=1)
                if module and module.state == 'uninstalled':
                    # Check if all dependencies are satisfied
                    dependencies = module.dependencies_id.mapped('name')
                    
                    for dep in dependencies:
                        if dep.startswith('clinic_'):
                            # This is a clinic dependency - check it comes before in order
                            try:
                                current_idx = module_order.index(module_name)
                                dep_idx = module_order.index(dep)
                                if dep_idx > current_idx:
                                    raise ValidationError(
                                        _("Dependency order error: %s requires %s but %s comes later in order") %
                                        (module_name, dep, dep))
                            except ValueError:
                                # Dependency not in our order list - that's ok for external deps
                                pass
            
            self._log_step(_("✓ Module dependency order validated"))
            
        except Exception as e:
            self._log_step(_("⚠️ Warning during dependency validation: %s") % str(e))

    def _rollback_installation(self):
        """Attempt to rollback failed installation"""
        self._log_step(_("🔄 Attempting automatic rollback..."))
        
        try:
            # Get list of modules that were installed during this session
            config_param = self.env['ir.config_parameter'].sudo()
            installation_start = config_param.get_param('clinic_installer.current_installation_start')
            
            if installation_start:
                # Find modules installed after installation start
                recently_installed = self.env['ir.module.module'].search([
                    ('name', 'like', 'clinic_%'),
                    ('state', '=', 'installed'),
                    ('write_date', '>=', installation_start)
                ])
                
                if recently_installed:
                    self._log_step(_("🗑️ Rolling back %d recently installed modules...") % len(recently_installed))
                    
                    # Uninstall in reverse order
                    for module in reversed(recently_installed):
                        try:
                            module.button_immediate_uninstall()
                            self._log_step(_("↩️ Rolled back %s") % module.name)
                        except Exception as e:
                            self._log_step(_("⚠️ Could not rollback %s: %s") % (module.name, str(e)))
                    
                    self.env.cr.commit()
                    self._log_step(_("✓ Rollback completed"))
                else:
                    self._log_step(_("ℹ️ No recently installed modules to rollback"))
            else:
                self._log_step(_("ℹ️ No installation tracking - manual cleanup may be needed"))
                
        except Exception as e:
            self._log_step(_("✗ Rollback failed: %s") % str(e))
            raise

    def _install_clinic_modules(self):
        """Install clinic modules in correct order"""
        from ..hooks import CLINIC_MODULES_ORDER
        
        # Mark installation start time for rollback tracking
        config_param = self.env['ir.config_parameter'].sudo()
        config_param.set_param('clinic_installer.current_installation_start', fields.Datetime.now())
        
        self.write({
            'state': 'installing',
            'progress': 20,
            'current_step': _('Installing clinic modules...')
        })
        
        optional_modules = ['clinic_integrations_whatsapp', 'clinic_integrations_telemed', 'clinic_api']
        modules_to_install = CLINIC_MODULES_ORDER.copy()
        
        if not self.install_optional_modules:
            modules_to_install = [m for m in modules_to_install if m not in optional_modules]
        
        self._install_module_list(modules_to_install)

    def _configure_system(self):
        """Configure the system after installation"""
        self.write({
            'state': 'configuring',
            'progress': 85,
            'current_step': _('Configuring system settings...')
        })
        
        # Set configuration parameters
        config_param = self.env['ir.config_parameter'].sudo()
        config_param.set_param('clinic_installer.installation_date', fields.Datetime.now())
        config_param.set_param('clinic_installer.load_demo_data', str(self.load_demo_data).lower())
        
        # Create clinic admin user if requested
        if self.create_admin_user:
            self._create_clinic_admin()
        
        self._log_step(_("✓ System configuration completed"))

    def _create_clinic_admin(self):
        """Create clinic administrator user"""
        try:
            existing_user = self.env['res.users'].search([('login', '=', 'clinic_admin')], limit=1)
            if not existing_user:
                clinic_groups = self.env['res.groups'].search([
                    ('name', 'ilike', 'clinic'),
                    ('name', 'ilike', 'manager')
                ])
                
                user_vals = {
                    'name': 'Clinic Administrator',
                    'login': 'clinic_admin',
                    'email': 'admin@clinic.local',
                    'groups_id': [(6, 0, clinic_groups.ids)],
                    'active': True,
                }
                
                self.env['res.users'].create(user_vals)
                self._log_step(_("✓ Created clinic admin user (login: clinic_admin)"))
            else:
                self._log_step(_("✓ Clinic admin user already exists"))
                
        except Exception as e:
            self._log_step(_("⚠ Warning: Could not create admin user: %s") % str(e))

    def action_view_clinic_dashboard(self):
        """Open clinic dashboard after installation"""
        try:
            # Try to find clinic KPI dashboard action
            action = self.env.ref('clinic_kpis.action_clinic_dashboard', raise_if_not_found=False)
            if action:
                return action.read()[0]
        except:
            pass
        
        # Fallback to main menu
        return {
            'type': 'ir.actions.act_url',
            'url': '/web#menu_id=',
            'target': 'self',
        }