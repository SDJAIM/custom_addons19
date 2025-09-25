#!/usr/bin/env bash
# Clinic System Preflight Checker
# ==============================
# Detects and cleans conflicts before installation

set -euo pipefail

# Configuration
ODP="${ODP:-python odoo/odoo-bin}"
CFG="${CFG:-odoo.conf}"
DB="${DB:-clinic_dev}"
LOG_FILE="${LOG_FILE:-clinic_preflight.log}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

# Check if Odoo is accessible
check_odoo_access() {
    log_info "🔍 Checking Odoo accessibility..."
    
    if ! ${ODP} -c ${CFG} -d ${DB} --help >/dev/null 2>&1; then
        log_error "❌ Cannot access Odoo binary at: ${ODP}"
        exit 1
    fi
    
    # Test database connection
    if ! ${ODP} -c ${CFG} -d ${DB} -i base --stop-after-init >/dev/null 2>&1; then
        log_error "❌ Cannot connect to database: ${DB}"
        log_info "💡 Try creating the database first: createdb -U postgres ${DB}"
        exit 1
    fi
    
    log_success "✅ Odoo access validated"
}

# Detect legacy/conflicting modules
detect_legacy_modules() {
    log_info "🔍 Scanning for legacy/conflicting modules..."
    
    # Create temporary Python script
    cat > /tmp/clinic_legacy_check.py <<'EOF'
import sys

# Legacy modules that conflict with new clinic system
LEGACY_MODULES = [
    'dental_medical_clinic',
    'medical_dental', 
    'dental_clinic',
    'medical_clinic',
    'clinic_management_old',
    'dental_management'
]

try:
    # Check installed legacy modules
    legacy_installed = env['ir.module.module'].search([
        ('name', 'in', LEGACY_MODULES),
        ('state', '=', 'installed')
    ])
    
    if legacy_installed:
        print("LEGACY_FOUND:" + ",".join(legacy_installed.mapped('name')))
        sys.exit(1)
    else:
        print("LEGACY_CLEAN")
        sys.exit(0)
        
except Exception as e:
    print(f"ERROR:{str(e)}")
    sys.exit(2)
EOF

    # Execute check
    result=$(${ODP} -c ${CFG} shell -d ${DB} < /tmp/clinic_legacy_check.py 2>/dev/null || echo "SCRIPT_ERROR")
    rm -f /tmp/clinic_legacy_check.py
    
    case "$result" in
        "LEGACY_CLEAN")
            log_success "✅ No legacy modules detected"
            ;;
        "LEGACY_FOUND:"*)
            legacy_modules="${result#LEGACY_FOUND:}"
            log_warning "⚠️ Found legacy modules: $legacy_modules"
            return 1
            ;;
        *)
            log_error "❌ Error checking legacy modules: $result"
            return 2
            ;;
    esac
    
    return 0
}

# Clean legacy modules
clean_legacy_modules() {
    log_info "🧹 Cleaning legacy modules..."
    
    cat > /tmp/clinic_legacy_clean.py <<'EOF'
LEGACY_MODULES = [
    'dental_medical_clinic',
    'medical_dental', 
    'dental_clinic',
    'medical_clinic',
    'clinic_management_old',
    'dental_management'
]

try:
    legacy = env['ir.module.module'].search([
        ('name', 'in', LEGACY_MODULES),
        ('state', '=', 'installed')
    ])
    
    if legacy:
        print(f"Uninstalling {len(legacy)} legacy modules...")
        for module in legacy:
            print(f"  - {module.name}")
            try:
                module.button_immediate_uninstall()
            except Exception as e:
                print(f"    Warning: {str(e)}")
        
        env.cr.commit()
        print("LEGACY_CLEANED")
    else:
        print("NO_LEGACY_TO_CLEAN")
        
except Exception as e:
    print(f"CLEAN_ERROR:{str(e)}")
EOF

    result=$(${ODP} -c ${CFG} shell -d ${DB} < /tmp/clinic_legacy_clean.py 2>&1)
    rm -f /tmp/clinic_legacy_clean.py
    
    if [[ "$result" == *"LEGACY_CLEANED"* ]]; then
        log_success "✅ Legacy modules cleaned successfully"
    elif [[ "$result" == *"NO_LEGACY_TO_CLEAN"* ]]; then
        log_info "ℹ️ No legacy modules to clean"
    else
        log_error "❌ Error cleaning legacy modules: $result"
        return 1
    fi
}

