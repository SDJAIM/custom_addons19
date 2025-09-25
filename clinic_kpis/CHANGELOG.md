# CHANGELOG - clinic_kpis

## [19.0.1.0.0] - 2025-09-25

### Fixed
- Commented out references to non-existent files from `__manifest__.py`:
  - 2 missing data files (kpi_data.xml, dashboard_data.xml)
  - 6 missing view files (all dashboard and analytics views)
  - 2 missing report files (kpi_report_templates.xml, monthly_report.xml)
  - 4 missing asset files (dashboard.scss, dashboard_widget.js, kpi_renderer.js, dashboard_templates.xml)

### Verified
- No _sql_constraints found (compliant with Odoo 19)
- No commented code blocks requiring action
- Security files exist and properly configured
- Module dependencies correct (includes board for dashboard functionality)
- Note: board module is available in Community Edition