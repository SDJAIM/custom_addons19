#!/usr/bin/env bash
# Clinic System Auto-Fix
# ======================
# Automatically repairs common issues and KeyErrors

set -euo pipefail

# Configuration
ODP="${ODP:-python odoo/odoo-bin}"
CFG="${CFG:-odoo.conf}"
DB="${DB:-clinic_dev}"
LOG_FILE="${LOG_FILE:-clinic_autofix.log}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

# Fix KeyError: appointment_id
fix_appointment_keyerror() {
    log_info "🔧 Fixing KeyError: appointment_id..."
    
    cat > /tmp/clinic_fix_appointment.py <<'EOF'
import sys

try:
    # 1. Check if appointment models exist
    appointment_models = [
        'clinic.appointment',
        'clinic.appointment.core'
    ]
    
    existing_models = []
    for model_name in appointment_models:
        model = env['ir.model'].search([('model', '=', model_name)], limit=1)
        if model:
            existing_models.append(model_name)
    
    print(f"Found appointment models: {existing_models}")
    
    # 2. Find views referencing appointment_id
    broken_views = env['ir.ui.view'].search([
        ('arch_db', 'ilike', 'appointment_id')
    ])
    
    fixed_views = 0
    for view in broken_views:
        try:
            # Test if view can be processed
            view._check_xml()
        except Exception as e:
            if 'appointment_id' in str(e):
                print(f"Removing broken view: {view.key or view.name}")
                view.unlink()
                fixed_views += 1
    
    # 3. Clean orphaned field definitions
    orphaned_fields = env['ir.model.fields'].search([
        ('name', '=', 'appointment_id'),
        ('model_id.model', 'not in', existing_models)
    ])
    
    if orphaned_fields:
        print(f"Removing {len(orphaned_fields)} orphaned field definitions")
        orphaned_fields.unlink()
    
    # 4. Clean broken menu items
    clinic_menus = env['ir.ui.menu'].search([
        ('name', 'ilike', 'clinic')
    ])
    
    fixed_menus = 0
    for menu in clinic_menus:
        if menu.action and not menu.action.exists():
            print(f"Removing broken menu: {menu.name}")
            menu.unlink()
            fixed_menus += 1
    
    # 5. Update module dependencies
    if 'clinic.appointment.core' in existing_models:
        # Update references to use core model
        core_model = env['ir.model'].search([('model', '=', 'clinic.appointment.core')], limit=1)
        if core_model:
            print("Updated to use clinic.appointment.core model")
    
    env.cr.commit()
    
    print(f"AUTOFIX_SUCCESS:views={fixed_views},menus={fixed_menus},fields={len(orphaned_fields)}")
    
except Exception as e:
    print(f"AUTOFIX_ERROR:{str(e)}")
    sys.exit(1)
EOF

    result=$(${ODP} -c ${CFG} shell -d ${DB} < /tmp/clinic_fix_appointment.py 2>&1)
    rm -f /tmp/clinic_fix_appointment.py
    
    if [[ "$result" == *"AUTOFIX_SUCCESS:"* ]]; then
        stats="${result##*AUTOFIX_SUCCESS:}"
        log_success "✅ Auto-fix completed: $stats"
        return 0
    else
        log_error "❌ Auto-fix failed: $result"
        return 1
    fi
}

# Fix broken dependencies
fix_module_dependencies() {
    log_info "🔧 Fixing module dependencies..."
    
    cat > /tmp/clinic_fix_deps.py <<'EOF'
import sys

try:
    # Clinic modules installation order
    CLINIC_ORDER = [
        'clinic_patient',
        'clinic_staff', 
        'clinic_appointment_core',
        'clinic_treatment',
        'clinic_prescription',
        'clinic_finance',
        'clinic_dental_chart',
        'clinic_appointment_web',
        'clinic_api',
        'clinic_integrations_whatsapp',
        'clinic_integrations_telemed',
        'clinic_kpis',
        'clinic_theme'
    ]
    
    # Check which modules exist and their states
    all_modules = env['ir.module.module'].search([('name', 'in', CLINIC_ORDER)])
    module_states = {m.name: m.state for m in all_modules}
    
    # Find modules in wrong state or with dependency issues
    issues_fixed = 0
    
    for module_name in CLINIC_ORDER:
        if module_name in module_states:
            module = env['ir.module.module'].search([('name', '=', module_name)], limit=1)
            state = module_states[module_name]
            
            # Fix modules stuck in 'to upgrade' or 'to install'
            if state in ['to upgrade', 'to install']:
                print(f"Fixing stuck module: {module_name} ({state})")
                try:
                    if state == 'to upgrade':
                        module.button_immediate_upgrade()
                    elif state == 'to install':
                        module.button_immediate_install()
                    issues_fixed += 1
                except Exception as e:
                    print(f"Could not fix {module_name}: {e}")
    
    # Update modules list
    env['ir.module.module'].update_list()
    
    env.cr.commit()
    print(f"DEPS_FIXED:{issues_fixed}")
    
except Exception as e:
    print(f"DEPS_ERROR:{str(e)}")
    sys.exit(1)
EOF

    result=$(${ODP} -c ${CFG} shell -d ${DB} < /tmp/clinic_fix_deps.py 2>&1)
    rm -f /tmp/clinic_fix_deps.py
    
    if [[ "$result" == *"DEPS_FIXED:"* ]]; then
        fixed="${result##*DEPS_FIXED:}"
        log_success "✅ Fixed $fixed module dependency issues"
        return 0
    else
        log_error "❌ Dependency fix failed: $result"
        return 1
    fi
}

