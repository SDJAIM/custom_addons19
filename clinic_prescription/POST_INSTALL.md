# Post-Installation Configuration

## ⚠️ IMPORTANT: Enable Expiration Dates in Inventory

After installing the `clinic_prescription` module, you **MUST** enable expiration date tracking in Odoo's Inventory settings:

### Steps:

1. **Go to:** Inventory → Configuration → Settings

2. **Enable these options:**
   - ✅ **Lots & Serial Numbers** (under Traceability)
   - ✅ **Expiration Dates** (appears after enabling Lots & Serial Numbers)

3. **Click:** Save

### Why is this needed?

The prescription module uses **FEFO (First Expired, First Out)** logic to automatically select medication lots based on expiration dates. This requires the following fields in `stock.lot` (stock.production.lot):

- `life_date` - End of life date (expiration)
- `use_date` - Best before date
- `removal_date` - Removal date
- `alert_date` - Alert date

These fields are **only available** when "Expiration Dates" is enabled in Inventory settings.

### Verification:

After enabling, you can verify the fields exist by:

1. **From Odoo UI:**
   - Go to Inventory → Products → Lots/Serial Numbers
   - Open any lot and check if you see expiration date fields

2. **From API (optional):**
   ```bash
   POST /json/2/ir.model.fields/search_read
   {
     "domain": [
       ["model_id.model", "=", "stock.production.lot"],
       ["name", "in", ["life_date", "use_date", "removal_date", "alert_date"]]
     ],
     "fields": ["name", "ttype"],
     "limit": 10
   }
   ```

### What happens if I don't enable it?

You'll get this error during installation:
```
KeyError: 'Field life_date referenced in related field definition
clinic.prescription.lot.selection.line.expiration_date does not exist.'
```

## Related Modules

This configuration is required for:
- `clinic_prescription` - Prescription management with FEFO
- Any custom modules that track lot expiration dates

---

**Last updated:** 2025-01-24
