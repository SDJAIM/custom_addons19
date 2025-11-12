# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class WhatsAppWebhookEvent(models.Model):
    """
    Webhook Event Log for Idempotency

    🔄 PURPOSE: Prevent duplicate processing of webhook events
    Meta resends webhooks if we don't respond with 200 within 20 seconds

    Reference: https://developers.facebook.com/docs/graph-api/webhooks/getting-started#event-notifications
    """
    _name = 'clinic.whatsapp.webhook.event'
    _description = 'WhatsApp Webhook Event Log (Idempotency)'
    _order = 'processed_at desc'
    _rec_name = 'event_id'

    # Core fields
    event_id = fields.Char(
        string='Event ID',
        required=True,
        index=True,
        help="Message ID or Status ID from Meta - used for deduplication"
    )

    event_type = fields.Selection([
        ('message', 'Incoming Message'),
        ('status', 'Status Update'),
    ], string='Event Type', required=True, index=True)

    # Timestamps
    processed_at = fields.Datetime(
        string='Processed At',
        default=fields.Datetime.now,
        readonly=True,
        index=True,
        help="When we successfully processed this event"
    )

    event_timestamp = fields.Integer(
        string='Event Timestamp',
        help="Timestamp from Meta (Unix epoch)"
    )

    # Payload storage (for debugging)
    payload = fields.Text(
        string='Raw Payload',
        help="Full JSON payload from Meta (useful for debugging)"
    )

    # Related data
    message_id = fields.Many2one(
        'clinic.whatsapp.message',
        string='WhatsApp Message',
        ondelete='set null',
        help="The message record created from this webhook"
    )

    from_number = fields.Char(
        string='From Number',
        help="Sender phone number (for incoming messages)"
    )

    # Processing status
    processing_result = fields.Selection([
        ('success', 'Success'),
        ('duplicate', 'Duplicate (Skipped)'),
        ('error', 'Error'),
    ], string='Result', default='success', readonly=True)

    error_message = fields.Text(
        string='Error Message',
        readonly=True,
        help="If processing failed, the error details"
    )

    # SQL constraint: One event_id can only be processed once
    _sql_constraints = [
        ('event_id_unique', 'UNIQUE(event_id)', 'This webhook event has already been processed'),
    ]

    @api.model
    def is_duplicate(self, event_id):
        """
        Check if event has already been processed

        Args:
            event_id (str): Message ID or Status ID

        Returns:
            bool: True if duplicate
        """
        return bool(self.search_count([('event_id', '=', event_id)]))

    @api.model
    def mark_processed(self, event_id, event_type, payload_dict, message_id=None, from_number=None):
        """
        Mark event as processed

        Args:
            event_id (str): Message/Status ID
            event_type (str): 'message' or 'status'
            payload_dict (dict): Full webhook payload
            message_id (int): Optional clinic.whatsapp.message ID
            from_number (str): Optional sender number

        Returns:
            recordset: Created webhook_event record
        """
        import json

        try:
            return self.create({
                'event_id': event_id,
                'event_type': event_type,
                'payload': json.dumps(payload_dict, indent=2),
                'message_id': message_id,
                'from_number': from_number,
                'event_timestamp': payload_dict.get('timestamp'),
                'processing_result': 'success',
            })
        except Exception as e:
            _logger.error(f"Failed to mark event {event_id} as processed: {e}")
            return self.env['clinic.whatsapp.webhook.event']

    @api.model
    def mark_duplicate(self, event_id, event_type):
        """
        Log duplicate webhook attempt

        This doesn't create a record (would violate unique constraint),
        just logs for monitoring purposes.
        """
        _logger.info(f"🔄 Duplicate webhook event skipped: {event_id} ({event_type})")

    @api.model
    def mark_error(self, event_id, event_type, payload_dict, error_msg):
        """
        Log failed webhook processing

        Note: We still create a record to prevent reprocessing failed events.
        Admins can manually delete the record to retry.
        """
        import json

        try:
            return self.create({
                'event_id': event_id,
                'event_type': event_type,
                'payload': json.dumps(payload_dict, indent=2),
                'event_timestamp': payload_dict.get('timestamp'),
                'processing_result': 'error',
                'error_message': error_msg,
            })
        except Exception as e:
            _logger.error(f"Failed to log error for event {event_id}: {e}")
            return self.env['clinic.whatsapp.webhook.event']

    @api.model
    def cleanup_old_events(self, days=90):
        """
        Clean up old webhook events (older than N days)

        Should be called by scheduled action monthly.

        Args:
            days (int): Keep events newer than this

        Returns:
            int: Number of deleted records
        """
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=days)
        old_events = self.search([
            ('processed_at', '<', cutoff_date),
            ('processing_result', '!=', 'error')  # Keep errors for analysis
        ])

        count = len(old_events)
        old_events.unlink()

        _logger.info(f"🧹 Cleaned up {count} webhook events older than {days} days")
        return count
