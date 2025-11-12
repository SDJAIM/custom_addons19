# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class AppointmentQuestionnaire(models.Model):
    """
    Appointment Questionnaire Line
    Questions to ask before/during appointment booking
    """
    _name = 'clinic.appointment.questionnaire.line'
    _description = 'Appointment Questionnaire Line'
    _order = 'type_id, sequence, id'

    # BASIC INFORMATION
    name = fields.Char(string='Question', required=True, translate=True)
    active = fields.Boolean(string='Active', default=True)
    sequence = fields.Integer(string='Sequence', default=10)
    
    # APPOINTMENT TYPE
    type_id = fields.Many2one(
        'clinic.appointment.type',
        string='Appointment Type',
        required=True,
        ondelete='cascade',
        help='Appointment type this question belongs to'
    )
    
    # QUESTION TYPE
    question_type = fields.Selection([
        ('text', 'Text'),
        ('textarea', 'Long Text'),
        ('selection', 'Multiple Choice'),
        ('checkbox', 'Checkbox'),
        ('date', 'Date'),
        ('number', 'Number'),
    ], string='Question Type', required=True, default='text')
    
    # ANSWER OPTIONS (For selection type)
    answer_options = fields.Text(
        string='Answer Options',
        help='One option per line (for Multiple Choice questions)'
    )
    
    # VALIDATION
    required = fields.Boolean(
        string='Required',
        default=False,
        help='Customer must answer this question to book'
    )
    
    placeholder = fields.Char(
        string='Placeholder',
        translate=True,
        help='Placeholder text shown in the form field'
    )
    
    help_text = fields.Text(
        string='Help Text',
        translate=True,
        help='Additional help text shown below the question'
    )
    
    @api.constrains('question_type', 'answer_options')
    def _check_answer_options(self):
        """Validate that selection type has options"""
        for line in self:
            if line.question_type == 'selection' and not line.answer_options:
                raise ValidationError(_(
                    'Multiple Choice questions must have answer options defined'
                ))
    
    def get_answer_options_list(self):
        """Get answer options as list"""
        self.ensure_one()
        if not self.answer_options:
            return []
        return [opt.strip() for opt in self.answer_options.split('\n') if opt.strip()]


class AppointmentQuestionnaireAnswer(models.Model):
    """
    Appointment Questionnaire Answer
    Stores customer answers to questionnaire
    """
    _name = 'clinic.appointment.questionnaire.answer'
    _description = 'Appointment Questionnaire Answer'
    _order = 'appointment_id, sequence, id'

    # RELATIONSHIP
    appointment_id = fields.Many2one(
        'clinic.appointment',
        string='Appointment',
        required=True,
        ondelete='cascade',
        index=True
    )

    question_id = fields.Many2one(
        'clinic.appointment.questionnaire.line',
        string='Question',
        ondelete='cascade',
        index=True,
        help='Optional link to predefined question'
    )

    # SIMPLE QUESTION (if not using predefined questions)
    question = fields.Char(
        string='Question Text',
        help='Direct question text (if not linked to predefined question)'
    )

    # SEQUENCE for ordering
    sequence = fields.Integer(string='Sequence', default=10)

    # ANSWERS - support multiple answer types
    answer_text = fields.Text(string='Text Answer')
    answer_bool = fields.Boolean(string='Boolean Answer')
    answer_number = fields.Float(string='Numeric Answer')
    answer_date = fields.Date(string='Date Answer')

    # COMPUTED DISPLAY
    question_name = fields.Char(
        compute='_compute_question_name',
        string='Question Display',
        store=True
    )

    question_type = fields.Selection(
        related='question_id.question_type',
        string='Type',
        store=True,
        readonly=True
    )

    @api.depends('question', 'question_id.name')
    def _compute_question_name(self):
        """Get question name from related question or use direct question text"""
        for answer in self:
            if answer.question_id:
                answer.question_name = answer.question_id.name
            else:
                answer.question_name = answer.question or 'Untitled Question'

    # Odoo 19 Constraint API
    # PostgreSQL UNIQUE treats NULL ≠ NULL, so multiple NULL question_ids are allowed
    # Only one answer per predefined (non-NULL) question_id per appointment
    _unique_answer_per_predefined_question = models.Constraint(
        'UNIQUE(appointment_id, question_id)',
        'Only one answer per predefined question per appointment allowed'
    )
