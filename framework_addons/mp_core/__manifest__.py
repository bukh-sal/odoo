{
    'name': 'Modular Platform Core', 'version': '19.0.0.2.7',
    'depends': ['mp_identity','bus'], 'license': 'LGPL-3', 'author': 'Modular Platform',
    'data': ['security/ir.model.access.csv', 'views/job_history.xml', 'views/workspace_landing.xml'],
    'assets': {'web.assets_backend': [
        'mp_core/static/src/workspace_menu.js', 'mp_core/static/src/workspace_menu.scss',
    ]},
}
