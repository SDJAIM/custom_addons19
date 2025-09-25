# 🌐 Clinic REST API Documentation

## Overview
The Clinic REST API provides secure programmatic access to the clinic management system. Built on Odoo 19, it offers RESTful endpoints with JWT authentication for external integrations.

## 🔐 Authentication

### JWT Token Authentication
All API requests require JWT token authentication.

#### Get Authentication Token
```http
POST /api/auth/login
Content-Type: application/json

{
    "username": "user@clinic.com",
    "password": "secure_password"
}
```

**Response:**
```json
{
    "success": true,
    "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "expires_in": 3600,
    "user": {
        "id": 1,
        "name": "John Doe",
        "email": "user@clinic.com"
    }
}
```

#### Using the Token
Include the token in the Authorization header:
```http
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

---

## 📋 API Endpoints

### Patient Management

#### List Patients
```http
GET /api/patients
```

**Query Parameters:**
- `limit` (int): Number of records to return (default: 50)
- `offset` (int): Number of records to skip
- `search` (string): Search term for name/email/phone
- `active` (boolean): Filter active/inactive patients

**Response:**
```json
{
    "success": true,
    "count": 150,
    "data": [
        {
            "id": 1,
            "patient_id": "PAT/2025/001",
            "name": "John Doe",
            "email": "john@example.com",
            "mobile": "+1234567890",
            "date_of_birth": "1990-01-15",
            "age": 35,
            "gender": "male",
            "blood_group": "o+"
        }
    ]
}
```

#### Get Patient Details
```http
GET /api/patients/{patient_id}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "id": 1,
        "patient_id": "PAT/2025/001",
        "name": "John Doe",
        "email": "john@example.com",
        "mobile": "+1234567890",
        "date_of_birth": "1990-01-15",
        "age": 35,
        "gender": "male",
        "blood_group": "o+",
        "allergies": "Penicillin",
        "medical_history": "Diabetes Type 2",
        "insurance_policies": [
            {
                "id": 1,
                "company": "HealthCare Inc",
                "policy_number": "HC123456",
                "valid_until": "2025-12-31"
            }
        ],
        "appointments": {
            "total": 10,
            "upcoming": 2,
            "completed": 8
        }
    }
}
```

#### Create Patient
```http
POST /api/patients
Content-Type: application/json

{
    "name": "Jane Smith",
    "date_of_birth": "1985-05-20",
    "mobile": "+1987654321",
    "email": "jane@example.com",
    "gender": "female",
    "blood_group": "a+",
    "address": {
        "street": "123 Main St",
        "city": "New York",
        "state": "NY",
        "zip": "10001"
    }
}
```

**Response:**
```json
{
    "success": true,
    "message": "Patient created successfully",
    "data": {
        "id": 2,
        "patient_id": "PAT/2025/002"
    }
}
```

#### Update Patient
```http
PUT /api/patients/{patient_id}
Content-Type: application/json

{
    "mobile": "+1999888777",
    "email": "newemail@example.com",
    "allergies": "Penicillin, Aspirin"
}
```

---

### Appointment Management

#### List Appointments
```http
GET /api/appointments
```

**Query Parameters:**
- `date_from` (date): Start date filter
- `date_to` (date): End date filter
- `patient_id` (int): Filter by patient
- `doctor_id` (int): Filter by doctor
- `status` (string): Filter by status (draft/confirmed/done/cancelled)

**Response:**
```json
{
    "success": true,
    "data": [
        {
            "id": 1,
            "appointment_number": "APT/2025/001",
            "patient": {
                "id": 1,
                "name": "John Doe"
            },
            "doctor": {
                "id": 1,
                "name": "Dr. Smith"
            },
            "start": "2025-01-25T10:00:00",
            "stop": "2025-01-25T10:30:00",
            "status": "confirmed",
            "type": "consultation"
        }
    ]
}
```

#### Book Appointment
```http
POST /api/appointments
Content-Type: application/json

