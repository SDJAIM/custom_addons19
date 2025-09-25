# CHANGELOG - clinic_finance

## [19.0.1.0.1] - 2025-09-25

### Fixed
- Removed references to non-existent files from `__manifest__.py`:
  - 6 missing view files (insurance_policy_views, insurance_claim_views, payment_plan_views, billing_views, revenue_analysis_views, menu_views)
  - 3 missing report files (invoice_report, claim_report, revenue_report)
  - 2 missing wizard files (claim_submission_wizard, payment_collection_wizard)
  - 2 missing asset files (finance.scss, payment_widget.js)

### Verified
- No _sql_constraints found (compliant with Odoo 19)
- No commented code blocks requiring action
- Security files exist and properly configured
- Data files exist (finance_sequence, payment_terms, insurance_data)
- One view file exists (invoice_views.xml)
- Module dependencies correct (includes account, sale, clinic modules)