# -*- coding: utf-8 -*-
"""
Migration script to move WhatsApp configuration from database model to ir.config_parameter
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migrate WhatsApp configuration from clinic.whatsapp.config to ir.config_parameter

    Args:
        cr: Database cursor
        version: Module version
    """
    _logger.info("Starting WhatsApp configuration migration to ir.config_parameter")

    # Check if the old configuration table exists
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'clinic_whatsapp_config'
        )
    """)

    table_exists = cr.fetchone()[0]

    if not table_exists:
        _logger.info("No existing WhatsApp configuration table found, skipping migration")
        return

    # Get existing configurations
    cr.execute("""
        SELECT id, name, api_url, api_token, phone_number, create_date
        FROM clinic_whatsapp_config
        WHERE migrated_to_config_params IS NOT TRUE
        ORDER BY create_date DESC
    """)

    configs = cr.fetchall()

    if not configs:
        _logger.info("No WhatsApp configurations found to migrate")
        return

    # Use the most recent configuration
    latest_config = configs[0]
    config_id, name, api_url, api_token, phone_number, create_date = latest_config

    _logger.info(f"Migrating WhatsApp configuration '{name}' (ID: {config_id}) to ir.config_parameter")

    # Migrate configuration values to ir.config_parameter
    migration_data = []

    if api_url:
        migration_data.append(('clinic.whatsapp.api_url', api_url))

    if api_token:
        migration_data.append(('clinic.whatsapp.api_token', api_token))

    if phone_number:
        migration_data.append(('clinic.whatsapp.phone_number', phone_number))

    # Set default values for new configuration options
    default_params = [
        ('clinic.whatsapp.default_country_code', '+1'),
        ('clinic.whatsapp.max_retries', '3'),
        ('clinic.whatsapp.retry_delay', '5'),
        ('clinic.whatsapp.enable_reminders', 'True'),
        ('clinic.whatsapp.enable_confirmations', 'True'),
        ('clinic.whatsapp.enable_prescription_reminders', 'True'),
        ('clinic.whatsapp.enable_auto_responses', 'True'),
        ('clinic.whatsapp.require_opt_in', 'True'),
        ('clinic.whatsapp.webhook_enabled', 'True'),
    ]

    migration_data.extend(default_params)

    # Insert/Update configuration parameters
    for key, value in migration_data:
        # Check if parameter already exists
        cr.execute("""
            SELECT id FROM ir_config_parameter
            WHERE key = %s
        """, (key,))

        existing = cr.fetchone()

        if existing:
            # Update existing parameter
            cr.execute("""
                UPDATE ir_config_parameter
                SET value = %s
                WHERE key = %s
            """, (value, key))
            _logger.info(f"Updated parameter: {key} = {value}")
        else:
            # Insert new parameter
            cr.execute("""
                INSERT INTO ir_config_parameter (key, value)
                VALUES (%s, %s)
            """, (key, value))
            _logger.info(f"Created parameter: {key} = {value}")

    # Mark all configurations as migrated
    cr.execute("""
        UPDATE clinic_whatsapp_config
        SET migrated_to_config_params = TRUE
        WHERE migrated_to_config_params IS NOT TRUE
    """)

    migrated_count = cr.rowcount
    _logger.info(f"Marked {migrated_count} WhatsApp configurations as migrated")

    # Add migration log entry
    cr.execute("""
        INSERT INTO ir_config_parameter (key, value)
        VALUES ('clinic.whatsapp.migration_completed', %s)
    """, (create_date.isoformat(),))

    _logger.info("WhatsApp configuration migration completed successfully")


def rollback_migration(cr, version):
    """
    Rollback migration if needed (for development/testing)

    Args:
        cr: Database cursor
        version: Module version
    """
    _logger.warning("Rolling back WhatsApp configuration migration")

    # Remove migrated configuration parameters
    whatsapp_params = [
        'clinic.whatsapp.api_url',
        'clinic.whatsapp.api_token',
        'clinic.whatsapp.phone_number',
        'clinic.whatsapp.default_country_code',
        'clinic.whatsapp.max_retries',
        'clinic.whatsapp.retry_delay',
        'clinic.whatsapp.enable_reminders',
        'clinic.whatsapp.enable_confirmations',
        'clinic.whatsapp.enable_prescription_reminders',
        'clinic.whatsapp.enable_auto_responses',
        'clinic.whatsapp.require_opt_in',
        'clinic.whatsapp.webhook_enabled',
        'clinic.whatsapp.migration_completed',
    ]

    for param in whatsapp_params:
        cr.execute("""
            DELETE FROM ir_config_parameter
            WHERE key = %s
        """, (param,))

    # Reset migration flag on configurations
    cr.execute("""
        UPDATE clinic_whatsapp_config
        SET migrated_to_config_params = FALSE
        WHERE migrated_to_config_params = TRUE
    """)

    _logger.warning("WhatsApp configuration migration rollback completed")