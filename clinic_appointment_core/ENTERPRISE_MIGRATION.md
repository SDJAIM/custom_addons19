# 🏗️ Enterprise Appointments Migration Plan

**Fecha inicio:** 2025-11-06
**Objetivo:** Replicar completamente Odoo Enterprise Appointments en Community Edition
**Versión:** Odoo 19 Community

---

## 📊 Arquitectura Objetivo

### Módulos del Sistema

```
clinic_appointment_core/
├── Core business logic
├── Models (appointment, type, stage, rule, questionnaire)
├── Slot engine con timezone awareness
├── Backend views (calendar, kanban, form)
└── Security & permissions

clinic_appointment_web/
├── Website/Portal controllers
├── QWeb templates (booking wizard)
├── AJAX slot fetching
├── Token-based confirmation
├── Reschedule/Cancel flows
└── Email templates con ICS

clinic_appointment_sms/ (opcional)
├── SMS reminders
├── SMS templates
└── Integration con sms module
```

---

## 🎯 Fase 1: Core Models + Slot Engine

### Status: 🟢 EN PROGRESO

### Objetivos
- ✅ Backup de código existente
- ⏳ Rediseñar `clinic.appointment` con `_inherits`
- ⏳ Crear `clinic.appointment.type`
- ⏳ Crear `clinic.appointment.stage`
- ⏳ Crear `clinic.appointment.rule`
- ⏳ Crear `clinic.appointment.questionnaire.line`
- ⏳ Implementar motor de slots
- ⏳ Tests unitarios básicos

### Cambios Clave

#### 1. clinic.appointment → Delegación a calendar.event

**ANTES (herencia múltiple - problemas):**
```python
_name = 'clinic.appointment'
_inherit = ['calendar.event', 'mail.thread']  # ❌ Causa conflictos M2M
```

**DESPUÉS (delegación - limpio):**
```python
_name = 'clinic.appointment'
_inherits = {'calendar.event': 'event_id'}  # ✅ Delegación
_inherit = ['mail.thread', 'mail.activity.mixin']

event_id = fields.Many2one('calendar.event', required=True, ondelete='cascade')
# Todos los campos de calendar.event accesibles vía delegación:
# start, stop, duration, categ_ids, partner_ids, alarm_ids, etc.
```

#### 2. Appointment Type - Configuración Completa

```python
class AppointmentType(models.Model):
    _name = 'clinic.appointment.type'

    # Básico
    name, description, default_duration

    # Booking
    allow_online_booking, min_notice_hours, max_days_ahead

    # Asignación
    assign_mode: ['random', 'round_robin', 'by_skill', 'customer_choice']

    # Capacidad
    capacity_per_slot, max_bookings_per_slot

    # Buffers
    buffer_before, buffer_after  # en horas

    # Reprogramación
    allow_reschedule, allow_cancel, reschedule_limit_hours

    # Meeting mode
    meeting_mode: ['onsite', 'online', 'phone']
    conferencing_url_template

    # Cuestionarios
    questionnaire_line_ids (O2M)
```

#### 3. Appointment Rules - Disponibilidad

```python
class AppointmentRule(models.Model):
    _name = 'clinic.appointment.rule'

    type_id  # Para qué tipo de cita aplica
    staff_id  # Opcional: regla específica de empleado

    # Temporalidad
    tz  # Zona horaria
    weekday (0-6)
    start_time, end_time  # Float (horas decimales)
    slot_interval_minutes

    # Validez
    active_from, active_to  # Fechas

    # Exclusiones
    exclude_public_holidays
    except_dates  # CSV de fechas YYYY-MM-DD

    # Capacidad
    max_bookings_per_slot (override del tipo)
```

#### 4. Motor de Slots

