# -*- coding: utf-8 -*-
import json
import logging
import hmac
import hashlib
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WhatsAppWebhook(http.Controller):
    """
    WhatsApp Cloud API Webhook Handler

    🔒 SECURITY: Validates X-Hub-Signature-256 to prevent forgery attacks
    Reference: https://developers.facebook.com/docs/graph-api/webhooks/getting-started
    """

    @http.route('/whatsapp/webhook', type='http', auth='none', methods=['GET'], csrf=False)
    def webhook_verify(self, **kwargs):
        """
        Webhook verification endpoint (Meta initial setup)

        Meta sends: hub.mode=subscribe, hub.challenge=<random>, hub.verify_token=<your_token>
        Must respond with hub.challenge if verify_token matches

        Reference: https://developers.facebook.com/docs/graph-api/webhooks/getting-started#verification-requests
        """
        mode = kwargs.get('hub.mode')
        token = kwargs.get('hub.verify_token')
        challenge = kwargs.get('hub.challenge')

        _logger.info(f"Webhook verification request: mode={mode}")

        # Get stored verify token
        verify_token = request.env['ir.config_parameter'].sudo().get_param(
            'clinic.whatsapp.webhook_verify_token'
        )

        if not verify_token:
            _logger.error("❌ Verify token not configured in Settings")
            return request.make_response('Configuration error', status=500)

        if mode == 'subscribe' and token == verify_token:
            _logger.info("✅ WhatsApp webhook verified successfully")
            return challenge
        else:
            _logger.warning(
                f"❌ Webhook verification failed: mode={mode}, "
                f"token_match={token == verify_token if verify_token else False}"
            )
            return request.make_response('Verification failed', status=403)

    @http.route('/whatsapp/webhook', type='http', auth='none', methods=['POST'], csrf=False)
    def webhook_receive(self, **kwargs):
        """
        Webhook for incoming messages and status updates

        🔒 SECURITY: Validates X-Hub-Signature-256 BEFORE processing
        This prevents webhook forgery attacks.

        Reference: https://developers.facebook.com/docs/graph-api/webhooks/getting-started#verification-requests

        Payload structure:
        {
          "entry": [{
            "changes": [{
              "value": {
                "messages": [...],  // Incoming messages
                "statuses": [...],  // Status updates (sent/delivered/read)
              }
            }]
          }]
        }
        """
        try:
            # 🔒 CRITICAL: Get signature BEFORE parsing
            signature = request.httprequest.headers.get('X-Hub-Signature-256')
            payload_bytes = request.httprequest.get_data()  # Raw bytes

            if not payload_bytes:
                _logger.warning("⚠️ Empty webhook payload received")
                return request.make_response('No data', status=200)

            # 🔒 CRITICAL: Verify signature
            if not self._verify_signature(payload_bytes, signature):
                _logger.error(
                    "❌ Invalid webhook signature - possible attack attempt!\n"
                    f"IP: {request.httprequest.remote_addr}\n"
                    f"Headers: {dict(request.httprequest.headers)}"
                )
                return request.make_response('Forbidden', status=403)

            # Signature is valid - NOW parse JSON
            payload = json.loads(payload_bytes)

            # Log webhook (useful for debugging)
            _logger.info(f"✅ Valid webhook received from {request.httprequest.remote_addr}")
            _logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

            # Process entries
            for entry in payload.get('entry', []):
                for change in entry.get('changes', []):
                    value = change.get('value', {})

                    # Process incoming messages
                    if 'messages' in value:
                        for message in value['messages']:
                            self._handle_incoming_message(message, value.get('metadata', {}))

                    # Process status updates
                    if 'statuses' in value:
                        for status in value['statuses']:
                            self._handle_status_update(status)

            # Always return 200 to Meta (otherwise they retry)
            return request.make_response('OK', status=200)

        except json.JSONDecodeError as e:
            _logger.error(f"❌ Invalid JSON in webhook: {e}")
            return request.make_response('Invalid JSON', status=400)
        except Exception as e:
            _logger.error(f"❌ Error processing webhook: {e}", exc_info=True)
            # Return 200 to prevent Meta retries (we logged the error)
            return request.make_response('OK', status=200)

    def _verify_signature(self, payload, signature):
        """
        Verify Meta webhook signature using HMAC-SHA256

        Security: Prevents webhook forgery attacks
        Uses constant-time comparison to prevent timing attacks

        Reference: https://developers.facebook.com/docs/graph-api/webhooks/getting-started#verification-requests

        Args:
            payload (bytes): Raw request body
            signature (str): X-Hub-Signature-256 header value

        Returns:
            bool: True if signature is valid
        """
        if not signature:
            _logger.error("❌ Missing X-Hub-Signature-256 header")
            return False

        app_secret = request.env['ir.config_parameter'].sudo().get_param(
            'clinic.whatsapp.app_secret'
        )

        if not app_secret:
            _logger.warning(
                "⚠️ App secret not configured - SKIPPING SIGNATURE VERIFICATION\n"
                "🔴 THIS IS UNSAFE FOR PRODUCTION!\n"
                "Configure app_secret in Settings > WhatsApp Configuration"
            )
            # Only allow in development (remove in production)
            return True  # TODO: Change to False for production

        # Compute expected signature
        expected_signature = 'sha256=' + hmac.new(
            app_secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        # Constant-time comparison (prevents timing attacks)
        is_valid = hmac.compare_digest(expected_signature, signature)

        if not is_valid:
            _logger.error(
                f"❌ Signature mismatch\n"
                f"Expected: {expected_signature[:20]}...\n"
                f"Received: {signature[:20] if signature else 'None'}..."
            )

        return is_valid

    def _handle_incoming_message(self, message_data, metadata):
        """
        Process incoming message from customer

        🔄 IDEMPOTENT: Uses message_id to prevent duplicate processing

        Args:
            message_data (dict): Message data from Meta
            metadata (dict): Metadata (phone_number_id, etc.)
        """
        try:
            message_id = message_data.get('id')
            from_number = message_data.get('from')
            timestamp = int(message_data.get('timestamp', 0))
            message_type = message_data.get('type', 'text')

            _logger.info(f"📥 Incoming message: {message_id} from {from_number}")

            # Get message handler
            WhatsAppMessage = request.env['clinic.whatsapp.message'].sudo()

            # Delegate to message model (handles idempotency)
            WhatsAppMessage.handle_incoming_webhook(message_data, metadata)

        except Exception as e:
            _logger.error(f"❌ Error handling incoming message: {e}", exc_info=True)

    def _handle_status_update(self, status_data):
        """
        Process status update for sent message

        🔄 IDEMPOTENT: Uses status id to prevent duplicate processing

        Status progression: sent → delivered → read
        Or: sent → failed

        Args:
            status_data (dict): Status data from Meta
        """
        try:
            message_id = status_data.get('id')
            status = status_data.get('status')

            _logger.info(f"📊 Status update: {message_id} → {status}")

            # Get message handler
            WhatsAppMessage = request.env['clinic.whatsapp.message'].sudo()

            # Delegate to message model (handles idempotency)
            WhatsAppMessage.handle_status_webhook(status_data)

        except Exception as e:
            _logger.error(f"❌ Error handling status update: {e}", exc_info=True)
