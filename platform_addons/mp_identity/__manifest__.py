{
    "name": "Modular Platform Identity",
    "version": "19.0.0.1.10",
    "depends": ["mp_compat"],
    "license": "LGPL-3",
    "author": "Modular Platform",
    "data": ["security/ir.model.access.csv", "security/rules.xml"],
    "assets": {
        "web.assets_web": [
            ("before", "web/static/src/main.js", "mp_identity/static/src/native_webclient.js"),
        ],
    },
}
