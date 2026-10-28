"""Disposable native lifecycle probes; not the production deployment executor."""
from __future__ import annotations

import argparse
import configparser
import json
import re
import subprocess
import sys
from pathlib import Path

CONFIG = "/run/secrets/odoo_config"


def emit(value):
    print("MP_R0_RESULT=" + json.dumps(value, sort_keys=True), flush=True)


def native(database, variant, *, install=None, upgrade=None, code=None):
    command = [sys.executable, "odoo-bin"]
    if code is not None:
        command.append("shell")
    command += ["-c", CONFIG, "-d", database, "--workers=0", "--max-cron-threads=0", "--no-http", f"--addons-path=/opt/modular/addons,/opt/modular/fixtures/{variant}"]
    if code is None:
        command += ["--stop-after-init", "--without-demo"]
    if install:
        command += ["-i", install]
    if upgrade:
        command += ["-u", upgrade]
    subprocess.run(command, input=code, text=True, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["bootstrap", "install", "inspect", "upgrade", "fail", "check-v2", "check-partial", "signal", "uninstall"])
    parser.add_argument("--database", required=True)
    parser.add_argument("--variant", choices=["v1", "v2", "bad"], default="v1")
    parser.add_argument("--probe-field", default="x_r0_signal")
    args = parser.parse_args()
    database = args.database
    if not re.fullmatch(r"mp_disposable_r0_[a-z0-9_]+", database):
        raise ValueError("R0 probes only operate on harness-named disposable databases")
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG)
    import psycopg2
    from psycopg2 import sql
    options = cfg["options"]
    conn = psycopg2.connect(host=options["db_host"], user=options["db_user"], password=options["db_password"], dbname="postgres")
    conn.autocommit = True
    try:
        with conn.cursor() as cr:
            cr.execute("SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname=%s", [database])
            existing = cr.fetchone()
            marker = "modular-platform disposable R0 " + database
            if args.action == "bootstrap":
                if existing:
                    raise RuntimeError("Database exists; inspect/reconcile it instead of repeating initialization")
                cr.execute(sql.SQL("CREATE DATABASE {} OWNER modular TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(database)))
                cr.execute(sql.SQL("COMMENT ON DATABASE {} IS %s").format(sql.Identifier(database)), [marker])
            elif not existing or existing[0] != marker:
                raise RuntimeError("Refusing an unrecognized database: missing harness ownership marker")
    finally:
        conn.close()
    if args.action == "bootstrap":
        native(database, "v1", install="web,auth_password_policy")
        native(database, "v1", code="""from pathlib import Path
password = Path('/run/mp-bootstrap/password').read_text().strip()
env.ref('base.user_admin').write({'password': password})
env['ir.config_parameter'].sudo().set_param('mp.r0.database', env.cr.dbname)
env.cr.commit()
print('MP_R0_RESULT=' + __import__('json').dumps({'bootstrap': 'complete', 'database': env.cr.dbname}))
""")
    elif args.action == "install":
        native(database, "v1", install="mp_r0_extension")
        native(database, "v1", code="""import base64, json
record = env['mp.r0.fixture'].create({'name': 'Original fixture', 'label': 'blue', 'revision': 1})
attachment = env['ir.attachment'].create({'name': 'r0-proof.txt', 'res_model': 'mp.r0.fixture', 'res_id': record.id, 'datas': base64.b64encode(b'R0 attachment checkpoint')})
env['ir.config_parameter'].sudo().set_param('mp.r0.record', str(record.id))
env['ir.config_parameter'].sudo().set_param('mp.r0.attachment', str(attachment.id))
env.cr.commit()
print('MP_R0_RESULT=' + json.dumps({'record': record.id, 'attachment': attachment.id, 'name': record.name, 'label': record.label, 'store_fname': attachment.store_fname}))
""")
    elif args.action == "upgrade":
        native(database, "v2", upgrade="mp_r0_fixture,mp_r0_extension")
    elif args.action == "fail":
        native(database, "bad", upgrade="mp_r0_fixture,mp_r0_extension")
        raise RuntimeError("Expected fixture failure did not occur")
    elif args.action == "inspect":
        native(database, args.variant, code="""import json, odoo.addons
modules = env['ir.module.module'].search([('state', '=', 'installed')])
result = {'database': env.cr.dbname, 'addons_paths': list(odoo.addons.__path__), 'installed': {m.name: m.latest_version for m in modules}, 'nonfinal': {m.name: m.state for m in env['ir.module.module'].search([('state', 'in', ['to install','to upgrade','to remove'])])}}
print('MP_R0_RESULT=' + json.dumps(result, sort_keys=True))
""")
    elif args.action == "check-v2":
        native(database, "v2", code="""import base64, json
record = env['mp.r0.fixture'].browse(int(env['ir.config_parameter'].sudo().get_param('mp.r0.record')))
assert record.name == 'Original fixture', record.name
assert record.label == 'BLUE' and record.label_length == 4
attachment = env['ir.attachment'].browse(int(env['ir.config_parameter'].sudo().get_param('mp.r0.attachment')))
assert base64.b64decode(attachment.datas) == b'R0 attachment checkpoint'
print('MP_R0_RESULT=' + json.dumps({'v2_data_and_attachment': 'passed', 'record': record.id, 'label': record.label}))
""")
    elif args.action == "check-partial":
        native(database, "v2", code="""import json
env.cr.execute('SELECT name FROM mp_r0_fixture ORDER BY id LIMIT 1')
assert env.cr.fetchone()[0] == 'committed-before-failure'
print('MP_R0_RESULT=' + json.dumps({'partial_commit_observed': True, 'recovery_required': True}))
""")
    elif args.action == "signal":
        if not re.fullmatch(r"x_r0_signal(?:_[0-9a-f]{8})?", args.probe_field):
            raise ValueError("Invalid disposable signal field")
        native(database, args.variant, code=f"field_name = {args.probe_field!r}\n" + """import json
model = env['ir.model']._get('mp.r0.fixture')
assert not env['ir.model.fields'].search_count([('model_id', '=', model.id), ('name', '=', field_name)]), 'Signal fixture already exists; inspect prior test evidence before replay'
env['ir.model.fields'].create({'name': field_name, 'field_description': 'Disposable cross-worker registry proof', 'model_id': model.id, 'ttype': 'char', 'state': 'manual'})
env.cr.commit()
env.registry.signal_changes()
print('MP_R0_RESULT=' + json.dumps({'registry_signal_sent': True, 'field': field_name}))
""")
    elif args.action == "uninstall":
        native(database, args.variant, code="""import json
env['ir.module.module'].search([('name', '=', 'mp_r0_fixture')]).button_immediate_uninstall()
env.cr.commit()
env.cr.execute("SELECT to_regclass('mp_r0_fixture')")
assert env.cr.fetchone()[0] is None
print('MP_R0_RESULT=' + json.dumps({'native_table_removed': True}))
""")


if __name__ == "__main__":
    main()
