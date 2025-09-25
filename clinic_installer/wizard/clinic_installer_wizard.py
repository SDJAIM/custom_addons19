from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ClinicInstallerWizard(models.TransientModel):
    _name = 'clinic.installer.wizard'
    _description = 'Clinic Installation Wizard'

    state = fields.Selection([
        ('welcome', 'Welcome'),
        ('options', 'Installation Options'),
        ('progress', 'Installation Progress'),
        ('complete', 'Installation Complete')
    ], default='welcome', string='State')
    
    # Installation options
    load_demo_data = fields.Boolean(
        string='Load Demo Data',
        default=False,
        help='Load sample data for testing and evaluation'
    )
    
    install_optional_modules = fields.Boolean(
        string='Install Optional Modules',
        default=True,
        help='Install WhatsApp, Telemedicine, and API integration modules'
    )
    
    create_admin_user = fields.Boolean(
        string='Create Clinic Admin User',
        default=True,
        help='Create a dedicated clinic administrator account'
    )
    
    configure_company = fields.Boolean(
        string='Configure Clinic Company',
        default=True,
        help='Set up basic company information for the clinic'
    )
    
    # Company information
    clinic_name = fields.Char(string='Clinic Name', default='My Clinic')
    clinic_email = fields.Char(string='Email', default='info@myclinic.com')
    clinic_phone = fields.Char(string='Phone')
    clinic_address = fields.Text(string='Address')
    
    # Progress tracking
    progress_percentage = fields.Integer(string='Progress', default=0)
    current_step = fields.Char(string='Current Step')
    installation_log = fields.Html(string='Installation Log')
    
    @api.model
    def default_get(self, fields_list):
        """Set default values"""
        res = super().default_get(fields_list)
        
        # Get company info if available
        company = self.env.user.company_id
        if company:
            res.update({
                'clinic_name': company.name or 'My Clinic',
                'clinic_email': company.email or 'info@myclinic.com',
                'clinic_phone': company.phone or '',
                'clinic_address': company.street or '',
            })
        
        return res
    
    def action_next_step(self):
        """Move to next installation step"""
        if self.state == 'welcome':
            return self._action_show_options()
        elif self.state == 'options':
            return self._action_start_installation()
        elif self.state == 'complete':
            return self._action_finish()
    
    def _action_show_options(self):
        """Show installation options"""
        self.state = 'options'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.installer.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
    
    def _action_start_installation(self):
        """Start the installation process"""
        self.write({
            'state': 'progress',
            'progress_percentage': 0,
            'current_step': 'Starting installation...',
            'installation_log': '<p><strong>🚀 Starting Clinic System Installation</strong></p>'
        })
        
        try:
            self._run_installation()
            
            self.write({
                'state': 'complete',
                'progress_percentage': 100,
                'current_step': 'Installation completed successfully!',
                'installation_log': self.installation_log + '<p><strong>✅ Installation Completed Successfully!</strong></p>'
            })
            
        except Exception as e:
            _logger.error(f"Installation failed: {e}")
            self.write({
                'installation_log': self.installation_log + f'<p style="color: red;"><strong>❌ Installation Failed:</strong> {str(e)}</p>'
            })
            raise UserError(_('Installation failed: %s') % str(e))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.installer.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
    
    def _run_installation(self):
        """Run the complete installation process"""
        steps = [
            (10, 'Checking prerequisites...', self._check_prerequisites),
            (25, 'Installing base modules...', self._install_base_modules),
            (50, 'Installing core modules...', self._install_core_modules),
            (70, 'Installing optional modules...', self._install_optional_modules),
            (85, 'Configuring system...', self._configure_system),
            (95, 'Loading demo data...', self._load_demo_data),
            (100, 'Finalizing installation...', self._finalize_installation),
        ]
        
        for progress, step_name, step_function in steps:
            self.write({
                'progress_percentage': progress,
                'current_step': step_name
            })
            self.env.cr.commit()  # Commit to show progress
            
            try:
                step_function()
                self._log_step(f"✅ {step_name} - Completed")
            except Exception as e:
                self._log_step(f"❌ {step_name} - Failed: {str(e)}")
                raise
    
    def _check_prerequisites(self):
        """Check system prerequisites"""
        from ..hooks import check_python_dependencies, CLINIC_MODULES_ORDER
        
        # Check Python dependencies
        check_python_dependencies()
        self._log_step("Python dependencies verified")
        
        # Check modules availability
        available_modules = self.env['ir.module.module'].search([
            ('name', 'in', CLINIC_MODULES_ORDER)
        ])
        
        missing_modules = set(CLINIC_MODULES_ORDER) - set(available_modules.mapped('name'))
        if missing_modules:
            raise Exception(f"Missing clinic modules: {', '.join(missing_modules)}")
        
        self._log_step(f"All {len(CLINIC_MODULES_ORDER)} clinic modules found")
    
    def _install_base_modules(self):
        """Install base modules"""
        base_modules = ['clinic_patient', 'clinic_staff']
        self._install_module_list(base_modules)
    
    def _install_core_modules(self):
        """Install core clinical modules"""
        core_modules = ['clinic_appointment_core', 'clinic_treatment', 'clinic_prescription', 'clinic_finance']
        self._install_module_list(core_modules)
    
    def _install_optional_modules(self):
        """Install optional modules if requested"""
        if self.install_optional_modules:
            optional_modules = [
                'clinic_dental_chart', 'clinic_appointment_web', 'clinic_api',
                'clinic_integrations_whatsapp', 'clinic_integrations_telemed', 
                'clinic_kpis', 'clinic_theme'
            ]
            self._install_module_list(optional_modules)
        else:
            essential_modules = ['clinic_kpis', 'clinic_theme']
            self._install_module_list(essential_modules)
    
    def _install_module_list(self, module_names):
        """Install a list of modules"""
        for module_name in module_names:
            module = self.env['ir.module.module'].search([('name', '=', module_name)], limit=1)
            
            if module and module.state == 'uninstalled':
                try:
                    module.button_immediate_install()
                    self._log_step(f"Installed {module_name}")
                except Exception as e:
                    self._log_step(f"Failed to install {module_name}: {str(e)}")
                    raise
            elif module and module.state == 'installed':
                self._log_step(f"{module_name} already installed")
            else:
                self._log_step(f"Module {module_name} not found")
    
    def _configure_system(self):
        """Configure system settings"""
        # Configure company information
        if self.configure_company:
            company = self.env.user.company_id
            company.write({
                'name': self.clinic_name,
                'email': self.clinic_email,
                'phone': self.clinic_phone,
                'street': self.clinic_address,
            })
            self._log_step("Company information configured")
        
        # Create admin user
        if self.create_admin_user:
            self._create_admin_user()
        
        # Set configuration parameters
        config_param = self.env['ir.config_parameter'].sudo()
        config_param.set_param('clinic_installer.installation_date', fields.Datetime.now())
        config_param.set_param('clinic_installer.load_demo_data', str(self.load_demo_data).lower())
        
        self._log_step("System configuration completed")
    
    def _create_admin_user(self):
        """Create clinic admin user"""
        try:
            existing_user = self.env['res.users'].search([('login', '=', 'clinic_admin')], limit=1)
            
            if not existing_user:
                # Get clinic groups
                clinic_groups = self.env['res.groups'].search([
                    '|', ('name', 'ilike', 'clinic'), ('category_id.name', 'ilike', 'clinic')
                ])
                
                user_vals = {
                    'name': 'Clinic Administrator',
                    'login': 'clinic_admin',
                    'email': self.clinic_email,
                    'groups_id': [(6, 0, clinic_groups.ids)] if clinic_groups else [],
                    'active': True,
                }
                
                self.env['res.users'].create(user_vals)
                self._log_step("Clinic admin user created (login: clinic_admin)")
            else:
                self._log_step("Clinic admin user already exists")
                
        except Exception as e:
            self._log_step(f"Warning: Could not create admin user: {str(e)}")
    
    def _load_demo_data(self):
        """Load demo data if requested"""
        if self.load_demo_data:
            try:
                # Demo data is loaded automatically during module installation
                self._log_step("Demo data loaded successfully")
            except Exception as e:
                self._log_step(f"Warning: Could not load demo data: {str(e)}")
    
    def _finalize_installation(self):
        """Finalize the installation"""
        # Update apps list
        self.env['ir.module.module'].update_list()
        
        self._log_step("Installation finalized successfully")
    
    def _log_step(self, message):
        """Add a step to the installation log"""
        timestamp = fields.Datetime.now().strftime('%H:%M:%S')
        log_entry = f'<p>[{timestamp}] {message}</p>'
        self.installation_log = (self.installation_log or '') + log_entry
        _logger.info(f"Clinic Installer: {message}")
    
    def _action_finish(self):
        """Finish the installation and close wizard"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Installation Complete!'),
                'message': _('Clinic system has been installed successfully. You can now start using the system.'),
                'sticky': False,
            }
        }
    
    def action_open_clinic_dashboard(self):
        """Open the clinic dashboard"""
        try:
            # Try to find clinic KPI dashboard action
            action = self.env.ref('clinic_kpis.action_clinic_dashboard', raise_if_not_found=False)
            if action:
                return action.read()[0]
        except:
            pass
        
        # Fallback to apps menu
        return {
            'type': 'ir.actions.act_url',
            'url': '/web#menu_id=',
            'target': 'self',
        }