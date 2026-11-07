{
    "name": "Disposable Workspace Feasibility",
    "version": "19.0.0.1.0",
    "depends": ["mp_identity"],
    "license": "LGPL-3",
    "author": "Modular Platform",
    "data": ["security/ir.model.access.csv", "security/rules.xml", "views/records.xml", "views/host.xml"],
    "assets": {
        "mp_feas.assets_host": [
            ("include", "web.assets_web"),
            ("remove", "web/static/src/main.js"),
            "mp_feas/static/src/plain_page.js",
            "mp_feas/static/src/host.js",
            "mp_feas/static/src/host.css",
        ],
    },
}