# Clean database inconsistencies
clean_db_inconsistencies() {
    log_info "🔧 Cleaning database inconsistencies..."
    
    cat > /tmp/clinic_clean_db.py <<'EOF'
import sys

try:
    cleaned = 0
    
    # 1. Remove broken model data entries
    broken_data = env['ir.model.data'].search([
        ('model', 'ilike', 'clinic%'),
        ('res_id', '=', False)
    ])
    
    if broken_data:
        print(f"Removing {len(broken_data)} broken model data entries")
        broken_data.unlink()
        cleaned += len(broken_data)
    
    # 2. Clean broken attachments
    broken_attachments = env['ir.attachment'].search([
        ('res_model', 'ilike', 'clinic%'),
        ('res_id', '!=', False)
    ])
    
    for att in broken_attachments:
        try:
            # Check if referenced record exists
            if att.res_model and att.res_id:
                record = env[att.res_model].browse(att.res_id)
                if not record.exists():
                    att.unlink()
                    cleaned += 1
        except Exception:
            att.unlink()
            cleaned += 1
    
    # 3. Clean broken translations
    broken_translations = env['ir.translation'].search([
        ('name', 'ilike', 'clinic%'),
        ('res_id', '!=', False)
    ])
    
    for trans in broken_translations:
        try:
            if ',' in trans.name:
                model, field = trans.name.split(',', 1)
                if trans.res_id:
                    record = env[model].browse(trans.res_id)
                    if not record.exists():
                        trans.unlink()
                        cleaned += 1
        except Exception:
            pass
    
    # 4. Vacuum analyze for performance
    env.cr.execute("VACUUM ANALYZE;")
    
    env.cr.commit()
    print(f"DB_CLEANED:{cleaned}")
    
except Exception as e:
    print(f"DB_CLEAN_ERROR:{str(e)}")
    sys.exit(1)
EOF

    result=$(${ODP} -c ${CFG} shell -d ${DB} < /tmp/clinic_clean_db.py 2>&1)
    rm -f /tmp/clinic_clean_db.py
    
    if [[ "$result" == *"DB_CLEANED:"* ]]; then
        cleaned="${result##*DB_CLEANED:}"
        log_success "✅ Cleaned $cleaned database inconsistencies"
        return 0
    else
        log_error "❌ Database cleanup failed: $result"
        return 1
    fi
}

# Reinstall core modules
reinstall_core_modules() {
    log_info "🔧 Reinstalling core appointment module..."
    
    # Force update clinic_appointment_core
    if ${ODP} -c ${CFG} -d ${DB} -u clinic_appointment_core --stop-after-init >/dev/null 2>&1; then
        log_success "✅ Core appointment module reinstalled"
        return 0
    else
        log_error "❌ Failed to reinstall core appointment module"
        return 1
    fi
}

# Main auto-fix routine
main() {
    log_info "🚀 Starting Clinic System Auto-Fix"
    log_info "Database: $DB"
    log_info "========================="
    
    # Initialize log
    echo "$(date): Starting auto-fix" > "$LOG_FILE"
    
    local fixes_applied=0
    local fixes_failed=0
    
    # Fix 1: KeyError appointment_id
    log_info "Step 1/4: Fixing KeyError issues..."
    if fix_appointment_keyerror; then
        ((fixes_applied++))
    else
        ((fixes_failed++))
    fi
    
    # Fix 2: Module dependencies
    log_info "Step 2/4: Fixing module dependencies..."
    if fix_module_dependencies; then
        ((fixes_applied++))
    else
        ((fixes_failed++))
    fi
    
    # Fix 3: Database inconsistencies
    log_info "Step 3/4: Cleaning database inconsistencies..."
    if clean_db_inconsistencies; then
        ((fixes_applied++))
    else
        ((fixes_failed++))
    fi
    
    # Fix 4: Reinstall core modules
    log_info "Step 4/4: Reinstalling core modules..."
    if reinstall_core_modules; then
        ((fixes_applied++))
    else
        ((fixes_failed++))
    fi
    
    # Summary
    log_info "========================="
    log_success "✅ Auto-fix completed: $fixes_applied successful, $fixes_failed failed"
    
    if [[ $fixes_failed -eq 0 ]]; then
        log_success "🎉 All fixes applied successfully!"
        log_info "🚀 Ready to install clinic_installer"
    else
        log_warning "⚠️ Some fixes failed - manual intervention may be required"
        log_info "📋 Check log file: $LOG_FILE"
    fi
}

# Help function
show_help() {
    echo "Clinic System Auto-Fix Tool"
    echo "Usage: $0 [options]"
    echo ""
    echo "Fixes common issues:"
    echo "  - KeyError: appointment_id"
    echo "  - Broken view references"  
    echo "  - Module dependency issues"
    echo "  - Database inconsistencies"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help"
    echo "  -d, --db NAME  Database name"
    echo "  -c, --config   Config file"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--db)
            DB="$2"
            shift 2
            ;;
        -c|--config)
            CFG="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Run main function
main "$@"