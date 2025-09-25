# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import secrets
import hashlib
import jwt
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class ApiKey(models.Model):
    _name = 'clinic.api.key'
    _description = 'API Key Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    
    name = fields.Char(
        string='Name',
        required=True,
        tracking=True
    )
    
    key = fields.Char(
        string='API Key',
        readonly=True,
        copy=False,
        tracking=True
    )
    
    key_hash = fields.Char(
        string='Key Hash',
        readonly=True,
        copy=False
    )
    
    secret = fields.Char(
        string='Secret Key',
        readonly=True,
        copy=False
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        tracking=True
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True
    )
    
    # Permissions
    scope = fields.Selection([
        ('read', 'Read Only'),
        ('write', 'Read/Write'),
        ('full', 'Full Access'),
    ], string='Scope', default='read', required=True, tracking=True)
    
    allowed_models = fields.Text(
        string='Allowed Models',
        help='Comma-separated list of model names this key can access'
    )
    
    allowed_ips = fields.Text(
        string='Allowed IPs',
        help='Comma-separated list of IP addresses that can use this key'
    )
    
    # Rate Limiting
    rate_limit = fields.Integer(
        string='Rate Limit (per hour)',
        default=1000,
        tracking=True
    )
    
    # Validity
    valid_from = fields.Datetime(
        string='Valid From',
        default=fields.Datetime.now,
        required=True,
        tracking=True
    )
    
    valid_until = fields.Datetime(
        string='Valid Until',
        tracking=True
    )
    
    is_valid = fields.Boolean(
        string='Is Valid',
        compute='_compute_is_valid',
        store=True
    )
    
    # Usage Statistics
    last_used = fields.Datetime(
        string='Last Used',
        readonly=True
    )
    
    usage_count = fields.Integer(
        string='Usage Count',
        readonly=True,
        default=0
    )
    
    # JWT Settings
    jwt_algorithm = fields.Selection([
        ('HS256', 'HS256'),
        ('HS384', 'HS384'),
        ('HS512', 'HS512'),
        ('RS256', 'RS256'),
    ], string='JWT Algorithm', default='HS512', required=True)  # Changed default to stronger HS512

    jwt_expiry_minutes = fields.Integer(
        string='JWT Expiry (minutes)',
        default=30,  # Reduced from 60 to 30 minutes for better security
        required=True,
        help='JWT tokens expire after this many minutes'
    )

    # Additional security fields
    refresh_token_enabled = fields.Boolean(
        string='Enable Refresh Tokens',
        default=True,
        help='Allow refresh tokens for extending sessions'
    )

    max_refresh_count = fields.Integer(
        string='Max Refresh Count',
        default=3,
        help='Maximum number of times a token can be refreshed'
    )

    require_jti = fields.Boolean(
        string='Require JWT ID (jti)',
        default=True,
        help='Require unique JWT ID to prevent replay attacks'
    )
    
    @api.depends('valid_from', 'valid_until', 'active')
    def _compute_is_valid(self):
        now = fields.Datetime.now()
        for key in self:
            key.is_valid = (
                key.active and
                key.valid_from <= now and
                (not key.valid_until or key.valid_until >= now)
            )
    
    @api.model
    def create(self, vals):
        # Generate API key and secret
        api_key = self._generate_api_key()
        secret_key = self._generate_secret_key()
        
        vals['key'] = api_key
        vals['key_hash'] = self._hash_key(api_key)
        vals['secret'] = secret_key
        
        return super().create(vals)
    
    def _generate_api_key(self):
        """Generate a unique API key"""
        return 'ck_' + secrets.token_urlsafe(32)
    
    def _generate_secret_key(self):
        """Generate a secret key for JWT signing"""
        return 'cs_' + secrets.token_urlsafe(48)
    
    def _hash_key(self, key):
        """Hash the API key for storage"""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def action_regenerate_key(self):
        """Regenerate API key"""
        self.ensure_one()
        
        new_key = self._generate_api_key()
        new_secret = self._generate_secret_key()
        
        self.write({
            'key': new_key,
            'key_hash': self._hash_key(new_key),
            'secret': new_secret,
            'usage_count': 0,
        })
        
        # Log the regeneration
        self.message_post(
            body=_("API key regenerated"),
            subject="Key Regeneration"
        )
        
        return True
    
    def action_revoke(self):
        """Revoke API key"""
        self.ensure_one()
        self.active = False
        
        self.message_post(
            body=_("API key revoked"),
            subject="Key Revocation"
        )
        
        return True
    
    def generate_jwt_token(self, payload=None, is_refresh=False):
        """Generate JWT token with enhanced security"""
        self.ensure_one()

        if not self.is_valid:
            raise ValidationError(_("API key is not valid"))

        now = datetime.utcnow()
        expiry = now + timedelta(minutes=self.jwt_expiry_minutes)

        # Generate unique JWT ID to prevent replay attacks
        jti = secrets.token_urlsafe(32) if self.require_jti else None

        token_payload = {
            'iss': 'clinic_api',  # Issuer
            'sub': self.user_id.login,  # Subject
            'aud': 'clinic_system',  # Audience
            'iat': now,  # Issued at
            'exp': expiry,  # Expiry
            'nbf': now,  # Not before
            'api_key_id': self.id,
            'scope': self.scope,
            'user_id': self.user_id.id,
            'token_type': 'refresh' if is_refresh else 'access',
        }

        if jti:
            token_payload['jti'] = jti
            # Store JTI in cache to track used tokens
            self._store_jti(jti, expiry)

        if is_refresh and self.refresh_token_enabled:
            # Extend expiry for refresh tokens
            token_payload['exp'] = now + timedelta(days=7)
            token_payload['refresh_count'] = 0
            token_payload['max_refresh'] = self.max_refresh_count

        if payload:
            # Sanitize custom payload to prevent injection
            safe_payload = {k: v for k, v in payload.items()
                          if k not in token_payload and isinstance(v, (str, int, float, bool))}
            token_payload.update(safe_payload)

        token = jwt.encode(
            token_payload,
            self.secret,
            algorithm=self.jwt_algorithm
        )

        # Log token generation for audit
        self.env['clinic.api.log'].sudo().create({
            'api_key_id': self.id,
            'action': 'token_generated',
            'details': f'Token type: {token_payload.get("token_type")}',
            'timestamp': fields.Datetime.now(),
        })

        return token
    
    def verify_jwt_token(self, token, expected_type='access'):
        """Verify JWT token with enhanced security checks"""
        self.ensure_one()

        try:
            # Decode with audience verification
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.jwt_algorithm],
                audience='clinic_system',  # Verify audience claim
                issuer='clinic_api',  # Verify issuer claim
            )

            # Verify token type
            if payload.get('token_type') != expected_type:
                raise ValidationError(_("Invalid token type. Expected %s, got %s") %
                                    (expected_type, payload.get('token_type')))

            # Verify API key ID matches
            if payload.get('api_key_id') != self.id:
                raise ValidationError(_("Token does not belong to this API key"))

            # Check JTI for replay attacks
            if self.require_jti:
                jti = payload.get('jti')
                if not jti or not self._verify_jti(jti):
                    raise ValidationError(_("Invalid or replayed token (jti check failed)"))

            # Verify user still exists and is active
            user = self.env['res.users'].browse(payload.get('user_id'))
            if not user.exists() or not user.active:
                raise ValidationError(_("User account is no longer valid"))

            # Update usage statistics
            self.sudo().write({
                'last_used': fields.Datetime.now(),
                'usage_count': self.usage_count + 1,
            })

            # Log successful verification
            self.env['clinic.api.log'].sudo().create({
                'api_key_id': self.id,
                'action': 'token_verified',
                'details': f'Token type: {expected_type}',
                'timestamp': fields.Datetime.now(),
            })

            return payload

        except jwt.ExpiredSignatureError:
            _logger.warning(f"Expired token for API key {self.id}")
            raise ValidationError(_("Token has expired"))
        except jwt.InvalidAudienceError:
            _logger.warning(f"Invalid audience for API key {self.id}")
            raise ValidationError(_("Invalid token audience"))
        except jwt.InvalidIssuerError:
            _logger.warning(f"Invalid issuer for API key {self.id}")
            raise ValidationError(_("Invalid token issuer"))
        except jwt.InvalidTokenError as e:
            _logger.warning(f"Invalid token for API key {self.id}: {str(e)}")
            raise ValidationError(_("Invalid token: %s") % str(e))
    
    def check_rate_limit(self, ip_address=None):
        """Check if rate limit is exceeded"""
        self.ensure_one()
        
        # Check IP restriction
        if self.allowed_ips and ip_address:
            allowed_ips = [ip.strip() for ip in self.allowed_ips.split(',')]
            if ip_address not in allowed_ips:
                raise ValidationError(_("IP address not allowed"))
        
        # Check rate limit
        hour_ago = fields.Datetime.now() - timedelta(hours=1)
        recent_logs = self.env['clinic.api.log'].search_count([
            ('api_key_id', '=', self.id),
            ('timestamp', '>=', hour_ago),
        ])
        
        if recent_logs >= self.rate_limit:
            raise ValidationError(_("Rate limit exceeded"))
        
        return True
    
    def _store_jti(self, jti, expiry):
        """Store JWT ID in database to prevent replay attacks"""
        self.env['clinic.api.jwt_blacklist'].sudo().create({
            'jti': jti,
            'api_key_id': self.id,
            'expiry': expiry,
        })

    def _verify_jti(self, jti):
        """Verify JWT ID hasn't been used (replay attack prevention)"""
        # Check if JTI is in blacklist (already used)
        blacklisted = self.env['clinic.api.jwt_blacklist'].sudo().search_count([
            ('jti', '=', jti),
            ('api_key_id', '=', self.id),
        ])
        return blacklisted == 0

    def refresh_token(self, refresh_token):
        """Generate new access token from refresh token"""
        self.ensure_one()

        if not self.refresh_token_enabled:
            raise ValidationError(_("Refresh tokens are not enabled for this API key"))

        # Verify refresh token
        payload = self.verify_jwt_token(refresh_token, expected_type='refresh')

        # Check refresh count
        refresh_count = payload.get('refresh_count', 0)
        max_refresh = payload.get('max_refresh', self.max_refresh_count)

        if refresh_count >= max_refresh:
            raise ValidationError(_("Maximum refresh count exceeded"))

        # Generate new access token with incremented refresh count
        new_payload = {
            'refresh_count': refresh_count + 1,
            'original_iat': payload.get('iat'),
        }

        return self.generate_jwt_token(new_payload)

    @api.model
    def authenticate(self, api_key, ip_address=None):
        """Authenticate using API key with IP verification"""
        # Constant-time comparison to prevent timing attacks
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        api_key_record = self.search([
            ('key_hash', '=', key_hash),
            ('is_valid', '=', True),
        ], limit=1)

        if not api_key_record:
            # Log failed authentication attempt
            _logger.warning(f"Failed authentication attempt with invalid API key from IP {ip_address}")
            return False

        # Check IP restrictions if provided
        if ip_address:
            try:
                api_key_record.check_rate_limit(ip_address)
            except ValidationError:
                _logger.warning(f"Authentication blocked for API key {api_key_record.id} from IP {ip_address}")
                return False

        return api_key_record

    @api.model
    def cleanup_expired_tokens(self):
        """Cleanup expired JTI entries (can be called by cron)"""
        expired = self.env['clinic.api.jwt_blacklist'].search([
            ('expiry', '<', datetime.utcnow())
        ])
        expired.unlink()
        _logger.info(f"Cleaned up {len(expired)} expired JWT blacklist entries")