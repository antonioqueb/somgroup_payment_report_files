{
    'name': 'SOMGROUP - Términos de Pago Importaciones',
    'version': '19.0.2.0.0',
    'category': 'Purchase',
    'summary': 'Términos de pago especiales para importaciones con fecha BL y cálculo automático de vencimientos',
    'description': """
        Módulo para gestión de pagos a proveedores de importación:
        - Campo Fecha BL en orden de compra
        - Términos de pago con reglas de anticipos, balances y vencimientos
        - Cálculo automático de fechas basado en BL o ETA
        - Soporte para términos CAD, contra entrega, anticipos parciales
        - Integración con account.payment (pagos contables reales)
        - Estado del calendario actualizado automáticamente al confirmar pagos
        - Reporte consolidado de pagos a proveedores (visor mensual)
        - Dashboard JS con resumen ejecutivo por categoría
        - Proyección multi-mes de compromisos futuros
    """,
    'author': 'Alphaqueb Consulting SAS',
    'depends': ['purchase', 'account', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/payment_term_data.xml',
        'wizard/import_payment_wizard_views.xml',
        'views/import_payment_line_views.xml',
        'views/import_payment_report_views.xml',
        'views/import_payment_dashboard_menus.xml',
        'views/purchase_order_views.xml',
        'views/purchase_order_views_report.xml',
        'views/payment_term_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'somgroup_payment_terms/static/src/js/import_payment_dashboard.js',
            'somgroup_payment_terms/static/src/xml/import_payment_dashboard.xml',
            'somgroup_payment_terms/static/src/css/import_payment_dashboard.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}