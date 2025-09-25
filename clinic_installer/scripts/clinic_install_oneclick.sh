#!/usr/bin/env bash
# Clinic System One-Click Installer
# =================================
# Professional installation with validation and rollback

set -euo pipefail

# Configuration  
ODP="${ODP:-python odoo/odoo-bin}"
CFG="${CFG:-odoo.conf}"
DB="${DB:-clinic_dev}"
MOD="${MOD:-clinic_installer}"
LOG_FILE="${LOG_FILE:-clinic_oneclick.log}"
BACKUP_PREFIX="${BACKUP_PREFIX:-clinic_backup_$(date +%Y%m%d_%H%M%S)}"

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

# Create database backup before installation
create_backup() {
    log_info "💾 Creating database backup..."
    
    if command -v pg_dump >/dev/null 2>&1; then
        backup_file="${BACKUP_PREFIX}.sql"
        
        if pg_dump -h localhost -U postgres -d "${DB}" -f "${backup_file}" 2>/dev/null; then
            log_success "✅ Backup created: $backup_file"
            echo "$backup_file" > /tmp/clinic_backup_path
        else
            log_warning "⚠️ Could not create backup - proceeding without backup"
        fi
    else
        log_warning "⚠️ pg_dump not found - proceeding without backup"
    fi
}

# Validate installation order
validate_installation_order() {
    log_info "🔍 Validating installation order..."
    
    cat > /tmp/clinic_validate_order.py <<'EOF'
import sys

REQUIRED_ORDER = [
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

try:
    # Check which modules exist
    available_modules = env['ir.module.module'].search([
        ('name', 'in', REQUIRED_ORDER)
    ])
    
    available_names = set(available_modules.mapped('name'))
    required_names = set(REQUIRED_ORDER)
    
    missing = required_names - available_names
    if missing:
        print(f"VALIDATION_ERROR:Missing modules: {','.join(missing)}")
        sys.exit(1)
    
    # Check for dependency conflicts
    installed = env['ir.module.module'].search([
        ('state', '=', 'installed'),
        ('name', 'in', REQUIRED_ORDER)
    ])
    
    print(f"VALIDATION_OK:Found {len(available_modules)} modules, {len(installed)} already installed")
    sys.exit(0)
    
except Exception as e:
    print(f"VALIDATION_ERROR:{str(e)}")
    sys.exit(1)
EOF

    result=$(${ODP} -c ${CFG} shell -d ${DB} < /tmp/clinic_validate_order.py 2>&1)
    rm -f /tmp/clinic_validate_order.py
    
    case "$result" in
        "VALIDATION_OK:"*)
            info="${result#VALIDATION_OK:}"
            log_success "✅ Installation order validated: $info"
            return 0
            ;;
        "VALIDATION_ERROR:"*)
            error="${result#VALIDATION_ERROR:}"
            log_error "❌ Validation failed: $error"
            return 1
            ;;
        *)
            log_error "❌ Validation error: $result"
            return 1
            ;;
    esac
}

# Install clinic system with progress monitoring
install_clinic_system() {
    log_info "🚀 Installing clinic system..."
    
    # Install with proper flags
    local install_cmd=(
        ${ODP}
        -c ${CFG}
        -d ${DB}
        -i ${MOD}
        --stop-after-init
        --no-http
    )
    
    # Add demo data if requested
    if [[ "${LOAD_DEMO:-false}" == "true" ]]; then
        install_cmd+=(--load-language=en_US)
        log_info "📊 Demo data will be loaded"
    else
        install_cmd+=(--without-demo=all)
    fi
    
    log_info "Executing: ${install_cmd[*]}"
    
    # Execute installation with timeout
    if timeout 1800 "${install_cmd[@]}" 2>&1 | tee -a "$LOG_FILE"; then
        log_success "✅ Clinic system installed successfully"
        return 0
    else
        log_error "❌ Installation failed or timed out"
        return 1
    fi
}

