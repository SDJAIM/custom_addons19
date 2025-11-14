# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SlotMetrics(models.Model):
    """
    Performance metrics for slot generation engine (TASK-F1-012)
    Tracks response times, cache hits, and slot counts for monitoring
    """
    _name = 'clinic.slot.metrics'
    _description = 'Slot Generation Performance Metrics'
    _order = 'create_date desc'
    _rec_name = 'create_date'

    # Request Details
    appointment_type_id = fields.Many2one(
        'clinic.appointment.type',
        string='Appointment Type',
        ondelete='cascade',
        index=True
    )

    staff_id = fields.Many2one(
        'clinic.staff',
        string='Staff Member',
        ondelete='set null',
        help='Specific staff requested, or None for all staff'
    )

    # Date Range
    start_date = fields.Date(
        string='Start Date',
        required=True
    )

    end_date = fields.Date(
        string='End Date',
        required=True
    )

    date_range_days = fields.Integer(
        string='Date Range (Days)',
        compute='_compute_date_range_days',
        store=True
    )

    # Performance Metrics
    slots_generated = fields.Integer(
        string='Slots Generated',
        required=True,
        help='Total number of slots generated'
    )

    duration_seconds = fields.Float(
        string='Duration (seconds)',
        required=True,
        digits=(10, 4),
        help='Time taken to generate slots'
    )

    cache_hit = fields.Boolean(
        string='Cache Hit',
        default=False,
        help='Was this request served from cache?'
    )

    # Additional Context
    timezone = fields.Char(
        string='Timezone',
        default='UTC'
    )

    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        readonly=True
    )

    # Computed Performance Indicators
    slots_per_second = fields.Float(
        string='Slots/Second',
        compute='_compute_performance_indicators',
        store=True,
        help='Throughput metric'
    )

    is_slow = fields.Boolean(
        string='Slow Query',
        compute='_compute_performance_indicators',
        store=True,
        help='Duration > 2 seconds (P95 threshold)'
    )

    performance_grade = fields.Selection([
        ('excellent', 'Excellent'),  # < 0.5s
        ('good', 'Good'),            # 0.5s - 1s
        ('acceptable', 'Acceptable'), # 1s - 2s
        ('slow', 'Slow'),            # > 2s
    ], string='Performance Grade',
       compute='_compute_performance_indicators',
       store=True)

    @api.depends('start_date', 'end_date')
    def _compute_date_range_days(self):
        for record in self:
            if record.start_date and record.end_date:
                delta = record.end_date - record.start_date
                record.date_range_days = delta.days + 1
            else:
                record.date_range_days = 0

    @api.depends('duration_seconds', 'slots_generated')
    def _compute_performance_indicators(self):
        for record in self:
            # Slots per second
            if record.duration_seconds > 0:
                record.slots_per_second = record.slots_generated / record.duration_seconds
            else:
                record.slots_per_second = 0

            # Slow query flag (P95 threshold from requirements)
            record.is_slow = record.duration_seconds > 2.0

            # Performance grade
            if record.duration_seconds < 0.5:
                record.performance_grade = 'excellent'
            elif record.duration_seconds < 1.0:
                record.performance_grade = 'good'
            elif record.duration_seconds < 2.0:
                record.performance_grade = 'acceptable'
            else:
                record.performance_grade = 'slow'

    @api.model
    def get_performance_stats(self, days=30):
        """
        Get aggregated performance statistics for dashboard

        Args:
            days (int): Number of days to look back (default 30)

        Returns:
            dict: Performance statistics
        """
        cutoff_date = fields.Datetime.now() - fields.timedelta(days=days)

        metrics = self.search([
            ('create_date', '>=', cutoff_date)
        ])

        if not metrics:
            return {
                'total_requests': 0,
                'avg_duration': 0,
                'p95_duration': 0,
                'cache_hit_rate': 0,
                'slow_query_count': 0,
                'avg_slots_per_request': 0,
            }

        durations = metrics.mapped('duration_seconds')
        durations_sorted = sorted(durations)

        # Calculate P95 (95th percentile)
        p95_index = int(len(durations_sorted) * 0.95)
        p95_duration = durations_sorted[p95_index] if durations_sorted else 0

        cache_hits = len(metrics.filtered(lambda m: m.cache_hit))
        slow_queries = len(metrics.filtered(lambda m: m.is_slow))

        return {
            'total_requests': len(metrics),
            'avg_duration': sum(durations) / len(durations) if durations else 0,
            'p95_duration': p95_duration,
            'cache_hit_rate': (cache_hits / len(metrics) * 100) if metrics else 0,
            'slow_query_count': slow_queries,
            'slow_query_rate': (slow_queries / len(metrics) * 100) if metrics else 0,
            'avg_slots_per_request': sum(metrics.mapped('slots_generated')) / len(metrics) if metrics else 0,
        }

    @api.model
    def get_performance_trend(self, days=7):
        """
        Get performance trend data for charts

        Args:
            days (int): Number of days for trend analysis

        Returns:
            list: Daily performance data
        """
        from datetime import date, timedelta

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        trend_data = []

        for i in range(days):
            current_date = start_date + timedelta(days=i)
            next_date = current_date + timedelta(days=1)

            daily_metrics = self.search([
                ('create_date', '>=', fields.Datetime.to_datetime(current_date)),
                ('create_date', '<', fields.Datetime.to_datetime(next_date))
            ])

            if daily_metrics:
                durations = daily_metrics.mapped('duration_seconds')
                cache_hits = len(daily_metrics.filtered(lambda m: m.cache_hit))

                trend_data.append({
                    'date': current_date.isoformat(),
                    'avg_duration': sum(durations) / len(durations),
                    'request_count': len(daily_metrics),
                    'cache_hit_rate': (cache_hits / len(daily_metrics) * 100),
                })
            else:
                trend_data.append({
                    'date': current_date.isoformat(),
                    'avg_duration': 0,
                    'request_count': 0,
                    'cache_hit_rate': 0,
                })

        return trend_data

    @api.model
    def cleanup_old_metrics(self, days=90):
        """
        Clean up metrics older than specified days
        Called by cron job to prevent unlimited growth

        Args:
            days (int): Keep metrics from last N days
        """
        cutoff_date = fields.Datetime.now() - fields.timedelta(days=days)

        old_metrics = self.search([
            ('create_date', '<', cutoff_date)
        ])

        count = len(old_metrics)
        old_metrics.unlink()

        return count
