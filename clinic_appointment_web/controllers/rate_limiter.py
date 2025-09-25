# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import functools
import hashlib
import json


class RateLimiter:
    """
    Rate limiting middleware for web controllers
    Stores attempts in database for distributed systems
    """

    @staticmethod
    def get_client_identifier():
        """Get unique identifier for the client"""
        # Use combination of IP and session for identification
        ip = request.httprequest.environ.get('REMOTE_ADDR', '')
        session_id = request.session.sid or 'anonymous'
        user_agent = request.httprequest.environ.get('HTTP_USER_AGENT', '')

        # Create hash for privacy
        identifier = hashlib.sha256(
            f"{ip}:{session_id}:{user_agent}".encode()
        ).hexdigest()

        return identifier

    @staticmethod
    def check_rate_limit(resource, max_attempts=5, window_minutes=60):
        """
        Check if client has exceeded rate limit

        :param resource: Resource being accessed (e.g., 'appointment_booking')
        :param max_attempts: Maximum attempts allowed
        :param window_minutes: Time window in minutes
        :return: (allowed, remaining_attempts, reset_time)
        """
        RateLimit = request.env['clinic.rate_limit'].sudo()
        client_id = RateLimiter.get_client_identifier()

        # Clean old entries
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        RateLimit.search([
            ('timestamp', '<', cutoff_time)
        ]).unlink()

        # Count recent attempts
        recent_attempts = RateLimit.search_count([
            ('client_id', '=', client_id),
            ('resource', '=', resource),
            ('timestamp', '>', cutoff_time)
        ])

        # Check if limit exceeded
        if recent_attempts >= max_attempts:
            reset_time = datetime.now() + timedelta(minutes=window_minutes)
            return False, 0, reset_time

        # Record this attempt
        RateLimit.create({
            'client_id': client_id,
            'resource': resource,
            'timestamp': datetime.now(),
            'ip_address': request.httprequest.environ.get('REMOTE_ADDR', ''),
        })

        remaining = max_attempts - recent_attempts - 1
        return True, remaining, None

    @staticmethod
    def rate_limit_decorator(resource='default', max_attempts=10, window_minutes=60):
        """
        Decorator for rate limiting controller methods

        Usage:
            @rate_limit_decorator(resource='appointment_booking', max_attempts=5, window_minutes=60)
            def book_appointment(self, **kw):
                ...
        """
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                allowed, remaining, reset_time = RateLimiter.check_rate_limit(
                    resource, max_attempts, window_minutes
                )

                if not allowed:
                    # Return rate limit error
                    response = request.make_response(
                        json.dumps({
                            'error': 'rate_limit_exceeded',
                            'message': _('Too many requests. Please try again later.'),
                            'reset_time': reset_time.isoformat() if reset_time else None
                        }),
                        headers=[
                            ('Content-Type', 'application/json'),
                            ('X-RateLimit-Limit', str(max_attempts)),
                            ('X-RateLimit-Remaining', '0'),
                            ('X-RateLimit-Reset', str(int(reset_time.timestamp())) if reset_time else '0'),
                            ('Retry-After', str(window_minutes * 60))
                        ],
                        status=429  # Too Many Requests
                    )
                    return response

                # Add rate limit headers to response
                result = func(*args, **kwargs)

                if hasattr(result, 'headers'):
                    result.headers.extend([
                        ('X-RateLimit-Limit', str(max_attempts)),
                        ('X-RateLimit-Remaining', str(remaining)),
                    ])

                return result

            return wrapper
        return decorator