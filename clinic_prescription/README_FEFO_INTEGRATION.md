# FEFO Stock Integration for Clinic Prescription System

## Overview

This document describes the enhanced integration between the clinic prescription system and Odoo's native stock management, implementing First Expired, First Out (FEFO) tracking for pharmaceutical inventory management.

## Key Features Implemented

### 1. Native Stock Integration

- **Product Integration**: Each medication is automatically linked to a `product.product` record
- **Lot Tracking**: Medications use native Odoo lot tracking (`tracking='lot'`)
- **Expiration Management**: Full support for expiration dates, alerts, and removal dates
- **Stock Moves**: Dispensing creates native `stock.move` records for proper inventory tracking

### 2. FEFO Logic Implementation

#### Medication Model Enhancements (`clinic.medication`)

- **Enhanced Stock Fields**:
  - `use_expiration_date`: Enable expiration tracking
  - `expiration_time`: Default expiration time in days
  - `use_alert_date`: Enable expiry alerts
  - `alert_time`: Days before expiration to show alerts
  - `qty_available` & `virtual_available`: Real-time stock quantities

- **FEFO Methods**:
  - `get_fefo_lots(quantity, location_id)`: Returns lots ordered by expiration date
  - `get_available_lots(location_id)`: Gets all available lots
  - `check_expiring_lots(days)`: Finds lots expiring within specified days

#### Prescription Line Enhancements (`clinic.prescription.line`)

- **Lot Selection**:
  - `selected_lot_ids`: Many2many field for selected lots
  - `lot_id`: Primary lot for single-lot dispensing
  - `suggested_lots`: Computed field showing FEFO suggestions
  - `needs_lot_selection`: Indicates if lot tracking is required

- **Expiry Warnings**:
  - `has_expiring_lots`: Boolean flag for expiring lots
  - `expiry_warning`: Detailed expiry warning messages
  - Real-time calculation of expiry status

- **Stock Integration**:
  - `stock_location_id`: Source location for picking
  - `dest_location_id`: Destination location (customer)
  - `create_stock_move()`: Creates native stock moves with lot tracking

### 3. FEFO Wizards

#### Lot Selection Wizard (`clinic.prescription.lot.selection.wizard`)

- **Features**:
  - Shows all available lots with expiration dates
  - FEFO suggestion algorithm
  - Automatic lot selection based on expiry dates
  - Expiry warnings with color coding
  - Quantity validation

- **FEFO Algorithm**:
  1. Sort lots by expiration date (earliest first)
  2. Allocate quantities starting with earliest expiring lots
  3. Warn about expired or soon-to-expire lots
  4. Ensure total selected quantity meets requirement

#### Dispensing Wizard (`clinic.prescription.dispense.wizard`)

- **Features**:
  - Integration with lot selection
  - Stock location management
  - Expiry validation before dispensing
  - Force dispensing option for expiring lots
  - Creates proper stock moves with lot tracking

### 4. Stock Move Integration

#### Enhanced Stock Move Model (`stock.move`)

- **Additional Fields**:
  - `prescription_line_id`: Link to prescription line
  - `prescription_id`: Related prescription
  - `patient_id`: Related patient
  - `medication_id`: Related medication
  - `is_prescription_dispense`: Boolean flag

### 5. Views and User Interface

#### Enhanced Medication Form
- Stock integration section with tracking options
- Expiration management configuration
- FEFO management page with lot visibility

#### Enhanced Prescription Line Form
- FEFO stock management section
- Selected lots display
- Expiry warnings with visual indicators
- Lot selection button

#### Wizard Views
- User-friendly lot selection interface
- FEFO suggestions display
- Expiry status with color coding
- Quantity validation

## Usage Workflow

### 1. Medication Setup
1. Create medication record
2. System automatically creates linked product with lot tracking
3. Configure expiration and alert settings
4. Set up reorder levels

### 2. Stock Receiving
1. Use standard Odoo stock operations
2. Create lots with expiration dates
3. System automatically tracks lot quantities and expiry

### 3. Prescription Creation
1. Create prescription with medication lines
2. System automatically suggests FEFO lots
3. Review expiry warnings if any

### 4. Dispensing Process
1. Click "Dispense" on prescription line
2. System shows FEFO suggestions
3. Optionally select specific lots
4. System validates expiry and stock availability
5. Creates stock moves with proper lot tracking

## FEFO Algorithm Details

The FEFO implementation uses the following logic:

1. **Lot Query**: Find all lots with available quantity for the medication
2. **Sorting**: Sort lots by expiration date (ascending)
3. **Allocation**:
   - Start with earliest expiring lot
   - Allocate maximum possible quantity from each lot
   - Move to next lot if quantity needed exceeds available
4. **Validation**:
   - Check for expired lots
   - Warn about soon-to-expire lots
   - Validate total quantity availability

## Configuration

### Medication Configuration
```python
medication_vals = {
    'use_expiration_date': True,
    'expiration_time': 730,  # 2 years
    'use_alert_date': True,
    'alert_time': 30,  # 30 days warning
    'track_inventory': True,
}
```

### Product Auto-Configuration
When a medication is created, the system automatically configures the linked product:
- `type`: 'product'
- `tracking`: 'lot'
- `use_expiration_date`: Based on medication setting
- `expiration_time`: From medication configuration

## Integration Points

### With Odoo Stock Module
- Uses native `stock.quant` for lot quantities
- Creates `stock.move` for dispensing operations
- Integrates with `stock.location` for source/destination
- Supports standard stock operations and reporting

### With Prescription Workflow
- FEFO suggestions update when prescription quantities change
- Expiry warnings integrate with prescription validation
- Dispensing updates prescription quantities automatically

## Security and Access Rights

- Prescription users: Can view FEFO suggestions, cannot modify
- Pharmacists: Can select lots and dispense with warnings
- Managers: Full access to all FEFO operations

## Benefits

1. **Regulatory Compliance**: Ensures oldest stock is used first
2. **Waste Reduction**: Minimizes expired medication waste
3. **Patient Safety**: Prevents dispensing expired medications
4. **Inventory Accuracy**: Native stock integration ensures accurate tracking
5. **Workflow Efficiency**: Automated FEFO suggestions speed up dispensing
6. **Audit Trail**: Complete traceability through stock moves

## Technical Notes

- All lot operations use native Odoo stock functionality
- FEFO calculations are performed in real-time
- Expiry warnings are computed dynamically
- Stock moves maintain full audit trail
- Integration preserves all standard stock management features