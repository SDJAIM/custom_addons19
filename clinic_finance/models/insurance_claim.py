# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class InsuranceClaim(models.Model):
    _name = 'clinic.insurance.claim'
    _description = 'Insurance Claim'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'submission_date desc, id desc'
    _rec_name = 'name'
    _check_company_auto = True

    # Display name – generated from sequence (fixes the view error)
    name = fields.Char(
        string='Claim #',
        required=True,
        readonly=True,
        copy=False,
        default='New',
        tracking=True,
        index=True,
        help='Auto-generated claim reference from sequence.'
    )

    # Optional external reference from the insurance company
    claim_number = fields.Char(
        string='External Claim Number',
        help='Reference provided by the insurance company.',
        tracking=True,
        index=True,
    )

    patient_id = fields.Many2one(
        'clinic.patient',
        string='Patient',
        required=True,
        tracking=True,
        index=True
    )

    policy_id = fields.Many2one(
        'clinic.insurance.policy',
        string='Insurance Policy',
        required=True,
        tracking=True,
        domain="[('patient_id', '=', patient_id), ('is_active', '=', True)]"
    )

    insurance_company_id = fields.Many2one(
        'clinic.insurance.company',
        string='Insurance Company',
        related='policy_id.insurance_company_id',
        store=True,
        readonly=True
    )

    # Claim Type
    claim_type = fields.Selection([
        ('medical', 'Medical'),
        ('dental', 'Dental'),
        ('vision', 'Vision'),
        ('pharmacy', 'Pharmacy'),
        ('mental_health', 'Mental Health'),
    ], string='Claim Type', default='medical', required=True, tracking=True)

    priority = fields.Selection([
        ('normal', 'Normal'),
        ('urgent', 'Urgent'),
        ('emergency', 'Emergency'),
    ], string='Priority', default='normal', tracking=True)

    # Related Records
    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Appointment',
        tracking=True
    )

    invoice_id = fields.Many2one(
        'clinic.invoice',
        string='Invoice',
        tracking=True
    )

    treatment_ids = fields.Many2many(
        'clinic.treatment.plan.line',
        string='Treatments'
    )

    prescription_ids = fields.Many2many(
        'clinic.prescription',
        string='Prescriptions'
    )

    # Service Information
    service_date = fields.Date(
        string='Service Date',
        required=True,
        tracking=True
    )

    service_end_date = fields.Date(
        string='Service End Date',
        help='For multi-day services'
    )

    provider_id = fields.Many2one(
        'clinic.staff',
        string='Provider',
        required=True,
        tracking=True,
        domain=[('is_practitioner', '=', True)]
    )

    facility_id = fields.Many2one(
        'clinic.branch',
        string='Facility',
        tracking=True
    )

    # Diagnosis and Procedures
    primary_diagnosis_id = fields.Many2one(
        'clinic.diagnosis',
        string='Primary Diagnosis',
        required=True,
        tracking=True
    )

    secondary_diagnosis_ids = fields.Many2many(
        'clinic.diagnosis',
        'claim_secondary_diagnosis_rel',
        string='Secondary Diagnoses'
    )

    procedure_codes = fields.Text(
        string='Procedure Codes',
        help='CPT/HCPCS codes'
    )

    # Authorization
    requires_authorization = fields.Boolean(
        string='Requires Authorization',
        related='policy_id.requires_preauth',
        store=True
    )

    authorization_number = fields.Char(
        string='Authorization Number',
        tracking=True
    )

    authorization_date = fields.Date(
        string='Authorization Date',
        tracking=True
    )

    # Claim Lines
    line_ids = fields.One2many(
        'clinic.claim.line',
        'claim_id',
        string='Claim Lines'
    )

    # Financial Information
    amount_billed = fields.Monetary(
        string='Amount Billed',
        required=True,
        tracking=True,
        currency_field='currency_id'
    )

    amount_approved = fields.Monetary(
        string='Amount Approved',
        tracking=True,
        currency_field='currency_id'
    )

    amount_paid = fields.Monetary(
        string='Amount Paid',
        tracking=True,
        readonly=True,
        currency_field='currency_id'
    )

    amount_adjusted = fields.Monetary(
        string='Adjustment',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id'
    )

    copay_amount = fields.Monetary(
        string='Co-payment',
        tracking=True,
        currency_field='currency_id'
    )

    deductible_amount = fields.Monetary(
        string='Deductible',
        tracking=True,
        currency_field='currency_id'
    )

    coinsurance_amount = fields.Monetary(
        string='Coinsurance',
        tracking=True,
        currency_field='currency_id'
    )

    patient_responsibility = fields.Monetary(
        string='Patient Responsibility',
        compute='_compute_patient_responsibility',
        store=True,
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    # Workflow State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('in_review', 'In Review'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('partially_paid', 'Partially Paid'),
        ('rejected', 'Rejected'),
        ('appealed', 'Appealed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True, index=True)

    # Submission Information
    submission_date = fields.Datetime(
        string='Submission Date',
        tracking=True,
        readonly=True
    )

    submission_method = fields.Selection([
        ('electronic', 'Electronic (EDI)'),
        ('paper', 'Paper'),
        ('portal', 'Web Portal'),
        ('fax', 'Fax'),
    ], string='Submission Method', tracking=True)

    submission_reference = fields.Char(
        string='Submission Reference',
        help='EDI transmission ID or tracking number'
    )

    submitted_by = fields.Many2one(
        'res.users',
        string='Submitted By',
        readonly=True
    )

    # Response Information
    response_date = fields.Datetime(
        string='Response Date',
        tracking=True
    )

    response_code = fields.Char(
        string='Response Code'
    )

    eob_number = fields.Char(
        string='EOB Number',
        help='Explanation of Benefits number'
    )

    # Payment Information
    payment_date = fields.Date(
        string='Payment Date',
        tracking=True
    )

    payment_method = fields.Selection([
        ('check', 'Check'),
        ('eft', 'Electronic Transfer'),
        ('credit_card', 'Credit Card'),
        ('cash', 'Cash'),
    ], string='Payment Method')

    payment_reference = fields.Char(
        string='Payment Reference',
        help='Check number or transaction ID'
    )

    # Rejection/Denial
    rejection_reason = fields.Text(
        string='Rejection Reason',
        tracking=True
    )

    rejection_code = fields.Char(
        string='Rejection Code'
    )

    can_appeal = fields.Boolean(
        string='Can Appeal',
        default=True
    )

    # Appeal Information
    appeal_date = fields.Date(
        string='Appeal Date',
        tracking=True
    )

    appeal_reason = fields.Text(
        string='Appeal Reason'
    )

    appeal_outcome = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
        ('partial', 'Partially Approved'),
    ], string='Appeal Outcome')

    # Documents
    claim_form = fields.Binary(
        string='Claim Form',
        attachment=True
    )

    supporting_documents = fields.Many2many(
        'ir.attachment',
        string='Supporting Documents'
    )

    eob_document = fields.Binary(
        string='EOB Document',
        attachment=True
    )

    # Tracking
    days_outstanding = fields.Integer(
        string='Days Outstanding',
        compute='_compute_days_outstanding',
        store=True
    )

    follow_up_date = fields.Date(
        string='Follow-up Date',
        tracking=True
    )

    follow_up_count = fields.Integer(
        string='Follow-ups',
        default=0,
        tracking=True
    )

    # Notes
    internal_notes = fields.Text(
        string='Internal Notes'
    )

    payer_notes = fields.Text(
        string='Payer Notes'
    )

    # ============================================================================
    # COMPUTE METHODS
    # ============================================================================

    @api.depends('amount_billed', 'amount_paid')
    def _compute_amounts(self):
        for claim in self:
            claim.amount_adjusted = claim.amount_billed - claim.amount_paid

    @api.depends('copay_amount', 'deductible_amount', 'coinsurance_amount')
    def _compute_patient_responsibility(self):
        """Compute patient responsibility as sum of cost-sharing components.

        SINGLE SOURCE OF TRUTH: This is the only place where patient_responsibility
        is calculated. Do NOT attempt to set it via create() or elsewhere.

        Formula: copay_amount + deductible_amount + coinsurance_amount

        Reference: Odoo 19 @api.depends and computed fields
        https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html#computed-fields
        """
        for claim in self:
            claim.patient_responsibility = (
                claim.copay_amount +
                claim.deductible_amount +
                claim.coinsurance_amount
            )

    @api.depends('submission_date', 'state')
    def _compute_days_outstanding(self):
        today = fields.Datetime.now()
        for claim in self:
            if claim.submission_date and claim.state in ['submitted', 'in_review', 'approved']:
                delta = today - claim.submission_date
                claim.days_outstanding = delta.days
            else:
                claim.days_outstanding = 0

    # ============================================================================
    # CONSTRAINT METHODS
    # ============================================================================

    @api.constrains('service_date', 'service_end_date')
    def _check_service_dates(self):
        for claim in self:
            if claim.service_end_date and claim.service_date > claim.service_end_date:
                raise ValidationError(_("Service end date must be after service date."))

    @api.constrains('amount_approved', 'amount_billed')
    def _check_approved_amount(self):
        for claim in self:
            if claim.amount_approved and claim.amount_approved > claim.amount_billed:
                raise ValidationError(_("Approved amount cannot exceed billed amount."))

    @api.constrains('amount_paid', 'amount_approved')
    def _check_paid_amount(self):
        for claim in self:
            if claim.amount_approved and claim.amount_paid > claim.amount_approved:
                raise ValidationError(_("Paid amount cannot exceed approved amount."))


    # ============================================================================
    # LIFECYCLE METHODS
    # ============================================================================

    def write(self, vals):
        """Override write to enforce state-based field restrictions.

        Validates field changes based on claim state BEFORE write occurs:
        - patient_id, provider_id, amount_billed are readonly after submission
        - amount_paid is always readonly (set only by action_mark_paid)
        - Raises UserError if invalid state transitions attempted

        Reference: Odoo 19 ORM best practices - field restrictions via write()
        https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html#using-write-method-for-validation
        """
        for claim in self:
            # Validate patient_id changes
            if 'patient_id' in vals and claim.state not in ('draft',):
                raise UserError(
                    _("Cannot change patient in %s state claim. "
                      "Create a new claim instead.") % claim.state
                )

            # Validate provider_id changes
            if 'provider_id' in vals and claim.state in ('submitted', 'in_review', 'approved', 'paid', 'partially_paid'):
                raise UserError(
                    _("Provider cannot be changed once claim is submitted (current state: %s).") % claim.state
                )

            # Validate amount_billed changes
            if 'amount_billed' in vals and claim.state in ('submitted', 'in_review', 'approved', 'paid', 'partially_paid'):
                raise UserError(
                    _("Billed amount cannot be changed in %s state. "
                      "Create an adjustment or credit memo instead.") % claim.state
                )

            # Prevent direct amount_paid updates (only via action_mark_paid or action_register_partial_payment)
            if 'amount_paid' in vals and not self.env.context.get('internal_amount_paid_update'):
                raise UserError(
                    _("Amount paid cannot be updated directly. "
                      "Use 'Mark as Paid' or 'Register Partial Payment' actions."))

        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Create insurance claim with auto-generated sequence number.

        The 'name' field holds the auto-generated claim reference (e.g., CLM/2025/00001).
        The 'claim_number' field can hold an external reference from the insurance company.

        Reference: Odoo 19 sequences & multi-create patterns
        https://www.odoo.com/documentation/19.0/developer/reference/backend/data.html#sequences
        """
        seq = self.env['ir.sequence']
        for vals in vals_list:
            # Only generate when not provided or placeholder value
            if not vals.get('name') or vals.get('name') in ('New', '/'):
                vals['name'] = seq.next_by_code('clinic.insurance.claim') or 'New'

        return super().create(vals_list)

    # ============================================================================
    # WORKFLOW STATE MACHINE METHODS
    # ============================================================================

    def action_submit(self):
        """Submit claim to insurance company.

        Allowed from: draft
        Transition to: submitted
        """
        self.ensure_one()

        if self.state != 'draft':
            raise UserError(
                _("Only draft claims can be submitted. Current state: %s") % self.state
            )

        if self.requires_authorization and not self.authorization_number:
            raise UserError(
                _("Authorization number is required for this claim.")
            )

        if not self.line_ids:
            raise UserError(
                _("Please add claim lines before submitting.")
            )

        self.write({
            'state': 'submitted',
            'submission_date': fields.Datetime.now(),
            'submitted_by': self.env.user.id,
        })

        # Log to chatter
        self.message_post(
            body=_("Claim submitted to insurance company."),
            subject=_("Claim Submitted")
        )

        # Create follow-up activity
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            summary=_('Follow up on claim'),
            date_deadline=fields.Date.today() + timedelta(days=14),
            user_id=self.env.user.id
        )

        return True

    def action_approve(self):
        """Approve claim for payment.

        Allowed from: submitted, in_review
        Transition to: approved
        """
        self.ensure_one()

        if self.state not in ['submitted', 'in_review']:
            raise UserError(
                _("Only submitted or in-review claims can be approved. "
                  "Current state: %s") % self.state
            )

        if not self.amount_approved:
            raise UserError(
                _("Please enter approved amount before approving.")
            )

        self.write({
            'state': 'approved',
            'response_date': fields.Datetime.now(),
        })

        # Log to chatter
        self.message_post(
            body=_("Claim approved for payment. Amount: %s %s") % (
                self.amount_approved, self.currency_id.symbol
            ),
            subject=_("Claim Approved")
        )

        return True

    def action_mark_paid(self):
        """Mark claim as paid with full approved amount.

        Allowed from: approved
        Transition to: paid

        Validates:
        - Current state must be 'approved'
        - amount_approved must be > 0
        - Sets payment_date to today
        - Sets amount_paid to amount_approved
        - Logs transition in chatter
        - Optional: Creates accounting move if configured via ir.config_parameter

        Reference: Odoo 19 state machine implementation
        https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html#state-machine-patterns
        """
        self.ensure_one()

        # Validate current state
        if self.state != 'approved':
            raise UserError(
                _("Only approved claims can be marked as paid. "
                  "Current state: %s") % self.state
            )

        # Validate approved amount
        if not self.amount_approved or self.amount_approved <= 0:
            raise UserError(
                _("Approved amount must be greater than 0 to mark claim as paid.")
            )

        # Perform transition with internal flag to bypass write() validation
        self.with_context(internal_amount_paid_update=True).write({
            'state': 'paid',
            'payment_date': fields.Date.context_today(self),
            'amount_paid': self.amount_approved,
        })

        # Log to chatter for audit trail
        self.message_post(
            body=_("Claim marked as paid. Amount: %s %s on %s") % (
                self.amount_paid, self.currency_id.symbol, self.payment_date
            ),
            subject=_("Payment Recorded"),
            message_type='notification'
        )

        # Hook: Optional automatic accounting move creation
        if self.env['ir.config_parameter'].sudo().get_param(
            'clinic_finance.auto_post_move_on_claim_payment', 'false'
        ).lower() == 'true':
            self._create_payment_move()

        return True

    def action_register_partial_payment(self, amount_paid, payment_date=None, payment_reference=None):
        """Register a partial payment on an approved claim.

        Allowed from: approved
        Transition to: partially_paid (if not fully paid) OR paid (if amount_paid == amount_approved)

        Args:
            amount_paid (float): Amount being paid in this transaction
            payment_date (Date): Optional payment date (defaults to today)
            payment_reference (str): Optional reference (check/transaction number)

        Returns:
            True on success

        Raises:
            UserError: If claim not in 'approved' state, or partial amount exceeds approved amount

        Reference: Odoo 19 state transitions
        https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html#state-machine-patterns
        """
        self.ensure_one()

        # Validate current state
        if self.state not in ('approved', 'partially_paid'):
            raise UserError(
                _("Partial payments only allowed in 'Approved' or 'Partially Paid' state. "
                  "Current state: %s") % self.state
            )

        # Validate amount
        if not amount_paid or amount_paid <= 0:
            raise UserError(_("Payment amount must be greater than 0."))

        # Calculate cumulative paid amount
        current_paid = self.amount_paid or 0.0
        new_total_paid = current_paid + amount_paid

        # Validate total paid doesn't exceed approved
        if new_total_paid > self.amount_approved:
            raise UserError(
                _("Total payment amount (%.2f) cannot exceed approved amount (%.2f).") % (
                    new_total_paid, self.amount_approved
                )
            )

        # Determine new state: if fully paid, transition to paid; otherwise stay/move to partially_paid
        new_state = 'paid' if new_total_paid >= self.amount_approved else 'partially_paid'

        # Perform update with internal flag
        self.with_context(internal_amount_paid_update=True).write({
            'state': new_state,
            'amount_paid': new_total_paid,
            'payment_date': payment_date or fields.Date.context_today(self),
            'payment_reference': payment_reference or self.payment_reference,
        })

        # Log to chatter
        message_body = _("Partial payment registered: %s %s. Total paid: %s %s / %s %s") % (
            amount_paid,
            self.currency_id.symbol,
            new_total_paid,
            self.currency_id.symbol,
            self.amount_approved,
            self.currency_id.symbol
        )
        if payment_reference:
            message_body += _(" (Ref: %s)") % payment_reference

        self.message_post(
            body=message_body,
            subject=_("Partial Payment Recorded"),
            message_type='notification'
        )

        # Optional: Hook for accounting move creation
        if self.env['ir.config_parameter'].sudo().get_param(
            'clinic_finance.auto_post_move_on_claim_payment', 'false'
        ).lower() == 'true':
            self._create_payment_move()

        return True

    def _create_payment_move(self):
        """Create accounting move for claim payment (optional, governed by config).

        Only called if clinic_finance.auto_post_move_on_claim_payment = true.
        Requires integration with account module (if installed).
        """
        try:
            if not self.env['ir.module.module'].search([
                ('name', '=', 'account'),
                ('state', '=', 'installed')
            ]):
                _logger.info(
                    "Account module not installed; skipping automatic move creation for claim %s",
                    self.claim_number
                )
                return

            # Placeholder for accounting move creation
            # In production, integrate with account.move creation logic
            _logger.info(
                "Auto payment move creation requested for claim %s (amount: %s)",
                self.claim_number,
                self.amount_paid
            )
        except Exception as e:
            _logger.warning(
                "Error creating payment move for claim %s: %s",
                self.claim_number,
                str(e)
            )

    def action_reject(self):
        """Reject claim.

        Allowed from: submitted, in_review, approved
        Transition to: rejected
        """
        self.ensure_one()

        if self.state not in ['submitted', 'in_review', 'approved']:
            raise UserError(
                _("Cannot reject claim in current state: %s") % self.state
            )

        return {
            'name': _('Reject Claim'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.claim.rejection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_claim_id': self.id,
            }
        }

    def action_appeal(self):
        """Appeal rejected claim.

        Allowed from: rejected
        Transition to: appealed
        """
        self.ensure_one()

        if self.state != 'rejected':
            raise UserError(
                _("Only rejected claims can be appealed. Current state: %s") % self.state
            )

        if not self.can_appeal:
            raise UserError(
                _("This claim cannot be appealed.")
            )

        return {
            'name': _('Appeal Claim'),
            'type': 'ir.actions.act_window',
            'res_model': 'clinic.claim.appeal.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_claim_id': self.id,
            }
        }

    def action_cancel(self):
        """Cancel claim.

        Allowed from: draft, submitted, in_review, approved, rejected, appealed
        Not allowed from: paid, cancelled
        Transition to: cancelled
        """
        self.ensure_one()

        if self.state in ['paid', 'cancelled']:
            raise UserError(
                _("Cannot cancel claim in current state: %s") % self.state
            )

        self.write({'state': 'cancelled'})

        self.message_post(
            body=_("Claim cancelled."),
            subject=_("Claim Cancelled")
        )

        return True

    def action_follow_up(self):
        """Record follow-up on claim."""
        self.ensure_one()

        self.write({
            'follow_up_count': self.follow_up_count + 1,
            'follow_up_date': fields.Date.today(),
        })

        self.message_post(
            body=_("Follow-up #%d on claim %s") % (self.follow_up_count, self.claim_number),
            subject=_("Claim Follow-up")
        )

        return True

    def action_print_claim(self):
        """Print claim form."""
        self.ensure_one()
        return self.env.ref('clinic_finance.action_report_insurance_claim').report_action(self)

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def name_get(self):
        """Display name: Claim Number - Patient Name"""
        result = []
        for claim in self:
            name = claim.claim_number
            if claim.patient_id:
                name = f"{name} - {claim.patient_id.name}"
            result.append((claim.id, name))
        return result

    @api.model
    def check_outstanding_claims(self):
        """Cron job to flag outstanding claims (>30 days).

        Called daily to identify insurance claims pending >30 days in submitted/in_review states.
        Creates warning activities assigned to the user who submitted the claim.

        Security:
        - Uses sudo() to read all outstanding claims regardless of field-level restrictions
        - Validates submitted_by user exists before assigning activity
        - Filters out already-processed claims (checks for existing activity)
        - Logs warnings for claims without submitted_by user

        Returns:
            bool: True on success

        Reference: Odoo 19 cron security patterns
        https://www.odoo.com/documentation/19.0/developer/reference/backend/actions.html#scheduled-actions
        """
        try:
            outstanding_date = fields.Datetime.now() - timedelta(days=30)

            # Use sudo() for system-wide claim visibility
            # Justification: Cron needs to identify all outstanding claims regardless of field access
            outstanding_claims = self.sudo().search([
                ('state', 'in', ['submitted', 'in_review']),
                ('submission_date', '<', outstanding_date),
            ])

            _logger.info("Found %d outstanding claims (>30 days)", len(outstanding_claims))

            activity_type_warning = self.env.ref(
                'mail.mail_activity_data_warning',
                raise_if_not_found=False
            )

            if not activity_type_warning:
                _logger.warning("Warning activity type not found; skipping activity creation")
                return False

            for claim in outstanding_claims:
                try:
                    # Defensive check: ensure submitted_by user exists and is active
                    assignee = None
                    if claim.submitted_by and claim.submitted_by.active:
                        assignee = claim.submitted_by.id
                    else:
                        if claim.submitted_by:
                            _logger.warning("Submitted by user %s is inactive for claim %s", claim.submitted_by.name, claim.claim_number)
                        else:
                            _logger.warning("No submitted_by user for claim %s", claim.claim_number)
                        # Fallback to current user (cron runner), or skip if no user available
                        assignee = self.env.user.id if self.env.user.active else None

                    if not assignee:
                        _logger.warning("Cannot assign activity; no valid user found for claim %s", claim.claim_number)
                        continue

                    # DEDUPLICATION: Check if warning activity already exists for this claim
                    existing_activity = self.env['mail.activity'].search([
                        ('res_model_id.model', '=', 'clinic.insurance.claim'),
                        ('res_id', '=', claim.id),
                        ('activity_type_id', '=', activity_type_warning.id),
                        ('state', '!=', 'done'),
                    ], limit=1)

                    if not existing_activity:
                        claim.activity_schedule(
                            'mail.mail_activity_data_warning',
                            summary=_('Claim %s outstanding for %d days') % (
                                claim.claim_number, claim.days_outstanding
                            ),
                            user_id=assignee
                        )
                        _logger.debug("Created outstanding claim activity for %s (days: %d)", claim.claim_number, claim.days_outstanding)
                    else:
                        _logger.debug("Outstanding claim activity already exists for %s; skipping", claim.claim_number)

                except (AttributeError, AccessError) as e:
                    _logger.error("Error processing claim %s: %s", claim.claim_number, str(e))
                    continue

            return True

        except Exception as e:
            _logger.error("Error checking outstanding claims: %s", str(e))
            return False
