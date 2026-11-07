# Derived from Odoo mail. See LICENSE and COPYRIGHT.
{'name': 'Incoming Mail Gateway',
 'version': '1.0',
 'depends': ['mail'],
 'application': True,
 'data': ['security/ir.model.access.csv',
          'views/mail_mail_views.xml',
          'views/fetchmail_views.xml',
          'views/mail_mail_field_views.xml',
          'data/ir_cron_data.xml',
          'views/mail_menus.xml',
          'views/res_config_settings_views.xml'],
 'license': 'LGPL-3',
 'author': 'Modular Platform; derived from Odoo S.A.'}
