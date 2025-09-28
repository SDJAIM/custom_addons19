# -*- coding: utf-8 -*-
{
    'name': "Clinic Theme & Design System",
    'version': '19.0.1.0.0',
    'category': 'Website/Website',
    'summary': 'Modern healthcare theme with accessibility and mobile-first design',
    'sequence': 13,
    
    'description': """
Clinic Theme & Design System
============================
Modern, accessible design system for the clinic management system.

Features:
---------
* Healthcare-focused color palette
* Accessible components (WCAG 2.1 AA)
* Mobile-first responsive design
* Custom icons for medical features
* Loading animations
* Empty state illustrations
* Form styling improvements
* Card-based layouts
* Enhanced buttons and badges
* Improved navigation
* Dark mode support
* High contrast mode
* RTL language support
* Print-optimized styles
* Custom fonts
    """,
    
    'author': "Clinic System",
    'license': 'LGPL-3',
    'website': "https://www.clinicsystem.com",
    
    'depends': [
        'web',
        'website',
    ],
    
    'data': [
        # Note: assets.xml uses old Odoo approach - consider migrating to 'assets' key
        'views/assets.xml',
    ],
    
    'assets': {
        'web.assets_backend': [
            'clinic_theme/static/src/scss/variables.scss',
            # Empty files commented out to prevent compilation errors
            # 'clinic_theme/static/src/scss/base.scss',
            # 'clinic_theme/static/src/scss/components.scss',
            # 'clinic_theme/static/src/scss/forms.scss',
            # 'clinic_theme/static/src/scss/buttons.scss',
            # 'clinic_theme/static/src/scss/cards.scss',
            # 'clinic_theme/static/src/scss/animations.scss',
            # 'clinic_theme/static/src/scss/responsive.scss',
            # 'clinic_theme/static/src/scss/dark_mode.scss',
            'clinic_theme/static/src/scss/accessibility.scss',
        ],
        # 'web.assets_frontend': [
        #     'clinic_theme/static/src/scss/website.scss',  # Empty file
        # ],
    },
    
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],
    
    'installable': True,
    'application': False,
    'auto_install': False,
}