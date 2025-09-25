# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class ClinicAuditLog(models.Model):
    _name = 'clinic.audit.log'
    _description = 'Clinic Audit Log'
    _order = 'create_date desc'
    _rec_name = 'action'

    # User and Session
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        readonly=True,
        index=True
    )

    session_id = fields.Char(
        string='Session ID',
        readonly=True,
        index=True
    )

    ip_address = fields.Char(
        string='IP Address',
        readonly=True
    )

    user_agent = fields.Char(
        string='User Agent',
        readonly=True
    )

    # Action Details
    action = fields.Selection([
        ('create', 'Create'),
        ('write', 'Update'),
        ('unlink', 'Delete'),
        ('read', 'Read'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('cancel', 'Cancel'),
        ('confirm', 'Confirm'),
        ('prescription_access', 'Prescription Access'),
        ('patient_data_access', 'Patient Data Access'),
        ('financial_access', 'Financial Access'),
        ('report_generation', 'Report Generation'),
        ('settings_change', 'Settings Change'),
        ('security_alert', 'Security Alert')
    ], string='Action', required=True, index=True)

    model_name = fields.Char(
        string='Model',
        readonly=True,
        index=True
    )

    record_id = fields.Integer(
        string='Record ID',
        readonly=True
    )

    record_name = fields.Char(
        string='Record Name',
        readonly=True
    )

    # Data Changes
    field_name = fields.Char(
        string='Field',
        readonly=True
    )

    old_value = fields.Text(
        string='Old Value',
        readonly=True
    )

    new_value = fields.Text(
        string='New Value',
        readonly=True
    )

    changes = fields.Text(
        string='Changes JSON',
        readonly=True,
        help='JSON representation of all changes'
    )

    # Security and Compliance
    security_level = fields.Selection([
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('emergency', 'Emergency')
    ], string='Security Level', default='info', index=True)

    is_sensitive = fields.Boolean(
        string='Sensitive Data',
        default=False,
        help='Indicates if the action involved sensitive patient data'
    )

    compliance_relevant = fields.Boolean(
        string='Compliance Relevant',
        default=False,
        help='Action is relevant for compliance auditing'
    )

    # Additional Context
    module = fields.Char(
        string='Module',
        readonly=True
    )

    method = fields.Char(
        string='Method',
        readonly=True
    )

    description = fields.Text(
        string='Description',
        readonly=True
    )

    error_message = fields.Text(
        string='Error Message',
        readonly=True
    )

    # Timestamps
    timestamp = fields.Datetime(
        string='Timestamp',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
        index=True
    )

    @api.model
    def create_log(self, action, model_name=None, record_id=None, **kwargs):
        """Create an audit log entry"""
        try:
            # Get request context if available
            req_context = {}
            if request and hasattr(request, 'httprequest'):
                req_context = {
                    'ip_address': request.httprequest.environ.get('REMOTE_ADDR'),
                    'user_agent': request.httprequest.environ.get('HTTP_USER_AGENT'),
                    'session_id': request.session.sid if hasattr(request, 'session') else None,
                }

            # Get record name if possible
            record_name = None
            if model_name and record_id:
                try:
                    record = self.env[model_name].browse(record_id)
                    if record.exists():
                        record_name = record.display_name if hasattr(record, 'display_name') else str(record_id)
                except:
                    pass

            # Prepare log values
            log_vals = {
                'user_id': self.env.user.id,
                'action': action,
                'model_name': model_name,
                'record_id': record_id,
                'record_name': record_name,
                'timestamp': fields.Datetime.now(),
                **req_context,
                **kwargs
            }

            # Determine security level based on action
            if action in ['delete', 'unlink', 'security_alert']:
                log_vals['security_level'] = 'critical'
            elif action in ['approve', 'reject', 'financial_access', 'settings_change']:
                log_vals['security_level'] = 'warning'
            else:
                log_vals['security_level'] = 'info'

            # Check if sensitive data is involved
            sensitive_models = [
                'clinic.patient', 'clinic.prescription', 'clinic.clinical.note',
                'clinic.lab.test', 'clinic.treatment.plan'
            ]
            if model_name in sensitive_models:
                log_vals['is_sensitive'] = True
                log_vals['compliance_relevant'] = True

            # Create the log
            return self.create(log_vals)

        except Exception as e:
            _logger.error(f"Failed to create audit log: {e}")
            return False

    @api.model
    def log_data_change(self, model_name, record_id, changes_dict):
        """Log data changes with old and new values"""
        changes_json = json.dumps(changes_dict, default=str)

        for field_name, values in changes_dict.items():
            self.create_log(
                action='write',
                model_name=model_name,
                record_id=record_id,
                field_name=field_name,
                old_value=str(values.get('old')),
                new_value=str(values.get('new')),
                changes=changes_json
            )

    @api.model
    def log_security_event(self, event_type, description, level='warning', **kwargs):
        """Log security-related events"""
        return self.create_log(
            action='security_alert',
            description=description,
            security_level=level,
            **kwargs
        )

    @api.model
    def get_user_activity(self, user_id, date_from=None, date_to=None):
        """Get activity log for a specific user"""
        domain = [('user_id', '=', user_id)]
        if date_from:
            domain.append(('timestamp', '>=', date_from))
        if date_to:
            domain.append(('timestamp', '<=', date_to))

        return self.search(domain, order='timestamp desc')

    @api.model
    def get_security_alerts(self, level='warning', limit=100):
        """Get recent security alerts"""
        security_levels = {
            'info': ['info', 'warning', 'critical', 'emergency'],
            'warning': ['warning', 'critical', 'emergency'],
            'critical': ['critical', 'emergency'],
            'emergency': ['emergency']
        }

        return self.search([
            ('action', '=', 'security_alert'),
            ('security_level', 'in', security_levels.get(level, [level]))
        ], limit=limit, order='timestamp desc')

    @api.model
    def cleanup_old_logs(self, days=90):
        """Clean up old audit logs (keep critical ones longer)"""
        cutoff_date = fields.Datetime.now() - timedelta(days=days)
        critical_cutoff_date = fields.Datetime.now() - timedelta(days=days * 4)  # Keep 1 year

        # Delete non-critical old logs
        self.search([
            ('timestamp', '<', cutoff_date),
            ('security_level', 'in', ['info'])
        ]).unlink()

        # Delete critical logs after longer period
        self.search([
            ('timestamp', '<', critical_cutoff_date),
            ('security_level', 'in', ['warning', 'critical', 'emergency'])
        ]).unlink()

        _logger.info(f"Cleaned up audit logs older than {days} days")

    def get_summary(self):
        """Get a summary of the audit log entry"""
        self.ensure_one()

        summary = {
            'timestamp': self.timestamp,
            'user': self.user_id.name,
            'action': self.action,
            'model': self.model_name,
            'record': self.record_name or self.record_id,
            'security_level': self.security_level,
            'ip_address': self.ip_address,
        }

        if self.changes:
            try:
                summary['changes'] = json.loads(self.changes)
            except:
                summary['changes'] = self.changes

        return summary


class AuditedModel(models.AbstractModel):
    """Abstract model to add audit logging capabilities to any model"""
    _name = 'clinic.audited.model'
    _description = 'Audited Model Mixin'

    @api.model
    def create(self, vals):
        record = super().create(vals)
        if self._should_audit():
            self.env['clinic.audit.log'].create_log(
                action='create',
                model_name=self._name,
                record_id=record.id,
                description=f"Created {self._description or self._name} record"
            )
        return record

    def write(self, vals):
        if self._should_audit():
            # Capture old values
            old_values = {}
            for field_name in vals.keys():
                old_values[field_name] = {
                    'old': getattr(self, field_name),
                    'new': vals[field_name]
                }

            result = super().write(vals)

            # Log the changes
            for record in self:
                self.env['clinic.audit.log'].log_data_change(
                    model_name=self._name,
                    record_id=record.id,
                    changes_dict=old_values
                )
        else:
            result = super().write(vals)

        return result

    def unlink(self):
        if self._should_audit():
            for record in self:
                self.env['clinic.audit.log'].create_log(
                    action='unlink',
                    model_name=self._name,
                    record_id=record.id,
                    description=f"Deleted {self._description or self._name} record: {record.display_name if hasattr(record, 'display_name') else record.id}"
                )
        return super().unlink()

    def _should_audit(self):
        """Check if this model should be audited"""
        # Override this method in inheriting models to control auditing
        audited_models = [
            'clinic.patient',
            'clinic.prescription',
            'clinic.clinical.note',
            'clinic.treatment.plan',
            'clinic.appointment',
            'account.move',
            'clinic.lab.test'
        ]
        return self._name in audited_models