# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval
import logging
from datetime import datetime, timedelta
import threading
import queue
import json

_logger = logging.getLogger(__name__)


class ClinicBatchProcessor(models.Model):
    _name = 'clinic.batch.processor'
    _description = 'Batch Processing Jobs'
    _order = 'create_date desc'

    name = fields.Char(
        string='Job Name',
        required=True,
        readonly=True
    )

    job_type = fields.Selection([
        ('appointment_reminder', 'Send Appointment Reminders'),
        ('invoice_generation', 'Generate Invoices'),
        ('insurance_claim', 'Process Insurance Claims'),
        ('patient_followup', 'Patient Follow-up Reminders'),
        ('prescription_expiry', 'Prescription Expiry Notifications'),
        ('inventory_check', 'Inventory Stock Check'),
        ('report_generation', 'Generate Reports'),
        ('data_cleanup', 'Data Cleanup'),
        ('email_campaign', 'Email Campaign'),
        ('payment_reminder', 'Payment Reminders'),
        ('lab_result_notification', 'Lab Result Notifications'),
        ('custom', 'Custom Job')
    ], string='Job Type', required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    # Scheduling
    scheduled_date = fields.Datetime(
        string='Scheduled Date',
        help='When to run this job'
    )

    is_recurring = fields.Boolean(
        string='Recurring Job',
        help='Job will repeat based on frequency'
    )

    frequency = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom')
    ], string='Frequency')

    next_run = fields.Datetime(
        string='Next Run',
        compute='_compute_next_run',
        store=True
    )

    # Execution Details
    start_time = fields.Datetime(
        string='Start Time',
        readonly=True
    )

    end_time = fields.Datetime(
        string='End Time',
        readonly=True
    )

    duration = fields.Float(
        string='Duration (seconds)',
        compute='_compute_duration',
        store=True
    )

    # Progress Tracking
    total_records = fields.Integer(
        string='Total Records',
        readonly=True
    )

    processed_records = fields.Integer(
        string='Processed Records',
        readonly=True
    )

    success_count = fields.Integer(
        string='Successful',
        readonly=True
    )

    error_count = fields.Integer(
        string='Errors',
        readonly=True
    )

    progress_percentage = fields.Float(
        string='Progress %',
        compute='_compute_progress',
        store=True
    )

    # Parameters
    parameters = fields.Text(
        string='Parameters',
        help='JSON parameters for the job'
    )

    filter_domain = fields.Text(
        string='Filter Domain',
        help='Domain to filter records for processing'
    )

    batch_size = fields.Integer(
        string='Batch Size',
        default=100,
        help='Number of records to process in each batch'
    )

    # Results
    result_summary = fields.Text(
        string='Result Summary',
        readonly=True
    )

    error_log = fields.Text(
        string='Error Log',
        readonly=True
    )

    # Related Records
    model_name = fields.Char(
        string='Model',
        help='Model to process'
    )

    record_ids = fields.Text(
        string='Record IDs',
        help='Specific record IDs to process (comma-separated)'
    )

    @api.depends('scheduled_date', 'is_recurring', 'frequency')
    def _compute_next_run(self):
        for record in self:
            if record.is_recurring and record.scheduled_date:
                if record.frequency == 'daily':
                    record.next_run = record.scheduled_date + timedelta(days=1)
                elif record.frequency == 'weekly':
                    record.next_run = record.scheduled_date + timedelta(weeks=1)
                elif record.frequency == 'monthly':
                    record.next_run = record.scheduled_date + timedelta(days=30)
                else:
                    record.next_run = record.scheduled_date
            else:
                record.next_run = record.scheduled_date

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for record in self:
            if record.start_time and record.end_time:
                delta = record.end_time - record.start_time
                record.duration = delta.total_seconds()
            else:
                record.duration = 0

    @api.depends('total_records', 'processed_records')
    def _compute_progress(self):
        for record in self:
            if record.total_records > 0:
                record.progress_percentage = (record.processed_records / record.total_records) * 100
            else:
                record.progress_percentage = 0

    def action_schedule(self):
        """Schedule the batch job"""
        self.ensure_one()
        if not self.scheduled_date:
            self.scheduled_date = fields.Datetime.now()
        self.state = 'scheduled'

        # Create cron job if recurring
        if self.is_recurring:
            self._create_cron_job()

        return True

    def action_run(self):
        """Run the batch job"""
        for record in self:
            if record.state not in ['scheduled', 'draft']:
                continue

            record.write({
                'state': 'running',
                'start_time': fields.Datetime.now(),
                'processed_records': 0,
                'success_count': 0,
                'error_count': 0,
                'error_log': ''
            })

            try:
                # Run the appropriate job method
                method_name = f"_run_{record.job_type}"
                if hasattr(record, method_name):
                    getattr(record, method_name)()
                else:
                    record._run_custom_job()

                record.write({
                    'state': 'completed',
                    'end_time': fields.Datetime.now()
                })

            except Exception as e:
                _logger.error(f"Batch job {record.name} failed: {str(e)}")
                record.write({
                    'state': 'failed',
                    'end_time': fields.Datetime.now(),
                    'error_log': str(e)
                })

    def action_cancel(self):
        """Cancel the batch job"""
        self.write({'state': 'cancelled'})

    def action_retry(self):
        """Retry failed job"""
        self.ensure_one()
        if self.state == 'failed':
            self.state = 'scheduled'
            self.action_run()

    # ========================
    # Job Implementation Methods
    # ========================

    def _run_appointment_reminder(self):
        """Send appointment reminders"""
        self.ensure_one()

        params = json.loads(self.parameters or '{}')
        days_ahead = params.get('days_ahead', 1)

        tomorrow = fields.Date.today() + timedelta(days=days_ahead)
        appointments = self.env['clinic.appointment'].search([
            ('appointment_date', '>=', tomorrow.strftime('%Y-%m-%d 00:00:00')),
            ('appointment_date', '<=', tomorrow.strftime('%Y-%m-%d 23:59:59')),
            ('state', '=', 'confirmed')
        ])

        self.total_records = len(appointments)
        errors = []

        for appointment in appointments:
            try:
                appointment.send_reminder()
                self.success_count += 1
            except Exception as e:
                self.error_count += 1
                errors.append(f"APT-{appointment.id}: {str(e)}")

            self.processed_records += 1

        self.result_summary = f"Sent {self.success_count} reminders for appointments on {tomorrow}"
        if errors:
            self.error_log = '\n'.join(errors[:100])  # Limit to 100 errors

    def _run_invoice_generation(self):
        """Generate invoices for completed appointments"""
        self.ensure_one()

        params = json.loads(self.parameters or '{}')
        date_from = params.get('date_from', fields.Date.today())
        date_to = params.get('date_to', fields.Date.today())

        appointments = self.env['clinic.appointment'].search([
            ('appointment_date', '>=', date_from),
            ('appointment_date', '<=', date_to),
            ('state', '=', 'done'),
            ('invoice_id', '=', False)
        ])

        self.total_records = len(appointments)
        created_invoices = []

        for appointment in appointments:
            try:
                invoice = appointment.create_invoice()
                if invoice:
                    created_invoices.append(invoice.id)
                    self.success_count += 1
            except Exception as e:
                self.error_count += 1
                self.error_log += f"\nAPT-{appointment.id}: {str(e)}"

            self.processed_records += 1

        self.result_summary = f"Created {len(created_invoices)} invoices"

    def _run_insurance_claim(self):
        """Process insurance claims"""
        self.ensure_one()

        claims = self.env['clinic.insurance.claim'].search([
            ('state', '=', 'draft')
        ])

        self.total_records = len(claims)

        for claim in claims:
            try:
                claim.action_submit()
                self.success_count += 1
            except Exception as e:
                self.error_count += 1
                self.error_log += f"\nClaim-{claim.id}: {str(e)}"

            self.processed_records += 1

        self.result_summary = f"Submitted {self.success_count} insurance claims"

    def _run_patient_followup(self):
        """Send follow-up reminders to patients"""
        self.ensure_one()

        today = fields.Date.today()

        # Find appointments that need follow-up
        appointments = self.env['clinic.appointment'].search([
            ('follow_up_date', '=', today),
            ('state', '=', 'done')
        ])

        self.total_records = len(appointments)

        for appointment in appointments:
            try:
                # Send follow-up reminder
                if appointment.patient_id.email:
                    template = self.env.ref('clinic_base.email_followup_reminder', False)
                    if template:
                        template.send_mail(appointment.id)
                        self.success_count += 1
            except Exception as e:
                self.error_count += 1
                self.error_log += f"\nPatient-{appointment.patient_id.id}: {str(e)}"

            self.processed_records += 1

        self.result_summary = f"Sent {self.success_count} follow-up reminders"

    def _run_prescription_expiry(self):
        """Check for expiring prescriptions"""
        self.ensure_one()

        params = json.loads(self.parameters or '{}')
        days_before = params.get('days_before', 7)

        expiry_date = fields.Date.today() + timedelta(days=days_before)

        prescriptions = self.env['clinic.prescription'].search([
            ('expiry_date', '<=', expiry_date),
            ('state', '=', 'confirmed')
        ])

        self.total_records = len(prescriptions)

        for prescription in prescriptions:
            try:
                # Notify patient and doctor
                prescription.send_expiry_notification()
                self.success_count += 1
            except Exception as e:
                self.error_count += 1
                self.error_log += f"\nRX-{prescription.id}: {str(e)}"

            self.processed_records += 1

        self.result_summary = f"Notified {self.success_count} expiring prescriptions"

    def _run_inventory_check(self):
        """Check inventory levels"""
        self.ensure_one()

        # Check for low stock items
        products = self.env['product.product'].search([
            ('type', '=', 'product'),
            ('clinic_item', '=', True)
        ])

        self.total_records = len(products)
        low_stock_items = []

        for product in products:
            try:
                if product.qty_available < product.reorder_point:
                    low_stock_items.append({
                        'product': product.name,
                        'current': product.qty_available,
                        'reorder': product.reorder_point
                    })
                    self.success_count += 1
            except Exception as e:
                self.error_count += 1

            self.processed_records += 1

        self.result_summary = f"Found {len(low_stock_items)} items below reorder point"

    def _run_report_generation(self):
        """Generate scheduled reports"""
        self.ensure_one()

        params = json.loads(self.parameters or '{}')
        report_type = params.get('report_type', 'daily_summary')

        # Generate report based on type
        if report_type == 'daily_summary':
            self._generate_daily_summary()
        elif report_type == 'monthly_revenue':
            self._generate_monthly_revenue()

        self.result_summary = f"Generated {report_type} report"

    def _run_data_cleanup(self):
        """Clean up old data"""
        self.ensure_one()

        params = json.loads(self.parameters or '{}')
        days_old = params.get('days_old', 90)

        cutoff_date = fields.Date.today() - timedelta(days=days_old)

        # Clean old audit logs
        old_logs = self.env['clinic.audit.log'].search([
            ('timestamp', '<', cutoff_date),
            ('security_level', '=', 'info')
        ])

        self.total_records = len(old_logs)
        old_logs.unlink()
        self.processed_records = self.total_records
        self.success_count = self.total_records

        self.result_summary = f"Cleaned {self.total_records} old audit logs"

    def _run_custom_job(self):
        """Run custom job based on parameters"""
        self.ensure_one()

        params = json.loads(self.parameters or '{}')

        if not self.model_name:
            raise UserError(_("Model name is required for custom jobs"))

        # Get records to process
        Model = self.env[self.model_name]

        if self.record_ids:
            record_ids = [int(x.strip()) for x in self.record_ids.split(',')]
            records = Model.browse(record_ids)
        elif self.filter_domain:
            # Use safe_eval to prevent code injection
            try:
                domain = safe_eval(self.filter_domain, {'datetime': datetime, 'timedelta': timedelta})
            except (ValueError, SyntaxError) as e:
                raise UserError(_("Invalid domain filter: %s") % str(e))
            records = Model.search(domain)
        else:
            records = Model.search([])

        self.total_records = len(records)

        # Process in batches
        for i in range(0, len(records), self.batch_size):
            batch = records[i:i + self.batch_size]

            try:
                # Call custom method if specified
                method = params.get('method')
                if method and hasattr(Model, method):
                    getattr(batch, method)()

                self.success_count += len(batch)
            except Exception as e:
                self.error_count += len(batch)
                self.error_log += f"\nBatch {i}: {str(e)}"

            self.processed_records += len(batch)

        self.result_summary = f"Processed {self.processed_records} {self.model_name} records"

    # ========================
    # Helper Methods
    # ========================

    def _create_cron_job(self):
        """Create a cron job for recurring batch processing"""
        self.ensure_one()

        cron_vals = {
            'name': f'Batch Job: {self.name}',
            'model_id': self.env['ir.model'].search([('model', '=', self._name)]).id,
            'state': 'code',
            'code': f'env["{self._name}"].browse({self.id}).action_run()',
            'interval_type': self.frequency if self.frequency != 'custom' else 'days',
            'interval_number': 1,
            'nextcall': self.scheduled_date,
            'active': True,
        }

        return self.env['ir.cron'].create(cron_vals)

    def _generate_daily_summary(self):
        """Generate daily summary report"""
        today = fields.Date.today()

        # Collect statistics
        stats = {
            'appointments': self.env['clinic.appointment'].search_count([
                ('appointment_date', '>=', today.strftime('%Y-%m-%d 00:00:00')),
                ('appointment_date', '<=', today.strftime('%Y-%m-%d 23:59:59'))
            ]),
            'new_patients': self.env['clinic.patient'].search_count([
                ('create_date', '>=', today.strftime('%Y-%m-%d 00:00:00')),
                ('create_date', '<=', today.strftime('%Y-%m-%d 23:59:59'))
            ]),
            'revenue': sum(self.env['account.move'].search([
                ('invoice_date', '=', today),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted')
            ]).mapped('amount_total'))
        }

        self.result_summary = f"Daily Summary: {stats['appointments']} appointments, {stats['new_patients']} new patients, ${stats['revenue']:,.2f} revenue"

    def _generate_monthly_revenue(self):
        """Generate monthly revenue report"""
        start_date = fields.Date.today().replace(day=1)

        revenue_data = self.env['clinic.revenue.analysis'].get_revenue_by_period(
            date_from=start_date,
            date_to=fields.Date.today(),
            groupby='month'
        )

        self.result_summary = f"Generated monthly revenue report with {len(revenue_data)} entries"

    @api.model
    def run_scheduled_jobs(self):
        """Cron method to run scheduled batch jobs"""
        jobs = self.search([
            ('state', '=', 'scheduled'),
            ('scheduled_date', '<=', fields.Datetime.now())
        ])

        for job in jobs:
            job.action_run()