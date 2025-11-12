# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class TelemedicineSettings(models.TransientModel):
    """
    Simplified Telemedicine Settings for Discuss Integration

    Note: Platform-specific settings (Zoom, Meet, Jitsi) have been removed
    as telemedicine now uses Odoo Discuss WebRTC for video calls.
    """
    _name = 'clinic.telemed.settings'
    _description = 'Telemedicine Configuration Settings'
    _inherit = 'res.config.settings'

    # Session Defaults
    default_session_duration = fields.Integer(
        string='Default Session Duration (minutes)',
        default=30,
        config_parameter='clinic.telemed.default_duration',
        help='Default duration for telemedicine sessions'
    )

    # Recording Settings
    recording_enabled = fields.Boolean(
        string='Enable Session Recording',
        config_parameter='clinic.telemed.recording_enabled',
        help='Allow session recordings (subject to Discuss recording capabilities)'
    )

    recording_retention_days = fields.Integer(
        string='Recording Retention (days)',
        default=90,
        config_parameter='clinic.telemed.recording_retention',
        help='Number of days to retain session recordings for compliance'
    )

    # Notification Settings
    send_email_invites = fields.Boolean(
        string='Send Email Invitations',
        default=True,
        config_parameter='clinic.telemed.send_email_invites',
        help='Automatically send email invitations to patients and doctors'
    )

    send_sms_reminders = fields.Boolean(
        string='Send SMS Reminders',
        default=False,
        config_parameter='clinic.telemed.send_sms_reminders',
        help='Send SMS reminders before telemedicine sessions'
    )

    reminder_time = fields.Integer(
        string='Reminder Time (minutes)',
        default=15,
        config_parameter='clinic.telemed.reminder_time',
        help='Send reminders X minutes before session starts'
    )

    # Auto-create Channel
    auto_create_channel = fields.Boolean(
        string='Auto-create Discuss Channel',
        default=True,
        config_parameter='clinic.telemed.auto_create_channel',
        help='Automatically create Discuss channel when telemedicine session is created'
    )

    # Help Text
    module_info = fields.Html(
        string='Module Information',
        compute='_compute_module_info',
        readonly=True
    )

    @api.depends()
    def _compute_module_info(self):
        info_text = """
        <div class="alert alert-info">
            <h4>Telemedicine with Odoo Discuss</h4>
            <p>
                Telemedicine sessions now use Odoo's built-in <strong>Discuss</strong> module
                for video calling with WebRTC technology.
            </p>
            <ul>
                <li>✅ No external platform API keys required</li>
                <li>✅ Native Odoo integration</li>
                <li>✅ Video + audio + chat in one place</li>
                <li>✅ Secure, HIPAA-compliant when properly configured</li>
            </ul>
            <p>
                <strong>How it works:</strong><br/>
                1. Create a telemedicine session from an appointment<br/>
                2. Click "Create Video Channel" to set up Discuss channel<br/>
                3. Doctor and patient join via "Join Video Call" button<br/>
                4. Complete session when consultation is done
            </p>
        </div>
        """
        for setting in self:
            setting.module_info = info_text