```python
# models/slot_engine.py

class SlotEngine:
    """
    Generador inteligente de slots disponibles

    Features:
    - Timezone awareness (browser TZ → rule TZ)
    - Aplicación de buffers
    - Validación min_notice_hours / max_days_ahead
    - Exclusión de festivos y except_dates
    - Chequeo de capacidad en tiempo real
    - Anti double-booking con locks
    """

    def get_available_slots(
        self,
        type_id,
        staff_id=None,
        start_date=None,
        end_date=None,
        tz='UTC'
    ):
        """
        Returns: [
            {
                'staff_id': 5,
                'start': datetime(2025, 11, 10, 9, 0, tzinfo=...),
                'end': datetime(2025, 11, 10, 9, 30, tzinfo=...),
                'capacity': 3,
                'available': 2,
                'label': '09:00 - 09:30',
            },
            ...
        ]
        """
```

---

## 📦 Estructura de Archivos (Fase 1)

```
clinic_appointment_core/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── appointment.py          # ✅ Rediseñado con _inherits
│   ├── appointment_type.py     # ✅ NUEVO
│   ├── appointment_stage.py    # ✅ NUEVO
│   ├── appointment_rule.py     # ✅ NUEVO
│   ├── questionnaire.py        # ✅ NUEVO
│   └── slot_engine.py          # ✅ NUEVO - Motor de slots
├── data/
│   ├── appointment_stages.xml  # Draft, Confirmed, Done, etc.
│   └── demo_types.xml          # Tipos de ejemplo
├── security/
│   ├── ir.model.access.csv
│   └── appointment_security.xml
├── views/
│   ├── appointment_views.xml
│   ├── appointment_type_views.xml
│   ├── appointment_rule_views.xml
│   └── menu_views.xml
└── tests/
    ├── __init__.py
    ├── test_appointment.py
    ├── test_slot_engine.py
    └── test_rules.py
```

---

## 🔧 Antipatrones Evitados

### ❌ NO USAR (Odoo 19)

```python
# 1. states= parameter (deprecated)
field = fields.Char(states={'draft': [('readonly', False)]})

# 2. related= a campos opcionales sin fallback
expiration_date = fields.Date(related='lot_id.life_date')  # Puede no existir!

# 3. Herencia múltiple con _inherit en modelo nuevo
_name = 'clinic.appointment'
_inherit = ['calendar.event']  # Copia campos, causa conflictos M2M
```

### ✅ SÍ USAR

```python
# 1. attrs en XML
<field name="field" attrs="{'readonly': [('state', '!=', 'draft')]}"/>

# 2. compute con fallback
@api.depends('lot_id')
def _compute_expiration(self):
    for rec in self:
        rec.expiration_date = getattr(rec.lot_id, 'life_date', False)

# 3. _inherits para delegación
_name = 'clinic.appointment'
_inherits = {'calendar.event': 'event_id'}  # Delega, no copia
```

---

## 🎯 Próximas Fases

### Fase 2: Website Booking Básico
- Controladores `/book`, `/book/<type_id>`
- Templates QWeb con wizard paso a paso
- AJAX para cargar slots dinámicamente
- Crear modelo `clinic.appointment.booking` (transient)

### Fase 3: Tokens + Confirmación
- Sistema de tokens URL-safe
- Email "Reserva recibida" con link de confirmación
- Confirmación → crear appointment + calendar.event
- Adjuntar archivo ICS

### Fase 4: Recordatorios + SMS
- Cron para enviar recordatorios X horas antes
- Mail templates
- Módulo SMS opcional

### Fase 5: Cuestionarios + Avanzado
- Renderizar cuestionarios dinámicos
- Validación de respuestas
- Asignación inteligente (round-robin, by_skill)
- Gestión de capacidad multi-slot

---

## 📚 Referencias

- [Odoo 19 ORM](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html)
- [Calendar Event Model](https://github.com/odoo/odoo/blob/19.0/addons/calendar/models/calendar_event.py)
- [_inherits Pattern](https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html#model-inheritance)
- [Timezone Best Practices](https://www.odoo.com/documentation/19.0/developer/howtos/rdtraining/07_basicviews.html)

---

**Última actualización:** 2025-11-06
**Estado:** Fase 1 en progreso
