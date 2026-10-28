{
    'name':'Modular Platform Shell','version':'19.0.0.1.1','depends':['mp_core'],
    'license':'LGPL-3','author':'Modular Platform','data':['views/bootstrap.xml'],
    'assets': {'mp_shell.assets_host': [
        ('include','web.assets_web'),('remove','web/static/src/main.js'),
        'mp_shell/static/src/operations.js','mp_shell/static/src/native_interactions.js','mp_shell/static/src/host.js','mp_shell/static/src/host.css',
    ]},
}