{
    "patient_id": 1,
    "doctor_id": 1,
    "appointment_date": "2025-01-25",
    "start_time": "10:00",
    "appointment_type": "consultation",
    "reason": "Regular checkup",
    "notes": "Patient has high blood pressure"
}
```

**Response:**
```json
{
    "success": true,
    "message": "Appointment booked successfully",
    "data": {
        "id": 2,
        "appointment_number": "APT/2025/002",
        "confirmation_code": "CONF123"
    }
}
```

#### Get Available Slots
```http
GET /api/appointments/slots
```

**Query Parameters:**
- `date` (date): Date to check availability (required)
- `doctor_id` (int): Specific doctor (optional)
- `service_type` (string): Type of service

**Response:**
```json
{
    "success": true,
    "data": [
        {
            "time": "09:00",
            "available": true,
            "doctor_id": 1,
            "doctor_name": "Dr. Smith"
        },
        {
            "time": "09:30",
            "available": true,
            "doctor_id": 1,
            "doctor_name": "Dr. Smith"
        },
        {
            "time": "10:00",
            "available": false,
            "doctor_id": 1,
            "doctor_name": "Dr. Smith"
        }
    ]
}
```

#### Cancel Appointment
```http
DELETE /api/appointments/{appointment_id}
Content-Type: application/json

{
    "reason": "Patient requested cancellation"
}
```

---

### Prescription Management

#### Get Patient Prescriptions
```http
GET /api/patients/{patient_id}/prescriptions
```

**Response:**
```json
{
    "success": true,
    "data": [
        {
            "id": 1,
            "prescription_number": "RX/2025/001",
            "date": "2025-01-20",
            "doctor": "Dr. Smith",
            "status": "dispensed",
            "medications": [
                {
                    "name": "Amoxicillin",
                    "dosage": "500mg",
                    "frequency": "3 times daily",
                    "duration": "7 days",
                    "quantity": 21
                }
            ]
        }
    ]
}
```

#### Create Prescription
```http
POST /api/prescriptions
Content-Type: application/json

{
    "patient_id": 1,
    "doctor_id": 1,
    "appointment_id": 1,
    "medications": [
        {
            "medication_id": 1,
            "dosage": "500mg",
            "frequency": "twice daily",
            "duration": "10 days",
            "quantity": 20,
            "instructions": "Take with food"
        }
    ],
    "notes": "Complete the full course"
}
```

---

### Treatment Plans

#### Get Treatment Plans
```http
GET /api/patients/{patient_id}/treatment-plans
```

**Response:**
```json
{
    "success": true,
    "data": [
        {
            "id": 1,
            "name": "Dental Restoration Plan",
            "start_date": "2025-01-01",
            "status": "in_progress",
            "procedures": [
                {
                    "name": "Root Canal",
                    "status": "completed",
                    "date": "2025-01-15"
                },
                {
                    "name": "Crown Placement",
                    "status": "scheduled",
                    "date": "2025-02-01"
                }
            ],
            "total_cost": 1500.00,
            "insurance_coverage": 1200.00
        }
    ]
}
```

---

### Staff Management

#### Get Staff Availability
```http
GET /api/staff/availability
```

**Query Parameters:**
- `date` (date): Date to check
- `specialty` (string): Filter by specialty
- `branch_id` (int): Filter by branch

**Response:**
```json
{
    "success": true,
    "data": [
        {
            "id": 1,
            "name": "Dr. Smith",
            "specialty": "General Medicine",
            "available_slots": ["09:00", "09:30", "10:00", "14:00", "14:30"],
            "branch": "Main Clinic"
        }
    ]
}
```

---

### Insurance Verification

#### Verify Insurance
```http
POST /api/insurance/verify
Content-Type: application/json