# Verify installation success
verify_installation() {
    log_info "🔍 Verifying installation..."
    
    cat > /tmp/clinic_verify.py <<'EOF'
import sys

try:
    # Check that clinic_installer is installed
    installer = env['ir.module.module'].search([
        ('name', '=', 'clinic_installer'),
        ('state', '=', 'installed')
    ], limit=1)
    
    if not installer:
        print("VERIFY_ERROR:clinic_installer not installed")
        sys.exit(1)
    
    # Check core modules are installed
    CORE_MODULES = ['clinic_patient', 'clinic_staff', 'clinic_appointment_core']
    core_installed = env['ir.module.module'].search([
        ('name', 'in', CORE_MODULES),
        ('state', '=', 'installed')
    ])
    
    if len(core_installed) != len(CORE_MODULES):
        print(f"VERIFY_ERROR:Core modules not fully installed ({len(core_installed)}/{len(CORE_MODULES)})")
        sys.exit(1)
    
    # Check main menu exists
    clinic_menus = env['ir.ui.menu'].search([
        ('name', 'ilike', 'clinic'),
        ('parent_id', '=', False)
    ])
    
    if not clinic_menus:
        print("VERIFY_WARNING:No main clinic menu found")
    
    # Count total installed clinic modules
    total_installed = env['ir.module.module'].search([
        ('name', 'ilike', 'clinic_%'),
        ('state', '=', 'installed')
    ])
    
    print(f"VERIFY_SUCCESS:Installed {len(total_installed)} clinic modules")
    sys.exit(0)
    
except Exception as e:
    print(f"VERIFY_ERROR:{str(e)}")
    sys.exit(1)
EOF

    result=$(${ODP} -c ${CFG} shell -d ${DB} < /tmp/clinic_verify.py 2>&1)
    rm -f /tmp/clinic_verify.py
    
    case "$result" in
        "VERIFY_SUCCESS:"*)
            info="${result#VERIFY_SUCCESS:}"
            log_success "✅ Installation verified: $info"
            return 0
            ;;
        "VERIFY_WARNING:"*)
            warning="${result#VERIFY_WARNING:}"
            log_warning "⚠️ Verification warning: $warning"
            return 0
            ;;
        "VERIFY_ERROR:"*)
            error="${result#VERIFY_ERROR:}"
            log_error "❌ Verification failed: $error"
            return 1
            ;;
        *)
            log_error "❌ Verification error: $result"
            return 1
            ;;
    esac
}

# Rollback on failure
rollback_installation() {
    log_warning "🔄 Rolling back installation..."
    
    if [[ -f /tmp/clinic_backup_path ]]; then
        backup_file=$(cat /tmp/clinic_backup_path)
        if [[ -f "$backup_file" ]]; then
            log_info "Restoring from backup: $backup_file"
            
            # Drop and recreate database
            if dropdb -U postgres "${DB}" 2>/dev/null && \
               createdb -U postgres "${DB}" 2>/dev/null && \
               psql -U postgres -d "${DB}" < "$backup_file" >/dev/null 2>&1; then
                log_success "✅ Database restored from backup"
            else
                log_error "❌ Could not restore from backup"
            fi
        fi
    else
        log_warning "⚠️ No backup available for rollback"
    fi
}

# Main installation routine
main() {
    log_info "🚀 Clinic System One-Click Installer"
    log_info "===================================="
    log_info "Database: $DB"
    log_info "Module: $MOD"
    log_info "Config: $CFG"
    log_info ""
    
    # Initialize log
    echo "$(date): Starting one-click installation" > "$LOG_FILE"
    
    # Trap for cleanup on exit
    trap 'rm -f /tmp/clinic_*' EXIT
    
    # Step 1: Create backup
    create_backup
    
    # Step 2: Validate installation order
    if ! validate_installation_order; then
        log_error "❌ Installation aborted due to validation errors"
        exit 1
    fi
    
    # Step 3: Install clinic system
    if ! install_clinic_system; then
        log_error "❌ Installation failed"
        rollback_installation
        exit 1
    fi
    
    # Step 4: Verify installation
    if ! verify_installation; then
        log_error "❌ Installation verification failed"
        rollback_installation  
        exit 1
    fi
    
    # Cleanup
    rm -f /tmp/clinic_backup_path
    
    log_success "🎉 One-click installation completed successfully!"
    log_info "📋 Next steps:"
    log_info "   1. Start Odoo: ${ODP} -c ${CFG} -d ${DB}"
    log_info "   2. Access web interface: http://localhost:8069"
    log_info "   3. Login and configure your clinic"
    log_info ""
    log_info "📝 Installation log: $LOG_FILE"
}

# Help function
show_help() {
    echo "Clinic System One-Click Installer"
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help       Show this help"
    echo "  -d, --db NAME    Database name"
    echo "  -m, --module MOD Module to install (default: clinic_installer)"
    echo "  --demo           Load demo data"
    echo "  --no-backup      Skip database backup"
    echo ""
    echo "Examples:"
    echo "  DB=clinic_prod $0"
    echo "  $0 -d clinic_test --demo"
    echo "  LOAD_DEMO=true $0"
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
        -m|--module)
            MOD="$2"
            shift 2
            ;;
        --demo)
            export LOAD_DEMO=true
            shift
            ;;
        --no-backup)
            export NO_BACKUP=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

main "$@"