# Check for broken field references (KeyError diagnostics)
check_broken_references() {
    log_info "🔍 Checking for broken field references..."
    
    cat > /tmp/clinic_broken_check.py <<'EOF'
import sys

try:
    # Check for common broken references
    broken_refs = []
    
    # Check for appointment_id field issues
    appointment_models = ['clinic.appointment', 'clinic.appointment.core']
    has_appointment_model = False
    
    for model_name in appointment_models:
        model = env['ir.model'].search([('model', '=', model_name)], limit=1)
        if model:
            has_appointment_model = True
            break
    
    if not has_appointment_model:
        broken_refs.append("Missing appointment model")
    
    # Check for views referencing non-existent fields
    suspect_views = env['ir.ui.view'].search([
        ('arch_db', 'ilike', 'appointment_id')
    ])
    
    if suspect_views and not has_appointment_model:
        broken_refs.append(f"Views reference appointment_id but no appointment model ({len(suspect_views)} views)")
    
    # Check for orphaned menu items
    clinic_menus = env['ir.ui.menu'].search([
        ('name', 'ilike', 'clinic'),
        ('action', '!=', False)
    ])
    
    orphaned_menus = 0
    for menu in clinic_menus:
        if menu.action and not menu.action.exists():
            orphaned_menus += 1
    
    if orphaned_menus > 0:
        broken_refs.append(f"Orphaned menu items: {orphaned_menus}")
    
    if broken_refs:
        print("BROKEN_REFS_FOUND:" + "|".join(broken_refs))
        sys.exit(1)
    else:
        print("REFERENCES_OK")
        sys.exit(0)
        
except Exception as e:
    print(f"CHECK_ERROR:{str(e)}")
    sys.exit(2)
EOF

    result=$(${ODP} -c ${CFG} shell -d ${DB} < /tmp/clinic_broken_check.py 2>/dev/null || echo "SCRIPT_ERROR")
    rm -f /tmp/clinic_broken_check.py
    
    case "$result" in
        "REFERENCES_OK")
            log_success "✅ No broken references detected"
            ;;
        "BROKEN_REFS_FOUND:"*)
            broken_refs="${result#BROKEN_REFS_FOUND:}"
            log_warning "⚠️ Broken references found: ${broken_refs//|/, }"
            return 1
            ;;
        *)
            log_error "❌ Error checking references: $result"
            return 2
            ;;
    esac
    
    return 0
}

# Update apps list
update_apps_list() {
    log_info "🔄 Updating apps list..."
    
    if ${ODP} -c ${CFG} -d ${DB} -u base --stop-after-init >/dev/null 2>&1; then
        log_success "✅ Apps list updated"
    else
        log_error "❌ Failed to update apps list"
        return 1
    fi
}

# Main preflight check
main() {
    log_info "🚀 Starting Clinic System Preflight Check"
    log_info "Database: $DB"
    log_info "Config: $CFG"
    log_info "=========================="
    
    # Initialize log file
    echo "$(date): Starting preflight check" > "$LOG_FILE"
    
    # Step 1: Check Odoo access
    if ! check_odoo_access; then
        log_error "❌ Preflight FAILED: Odoo access check"
        exit 1
    fi
    
    # Step 2: Detect legacy modules
    if ! detect_legacy_modules; then
        case $? in
            1)
                log_warning "⚠️ Legacy modules detected - cleaning required"
                if ! clean_legacy_modules; then
                    log_error "❌ Preflight FAILED: Could not clean legacy modules"
                    exit 1
                fi
                ;;
            2)
                log_error "❌ Preflight FAILED: Error detecting legacy modules"
                exit 1
                ;;
        esac
    fi
    
    # Step 3: Check for broken references
    if ! check_broken_references; then
        case $? in
            1)
                log_warning "⚠️ Broken references detected - may need manual cleanup"
                log_info "💡 Run clinic_autofix.sh after preflight to attempt auto-repair"
                ;;
            2)
                log_error "❌ Error checking broken references"
                ;;
        esac
    fi
    
    # Step 4: Update apps list
    if ! update_apps_list; then
        log_error "❌ Preflight FAILED: Could not update apps list"
        exit 1
    fi
    
    log_success "✅ Preflight check completed successfully!"
    log_info "📋 Log saved to: $LOG_FILE"
    log_info "🚀 Ready to install clinic_installer module"
}

# Help function
show_help() {
    echo "Clinic System Preflight Checker"
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help"
    echo "  -d, --db NAME  Database name (default: clinic_dev)"
    echo "  -c, --config   Config file (default: odoo.conf)"
    echo ""
    echo "Environment variables:"
    echo "  ODP     Odoo binary command (default: python odoo/odoo-bin)"
    echo "  CFG     Odoo config file (default: odoo.conf)"
    echo "  DB      Database name (default: clinic_dev)"
    echo ""
    echo "Examples:"
    echo "  DB=clinic_prod $0"
    echo "  $0 -d clinic_test -c test.conf"
}

# Parse command line arguments
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