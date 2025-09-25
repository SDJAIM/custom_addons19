# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, _
import json
import hashlib
from datetime import datetime, timedelta
import logging
import pickle
import base64

_logger = logging.getLogger(__name__)


class CacheManager(models.Model):
    _name = 'clinic.cache.manager'
    _description = 'Cache Management System'
    _rec_name = 'cache_key'

    cache_key = fields.Char(
        string='Cache Key',
        required=True,
        index=True
    )

    cache_value = fields.Text(
        string='Cached Value'
    )

    cache_type = fields.Selection([
        ('query', 'Query Result'),
        ('computation', 'Computation Result'),
        ('api_response', 'API Response'),
        ('report_data', 'Report Data'),
        ('analytics', 'Analytics Data'),
        ('configuration', 'Configuration')
    ], string='Cache Type', default='query')

    model_name = fields.Char(
        string='Model Name',
        index=True
    )

    method_name = fields.Char(
        string='Method Name'
    )

    user_id = fields.Many2one(
        'res.users',
        string='User',
        index=True
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    expiry_date = fields.Datetime(
        string='Expiry Date',
        required=True,
        index=True
    )

    hit_count = fields.Integer(
        string='Hit Count',
        default=0,
        help='Number of times this cache entry was accessed'
    )

    last_accessed = fields.Datetime(
        string='Last Accessed'
    )

    size_bytes = fields.Integer(
        string='Size (bytes)',
        compute='_compute_size'
    )

    is_expired = fields.Boolean(
        string='Expired',
        compute='_compute_is_expired',
        search='_search_is_expired'
    )

    tags = fields.Char(
        string='Tags',
        help='Comma-separated tags for cache invalidation'
    )

    @api.depends('cache_value')
    def _compute_size(self):
        for record in self:
            if record.cache_value:
                record.size_bytes = len(record.cache_value.encode('utf-8'))
            else:
                record.size_bytes = 0

    @api.depends('expiry_date')
    def _compute_is_expired(self):
        now = fields.Datetime.now()
        for record in self:
            record.is_expired = record.expiry_date < now

    def _search_is_expired(self, operator, value):
        now = fields.Datetime.now()
        if operator == '=' and value:
            return [('expiry_date', '<', now)]
        elif operator == '=' and not value:
            return [('expiry_date', '>=', now)]
        else:
            return []

    @api.model
    def set_cache(self, key, value, expiry_minutes=60, cache_type='query', tags=None, **kwargs):
        """Set a cache entry"""
        # Generate unique cache key
        cache_key = self._generate_cache_key(key, **kwargs)

        # Serialize value
        if isinstance(value, (dict, list)):
            cache_value = json.dumps(value, default=str)
        else:
            # For complex objects, use pickle
            try:
                cache_value = base64.b64encode(pickle.dumps(value)).decode('utf-8')
            except:
                cache_value = str(value)

        # Calculate expiry
        expiry_date = fields.Datetime.now() + timedelta(minutes=expiry_minutes)

        # Check if cache exists
        existing = self.search([('cache_key', '=', cache_key)], limit=1)

        cache_data = {
            'cache_key': cache_key,
            'cache_value': cache_value,
            'cache_type': cache_type,
            'expiry_date': expiry_date,
            'model_name': kwargs.get('model_name'),
            'method_name': kwargs.get('method_name'),
            'user_id': kwargs.get('user_specific') and self.env.user.id,
            'company_id': self.env.company.id,
            'tags': ','.join(tags) if tags else None,
        }

        if existing:
            existing.write(cache_data)
            return existing
        else:
            return self.create(cache_data)

    @api.model
    def get_cache(self, key, default=None, **kwargs):
        """Get a cache entry"""
        cache_key = self._generate_cache_key(key, **kwargs)

        cache_entry = self.search([
            ('cache_key', '=', cache_key),
            ('expiry_date', '>', fields.Datetime.now())
        ], limit=1)

        if cache_entry:
            # Update hit count and last accessed
            cache_entry.write({
                'hit_count': cache_entry.hit_count + 1,
                'last_accessed': fields.Datetime.now()
            })

            # Deserialize value
            try:
                # Try JSON first
                return json.loads(cache_entry.cache_value)
            except:
                # Try pickle
                try:
                    return pickle.loads(base64.b64decode(cache_entry.cache_value.encode('utf-8')))
                except:
                    return cache_entry.cache_value

        return default

    @api.model
    def invalidate_cache(self, key=None, tags=None, model_name=None, user_id=None, all_entries=False):
        """Invalidate cache entries"""
        domain = []

        if all_entries:
            domain = []
        elif key:
            cache_key = self._generate_cache_key(key)
            domain = [('cache_key', '=', cache_key)]
        else:
            if tags:
                tag_domains = []
                for tag in tags:
                    tag_domains.append(('tags', 'like', tag))
                if tag_domains:
                    domain.append('|' * (len(tag_domains) - 1))
                    domain.extend(tag_domains)

            if model_name:
                domain.append(('model_name', '=', model_name))

            if user_id:
                domain.append(('user_id', '=', user_id))

        if domain or all_entries:
            entries = self.search(domain)
            _logger.info(f"Invalidating {len(entries)} cache entries")
            entries.unlink()
            return len(entries)

        return 0

    @api.model
    def _generate_cache_key(self, key, user_specific=False, company_specific=True, **kwargs):
        """Generate a unique cache key"""
        key_parts = [str(key)]

        if user_specific:
            key_parts.append(f"user_{self.env.user.id}")

        if company_specific:
            key_parts.append(f"company_{self.env.company.id}")

        # Add additional parameters to key
        for k, v in sorted(kwargs.items()):
            if k not in ['model_name', 'method_name']:
                key_parts.append(f"{k}_{v}")

        full_key = '|'.join(key_parts)

        # Hash if too long
        if len(full_key) > 200:
            return hashlib.md5(full_key.encode()).hexdigest()

        return full_key

    @api.model
    def clean_expired_cache(self):
        """Clean expired cache entries (cron job)"""
        expired = self.search([('expiry_date', '<', fields.Datetime.now())])
        count = len(expired)
        expired.unlink()
        _logger.info(f"Cleaned {count} expired cache entries")
        return count

    @api.model
    def get_cache_statistics(self):
        """Get cache statistics"""
        total_entries = self.search_count([])
        expired_entries = self.search_count([('is_expired', '=', True)])
        active_entries = total_entries - expired_entries

        # Calculate total size
        self.env.cr.execute("""
            SELECT
                COUNT(*) as count,
                SUM(LENGTH(cache_value)) as total_size,
                AVG(hit_count) as avg_hits,
                cache_type
            FROM clinic_cache_manager
            WHERE expiry_date > %s
            GROUP BY cache_type
        """, (fields.Datetime.now(),))

        type_stats = self.env.cr.dictfetchall()

        # Most accessed
        top_cached = self.search([
            ('is_expired', '=', False)
        ], order='hit_count desc', limit=10)

        return {
            'total_entries': total_entries,
            'active_entries': active_entries,
            'expired_entries': expired_entries,
            'type_statistics': type_stats,
            'top_accessed': [{
                'key': c.cache_key,
                'hits': c.hit_count,
                'type': c.cache_type,
                'size': c.size_bytes
            } for c in top_cached]
        }

    @api.model
    def optimize_cache(self):
        """Optimize cache by removing least used entries"""
        # Get cache size limit from config
        max_size_mb = int(self.env['ir.config_parameter'].sudo().get_param(
            'clinic.cache_max_size_mb', 100
        ))
        max_size_bytes = max_size_mb * 1024 * 1024

        # Calculate current size
        self.env.cr.execute("""
            SELECT SUM(LENGTH(cache_value)) as total_size
            FROM clinic_cache_manager
            WHERE expiry_date > %s
        """, (fields.Datetime.now(),))
        result = self.env.cr.dictfetchone()
        current_size = result['total_size'] or 0

        if current_size > max_size_bytes:
            # Remove least recently used entries
            to_remove = current_size - max_size_bytes

            entries = self.search([
                ('is_expired', '=', False)
            ], order='last_accessed asc, hit_count asc')

            removed_size = 0
            for entry in entries:
                entry.unlink()
                removed_size += entry.size_bytes
                if removed_size >= to_remove:
                    break

            _logger.info(f"Optimized cache: removed {removed_size} bytes")

    # Decorator for caching method results
    @api.model
    def cached_method(self, expiry_minutes=60, user_specific=False, tags=None):
        """Decorator to cache method results"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Generate cache key from method and arguments
                cache_key = f"{func.__module__}.{func.__name__}"

                # Add arguments to key
                key_args = str(args) + str(kwargs)
                cache_key = f"{cache_key}:{key_args}"

                # Try to get from cache
                result = self.get_cache(
                    cache_key,
                    user_specific=user_specific,
                    model_name=func.__module__,
                    method_name=func.__name__
                )

                if result is not None:
                    _logger.debug(f"Cache hit for {func.__name__}")
                    return result

                # Execute method
                result = func(*args, **kwargs)

                # Store in cache
                self.set_cache(
                    cache_key,
                    result,
                    expiry_minutes=expiry_minutes,
                    cache_type='computation',
                    tags=tags,
                    user_specific=user_specific,
                    model_name=func.__module__,
                    method_name=func.__name__
                )

                return result

            return wrapper
        return decorator


class CachedModel(models.AbstractModel):
    """Abstract model to add caching capabilities"""
    _name = 'clinic.cached.model'
    _description = 'Cached Model Mixin'

    @api.model
    def search_cached(self, domain, limit=None, order=None, cache_minutes=30):
        """Cached search method"""
        cache_key = f"search:{self._name}:{domain}:{limit}:{order}"

        cache_manager = self.env['clinic.cache.manager']
        cached_ids = cache_manager.get_cache(
            cache_key,
            model_name=self._name,
            method_name='search_cached'
        )

        if cached_ids is not None:
            return self.browse(cached_ids)

        # Perform search
        records = self.search(domain, limit=limit, order=order)

        # Cache the IDs
        cache_manager.set_cache(
            cache_key,
            records.ids,
            expiry_minutes=cache_minutes,
            cache_type='query',
            model_name=self._name,
            method_name='search_cached'
        )

        return records

    @api.model
    def read_cached(self, fields=None, cache_minutes=30):
        """Cached read method"""
        cache_key = f"read:{self._name}:{self.ids}:{fields}"

        cache_manager = self.env['clinic.cache.manager']
        cached_data = cache_manager.get_cache(
            cache_key,
            model_name=self._name,
            method_name='read_cached'
        )

        if cached_data is not None:
            return cached_data

        # Perform read
        data = self.read(fields)

        # Cache the data
        cache_manager.set_cache(
            cache_key,
            data,
            expiry_minutes=cache_minutes,
            cache_type='query',
            model_name=self._name,
            method_name='read_cached'
        )

        return data

    def invalidate_cache(self):
        """Invalidate cache for this record"""
        cache_manager = self.env['clinic.cache.manager']
        return cache_manager.invalidate_cache(model_name=self._name)


class PerformanceMonitor(models.Model):
    _name = 'clinic.performance.monitor'
    _description = 'Performance Monitoring'
    _order = 'create_date desc'

    name = fields.Char(
        string='Operation',
        required=True
    )

    model_name = fields.Char(
        string='Model'
    )

    method_name = fields.Char(
        string='Method'
    )

    execution_time = fields.Float(
        string='Execution Time (ms)'
    )

    query_count = fields.Integer(
        string='Query Count'
    )

    memory_usage = fields.Float(
        string='Memory Usage (MB)'
    )

    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user
    )

    timestamp = fields.Datetime(
        string='Timestamp',
        default=fields.Datetime.now
    )

    is_slow = fields.Boolean(
        string='Slow Query',
        compute='_compute_is_slow'
    )

    @api.depends('execution_time')
    def _compute_is_slow(self):
        threshold = float(self.env['ir.config_parameter'].sudo().get_param(
            'clinic.slow_query_threshold_ms', 1000
        ))
        for record in self:
            record.is_slow = record.execution_time > threshold

    @api.model
    def log_performance(self, name, execution_time, **kwargs):
        """Log performance metrics"""
        self.create({
            'name': name,
            'execution_time': execution_time,
            'model_name': kwargs.get('model_name'),
            'method_name': kwargs.get('method_name'),
            'query_count': kwargs.get('query_count'),
            'memory_usage': kwargs.get('memory_usage'),
        })

    @api.model
    def get_performance_summary(self, date_from=None, date_to=None):
        """Get performance summary"""
        domain = []
        if date_from:
            domain.append(('timestamp', '>=', date_from))
        if date_to:
            domain.append(('timestamp', '<=', date_to))

        records = self.search(domain)

        if not records:
            return {}

        return {
            'total_operations': len(records),
            'avg_execution_time': sum(records.mapped('execution_time')) / len(records),
            'max_execution_time': max(records.mapped('execution_time')),
            'slow_queries': len(records.filtered('is_slow')),
            'total_queries': sum(records.mapped('query_count')),
            'avg_memory_usage': sum(records.mapped('memory_usage')) / len(records) if any(records.mapped('memory_usage')) else 0
        }