{
    "patient_id": 1,
    "insurance_company": "HealthCare Inc",
    "policy_number": "HC123456",
    "service_codes": ["CPT99213", "CPT99214"]
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "verified": true,
        "coverage": {
            "deductible_met": 500.00,
            "deductible_remaining": 500.00,
            "copay": 25.00,
            "coverage_percentage": 80,
            "services": [
                {
                    "code": "CPT99213",
                    "covered": true,
                    "amount": 150.00
                }
            ]
        }
    }
}
```

---

## 🔄 Webhooks

### Available Webhook Events

The API supports webhooks for real-time notifications:

- `appointment.created` - New appointment booked
- `appointment.confirmed` - Appointment confirmed
- `appointment.cancelled` - Appointment cancelled
- `prescription.created` - New prescription issued
- `patient.created` - New patient registered
- `payment.received` - Payment processed

### Webhook Configuration
```http
POST /api/webhooks
Content-Type: application/json

{
    "url": "https://your-app.com/webhook",
    "events": ["appointment.created", "appointment.confirmed"],
    "secret": "your_webhook_secret"
}
```

### Webhook Payload Example
```json
{
    "event": "appointment.created",
    "timestamp": "2025-01-23T10:30:00Z",
    "data": {
        "appointment_id": 123,
        "patient_id": 1,
        "doctor_id": 1,
        "date": "2025-01-25",
        "time": "10:00"
    },
    "signature": "sha256=..."
}
```

---

## 🚦 Rate Limiting

API requests are rate-limited to ensure fair usage:

- **Default limit:** 1000 requests per hour per API key
- **Burst limit:** 100 requests per minute

Rate limit headers in response:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1611403200
```

---

## 📊 Response Formats

### Success Response
```json
{
    "success": true,
    "message": "Operation successful",
    "data": { }
}
```

### Error Response
```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid input data",
        "details": {
            "field": "email",
            "error": "Invalid email format"
        }
    }
}
```

### Error Codes
- `AUTH_FAILED` - Authentication failed
- `TOKEN_EXPIRED` - JWT token expired
- `VALIDATION_ERROR` - Input validation failed
- `NOT_FOUND` - Resource not found
- `PERMISSION_DENIED` - Insufficient permissions
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `SERVER_ERROR` - Internal server error

---

## 🧪 Testing

### Test Environment
Base URL: `https://api-test.clinic.com`

### Test Credentials
```json
{
    "username": "test@clinic.com",
    "password": "test123",
    "api_key": "test_key_123"
}
```

### Sample cURL Commands

**Get Token:**
```bash
curl -X POST https://api.clinic.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user@clinic.com","password":"password"}'
```

**Get Patients:**
```bash
curl -X GET https://api.clinic.com/api/patients \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Book Appointment:**
```bash
curl -X POST https://api.clinic.com/api/appointments \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": 1,
    "doctor_id": 1,
    "appointment_date": "2025-01-25",
    "start_time": "10:00"
  }'
```

---

## 📦 SDKs

### Python SDK
```python
from clinic_api import ClinicAPI

api = ClinicAPI(api_key='your_api_key')

# Get patients
patients = api.patients.list(limit=10)

# Book appointment
appointment = api.appointments.create(
    patient_id=1,
    doctor_id=1,
    date='2025-01-25',
    time='10:00'
)
```

### JavaScript SDK
```javascript
const ClinicAPI = require('clinic-api-sdk');

const api = new ClinicAPI({ apiKey: 'your_api_key' });

// Get patients
const patients = await api.patients.list({ limit: 10 });

// Book appointment
const appointment = await api.appointments.create({
    patientId: 1,
    doctorId: 1,
    date: '2025-01-25',
    time: '10:00'
});
```

---

## 🔒 Security Best Practices

1. **Always use HTTPS** for API calls
2. **Store API keys securely** - never in client-side code
3. **Implement webhook signature verification**
4. **Use short-lived JWT tokens** (1 hour default)
5. **Implement request retry with exponential backoff**
6. **Log all API access** for audit purposes

---

## 📄 Changelog

### Version 1.0.0 (2025-01-23)
- Initial API release
- JWT authentication
- Patient, appointment, prescription endpoints
- Webhook support
- Rate limiting

---

## 📞 Support

For API support:
- Email: api-support@clinic.com
- Documentation: https://api.clinic.com/docs
- Status Page: https://status.clinic.com

---

*API Version: 1.0.0 | Odoo 19 Community Edition*