"""Local R0 harness. All data targets are generated and explicitly disposable."""
from __future__ import annotations

import argparse
import configparser
import hashlib
import http.cookiejar
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local/r0"
STATE = LOCAL / "state.json"


def now():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def load():
    state = json.loads(STATE.read_text())
    if not re.fullmatch(r"mp-r0-[a-z0-9]+", state["project"]):
        raise ValueError("Invalid harness project")
    for target in state["databases"]:
        if not re.fullmatch(r"mp_disposable_r0_[a-z0-9_]+", target):
            raise ValueError("Non-disposable database in state")
    return state


def save(state):
    STATE.write_text(json.dumps(state, indent=2) + "\n")


def setup():
    if STATE.exists():
        state = load()
        print(json.dumps({"setup": "already_exists", "project": state["project"], "database": state["active_db"]}))
        return
    LOCAL.mkdir(parents=True, exist_ok=True)
    run = datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%Sz").lower()
    database = "mp_disposable_r0_" + run
    project = "mp-r0-" + run.replace("t", "").replace("z", "")
    port = 18069
    while port < 18100:
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
                break
            except OSError:
                port += 1
    if port >= 18100:
        raise RuntimeError("No free loopback harness port")
    for name in ["postgres-password", "app-db-password", "bootstrap-password", "database-master-password"]:
        (LOCAL / name).write_text(secrets.token_urlsafe(32) + "\n")
    config = configparser.ConfigParser()
    config["options"] = {
        "db_host": "db", "db_port": "5432", "db_user": "modular",
        "db_password": (LOCAL / "app-db-password").read_text().strip(),
        "admin_passwd": (LOCAL / "database-master-password").read_text().strip(),
        "db_name": database, "dbfilter": "^" + database + "$", "list_db": "False",
        "data_dir": "/var/lib/modular", "addons_path": "/opt/modular/addons,/opt/modular/fixtures/v1",
        "server_wide_modules": "base,web", "without_demo": "True", "max_cron_threads": "0",
        "workers": "2", "db_maxconn": "12", "http_interface": "0.0.0.0",
        "proxy_mode": "False", "limit_memory_soft": "536870912", "limit_memory_hard": "671088640",
    }
    with (LOCAL / "odoo.conf").open("w") as handle:
        config.write(handle)
    evidence = ROOT / "docs/evidence/G0" / run
    evidence.mkdir(parents=True)
    state = {"run_id": run, "project": project, "active_db": database, "databases": [database], "port": port, "variant": "v1", "stage": "empty", "evidence": str(evidence.relative_to(ROOT)), "created_by": "tools/r0.py", "disposable": True}
    save(state)
    write_compose_env(state)
    print(json.dumps({"setup": "created", "project": project, "database": database, "port": port, "secrets": "generated locally; values not displayed"}))


def write_compose_env(state):
    (LOCAL / "compose.env").write_text(f"MP_COMPOSE_PROJECT={state['project']}\nMP_HTTP_PORT={state['port']}\nMP_FIXTURE_VARIANT={state['variant']}\n")


def compose():
    return ["docker", "compose", "--env-file", str(LOCAL / "compose.env"), "-f", str(ROOT / "deploy/compose.yaml")]


def seed_volumes(state):
    """Transfer config over stdin, avoiding Windows host bind mounts entirely."""
    for suffix in ["appconfig", "dbconfig", "bootstrap", "evidence", "proxyconfig"]:
        execute(state, "create-" + suffix, ["docker", "volume", "create", "--label", "com.modular.disposable=" + state["project"], state["project"] + "_" + suffix])
    payload = {
        "appconfig": {"odoo_config": (LOCAL / "odoo.conf").read_text()},
        "dbconfig": {
            "postgres_password": (LOCAL / "postgres-password").read_text(),
            "app_db_password": (LOCAL / "app-db-password").read_text(),
            "init-db.sh": (ROOT / "deploy/init-db.sh").read_text(),
            "postgres-entrypoint.sh": (ROOT / "deploy/postgres-entrypoint.sh").read_text(),
        },
        "bootstrap": {"password": (LOCAL / "bootstrap-password").read_text()},
        "evidence": {},
        "proxyconfig": {"default.conf": (ROOT / "deploy/nginx-r0.conf").read_text()},
    }
    command = ["docker", "run", "--rm", "-i", "--network", "none"]
    for suffix in payload:
        command += ["--mount", f"type=volume,source={state['project']}_{suffix},target=/{suffix}"]
    code = """import json, os, pathlib, sys
for group, files in json.load(sys.stdin).items():
    directory = pathlib.Path('/') / group
    if group == 'evidence':
        os.chown(directory, 10001, 10001)
        os.chmod(directory, 0o770)
    for name, text in files.items():
        path = directory / name
        path.write_text(text)
        os.chmod(path, 0o444)
print('Configuration transferred to separate project volumes; values not displayed')
"""
    command += ["python:3.12-slim-bookworm@sha256:6dd8b6dab6b3adc7812bab69eca5dbdc1a5cc690ad28306d234ffb4ef8ac9753", "python", "-c", code]
    execute(state, "seed-config-volumes", command, input_bytes=json.dumps(payload).encode())


def execute(state, label, command, *, input_bytes=None, binary_path=None, expected_failure=False):
    evidence = ROOT / state["evidence"]
    log = evidence / (now() + "-" + label + ".log")
    started = time.monotonic()
    # Commands contain targets and paths, never secret values.
    with log.open("wb") as handle:
        handle.write(("COMMAND: " + json.dumps(command) + "\n").encode())
        handle.flush()
        if binary_path:
            with binary_path.open("wb") as output:
                result = subprocess.run(command, cwd=ROOT, input=input_bytes, stdout=output, stderr=handle)
        else:
            result = subprocess.run(command, cwd=ROOT, input=input_bytes, stdout=handle, stderr=subprocess.STDOUT)
    record = {"label": label, "exit_code": result.returncode, "duration_seconds": round(time.monotonic() - started, 3), "evidence": str(log.relative_to(ROOT)), "expected_failure": expected_failure}
    print(json.dumps(record), flush=True)
    if (result.returncode != 0) != expected_failure:
        print("\n".join(log.read_text(errors="replace").splitlines()[-25:]), file=sys.stderr)
        raise RuntimeError("Unexpected command outcome; inspect evidence")
    return log


def inside(state, action, *, database=None, variant=None, expected_failure=False, extra_args=None):
    return execute(state, action, compose() + ["run", "--rm", "--no-deps", "maintenance", action, "--database", database or state["active_db"], "--variant", variant or state["variant"]] + (extra_args or []), expected_failure=expected_failure)


def stop(state):
    execute(state, "stop-app", compose() + ["stop", "-t", "20", "edge", "app"])


def http_probe(state, registry_sync=False):
    base = f"http://127.0.0.1:{state['port']}"
    jar = http.cookiejar.CookieJar()
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    deadline = time.monotonic() + 90
    while True:
        try:
            with client.open(base + "/web/login", timeout=5) as response:
                login_html = response.read().decode()
                assert response.status == 200 and 'csrf_token' in login_html
            break
        except Exception:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)

    def rpc(path, params):
        request = urllib.request.Request(base + path, data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params, "id": 1}).encode(), headers={"Content-Type": "application/json"})
        with client.open(request, timeout=60) as response:
            payload = json.load(response)
        if "error" in payload:
            raise RuntimeError(payload["error"].get("message", "RPC failure"))
        return payload.get("result")

    password = (LOCAL / "bootstrap-password").read_text().strip()
    result = rpc("/web/session/authenticate", {"db": state["active_db"], "login": "admin", "password": password})
    assert result.get("uid"), "Login did not return an authenticated user"
    with client.open(base + "/odoo", timeout=90) as response:
        html = response.read().decode()
        assert response.status == 200
    assets = sorted(set(re.findall(r'''(?:src|href)=["']([^"']*/web/assets/[^"']+)["']''', html + login_html)))
    assert assets, "No standard web bundles found"
    fetched = []
    for path in assets:
        if not path.startswith("/"):
            continue
        with client.open(base + path, timeout=90) as response:
            body = response.read()
            assert response.status == 200 and body, path
            if ".css" in path:
                assert len(body) > 10000, "Expected compiled standard style bundle"
                assert b"## CSS error message ##" not in body, "Asset compiler returned fallback error CSS"
            fetched.append({"path": path, "bytes": len(body), "content_type": response.headers.get("Content-Type")})
    timings = []
    for _ in range(20):
        started = time.monotonic()
        assert rpc("/web/session/get_session_info", {}).get("uid")
        timings.append(round((time.monotonic() - started) * 1000, 3))
    registry_evidence = None
    if registry_sync:
        route = "/web/dataset/call_kw/mp.r0.fixture/fields_get"
        params = {"model": "mp.r0.fixture", "method": "fields_get", "args": [], "kwargs": {"attributes": ["type"]}}
        probe = state.get("registry_probe", {})
        if probe.get("database") != state["active_db"] or probe.get("status") == "passed" or not probe:
            probe = {"database": state["active_db"], "field": "x_r0_signal_" + secrets.token_hex(4), "status": "pending"}
            state["registry_probe"] = probe
            save(state)
        field_name = probe["field"]
        before = rpc(route, params)
        since = datetime.now(timezone.utc).isoformat()
        if field_name not in before:
            inside(state, "signal", extra_args=["--probe-field", field_name])
            probe["status"] = "signal_committed"
            save(state)
        elif probe["status"] != "signal_committed":
            raise RuntimeError("Signal outcome needs reconciliation; inspect recorded field and native log")
        cookie = "; ".join(c.name + "=" + c.value for c in jar)
        def read_fields(_):
            connection = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            request = urllib.request.Request(base + route, data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params, "id": 1}).encode(), headers={"Content-Type": "application/json", "Cookie": cookie})
            with connection.open(request, timeout=30) as response:
                payload = json.load(response)
            assert payload.get("result", {}).get(field_name, {}).get("type") == "char"
            return True
        with ThreadPoolExecutor(max_workers=8) as executor:
            assert all(executor.map(read_fields, range(80)))
        log = execute(state, "multiworker-http-logs", compose() + ["logs", "--no-color", "--since", since, "app"])
        pids = sorted(set(re.findall(r"\s(\d+)\s+INFO\s+[^\n]*werkzeug:[^\n]*POST /web/dataset/call_kw/mp.r0.fixture/fields_get", log.read_text(errors="replace"))))
        assert len(pids) >= 2, ("Did not observe both workers serving updated registry", pids)
        probe["status"] = "passed"
        save(state)
        registry_evidence = {"field": field_name, "updated_field_seen_in_responses": 80, "concurrent_clients": 8, "worker_pids": pids, "log": str(log.relative_to(ROOT))}
    rpc("/web/session/destroy", {})
    try:
        rpc("/web/session/check", {})
    except RuntimeError:
        pass
    else:
        raise AssertionError("Destroyed session still authorizes a user endpoint")
    anonymous = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with anonymous.open(base + "/odoo", timeout=10) as response:
        assert "/web/login" in response.geturl()
    denied = {}
    for path, expected in [("/web/database/manager", 403), ("/xmlrpc/2/object", 404), ("/jsonrpc", 404)]:
        try:
            anonymous.open(base + path, timeout=10)
        except urllib.error.HTTPError as error:
            assert error.code == expected, (path, error.code)
            denied[path] = error.code
        else:
            raise AssertionError("Unexpectedly available endpoint: " + path)
    artifact = {"database": state["active_db"], "login": "passed", "logout": "subsequent_authenticated_endpoint_denied", "anonymous_and_omitted_routes": denied, "assets": fetched, "warm_session_ms": {"samples": timings, "p95": sorted(timings)[18]}, "registry_sync": registry_evidence, "source": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "variant": state["variant"]}
    path = ROOT / state["evidence"] / (now() + "-http-probe.json")
    path.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps({"http_probe": "passed", "asset_count": len(fetched), "evidence": str(path.relative_to(ROOT))}))


def backup(state):
    stop(state)
    folder = LOCAL / "backups" / (now() + "-backup")
    folder.mkdir(parents=True)
    dump = folder / "database.dump"
    execute(state, "database-backup", compose() + ["exec", "-T", "db", "pg_dump", "-U", "postgres", "--no-owner", "-Fc", state["active_db"]], binary_path=dump)
    relative = "backups/" + folder.name
    archive = folder / "filestore.tar.gz"
    execute(state, "prepare-backup-path", compose() + ["run", "--rm", "--no-deps", "--entrypoint", "mkdir", "maintenance", "-p", "/evidence/" + relative])
    execute(state, "filestore-backup", compose() + ["run", "--rm", "--no-deps", "--entrypoint", "tar", "maintenance", "-czf", "/evidence/" + relative + "/filestore.tar.gz", "-C", "/var/lib/modular/filestore", state["active_db"]])
    copy_container = state["project"] + "-evidence-copy"
    execute(state, "create-evidence-copy", ["docker", "create", "--name", copy_container, "--mount", f"type=volume,source={state['project']}_evidence,target=/evidence", "--entrypoint", "true", "modular-platform:r0"])
    try:
        execute(state, "copy-filestore-backup", ["docker", "cp", copy_container + ":/evidence/" + relative + "/filestore.tar.gz", str(archive)])
    finally:
        execute(state, "remove-evidence-copy", ["docker", "rm", copy_container])
    metadata = {"database": state["active_db"], "variant": state["variant"], "image_id": subprocess.check_output(["docker", "image", "inspect", "modular-platform:r0", "--format", "{{.Id}}"], text=True).strip(), "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [dump, archive]}, "source": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    (folder / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (ROOT / state["evidence"] / (folder.name + "-manifest.json")).write_text(json.dumps(metadata, indent=2) + "\n")
    state["backup"] = str(folder.relative_to(ROOT))
    save(state)
    print(json.dumps({"backup": state["backup"], "coordinated": "app stopped; cron disabled; internal network"}))


def restore(state):
    stop(state)
    folder = ROOT / state["backup"]
    metadata = json.loads((folder / "manifest.json").read_text())
    current_image = subprocess.check_output(["docker", "image", "inspect", "modular-platform:r0", "--format", "{{.Id}}"], text=True).strip()
    assert current_image == metadata["image_id"], "Restore requires the exact checkpoint runtime image"
    for name, digest in metadata["files"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest
    target = metadata["database"] + "_restore"
    if target in state["databases"]:
        raise RuntimeError("Restore target already reserved; reconcile instead of replaying")
    state["databases"].append(target)
    state["restore_pending"] = target
    save(state)
    execute(state, "create-restore-target", compose() + ["exec", "-T", "db", "createdb", "-U", "postgres", "-O", "modular", target])
    with (folder / "database.dump").open("rb") as dump:
        execute(state, "database-restore", compose() + ["exec", "-T", "db", "pg_restore", "-U", "postgres", "--no-owner", "--role=modular", "-d", target], input_bytes=dump.read())
    statement = f"COMMENT ON DATABASE {target} IS 'modular-platform disposable R0 {target}';"
    execute(state, "mark-restore-target", compose() + ["exec", "-T", "db", "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-c", statement])
    relative = "backups/" + folder.name
    # Only a checksum-verified archive created by this harness is extracted, into
    # a fresh tmpfs directory. Never restore arbitrary user archives this way.
    code = "import pathlib, shutil, subprocess, tempfile; original, target, archive = __import__('sys').argv[1:]; destination=pathlib.Path('/var/lib/modular/filestore')/target; assert not destination.exists(); scratch=tempfile.mkdtemp(); subprocess.run(['tar','-xzf',archive,'-C',scratch],check=True); shutil.copytree(pathlib.Path(scratch)/original,destination)"
    execute(state, "filestore-restore", compose() + ["run", "--rm", "--no-deps", "--entrypoint", "python", "maintenance", "-c", code, metadata["database"], target, "/evidence/" + relative + "/filestore.tar.gz"])
    inside(state, "check-v2", database=target, variant=metadata["variant"])
    state["restored_db"] = target
    state.pop("restore_pending")
    state["stage"] = "restored_verified_offline"
    save(state)
    print(json.dumps({"restore": "verified offline", "target": target, "dispatch": "disabled; not reopened to traffic"}))


def reopen_restored(state):
    """Reopen only the known fixture-restored site after authority rotation."""
    if state["stage"] != "destructive_uninstall_observed":
        raise RuntimeError("Finish offline restoration/uninstall verification before reopening")
    target = state["restored_db"]
    code = """import json, secrets
from pathlib import Path
assert env['ir.config_parameter'].sudo().get_param('mp.r0.database')
assert not env['res.users.apikeys'].search_count([]), 'Unexpected technical credentials require reconciliation'
env.ref('base.user_admin').write({'password': Path('/run/mp-bootstrap/password').read_text().strip()})
env.ref('base.user_root').write({'password': secrets.token_urlsafe(32)})
env['ir.config_parameter'].sudo().set_param('database.secret', secrets.token_hex(32))
env['ir.config_parameter'].sudo().set_param('mp.r0.database', env.cr.dbname)
modules = env['ir.module.module'].search([('name', 'in', ['mp_r0_fixture', 'mp_r0_extension'])])
assert all(m.state == 'uninstalled' for m in modules)
env.cr.commit()
print('MP_R0_RESULT=' + json.dumps({'restored_authority_rotated': True, 'fixture_dependents_uninstalled': True}))
"""
    execute(state, "reopen-authority-check", compose() + ["run", "--rm", "--no-deps", "--entrypoint", "python", "maintenance", "odoo-bin", "shell", "-c", "/run/secrets/odoo_config", "-d", target, "--workers=0", "--no-http", "--max-cron-threads=0", "--addons-path=/opt/modular/addons,/opt/modular/fixtures/v2"], input_bytes=code.encode())
    state["active_db"], state["variant"], state["stage"] = target, "v2", "bootstrapped"
    save(state)
    config = configparser.ConfigParser()
    config.read(LOCAL / "odoo.conf")
    config["options"]["db_name"] = target
    config["options"]["dbfilter"] = "^" + target + "$"
    with (LOCAL / "odoo.conf").open("w") as handle:
        config.write(handle)
    write_compose_env(state)
    seed_volumes(state)
    print(json.dumps({"reopened_target": target, "cron": "disabled", "external_effects": "private runtime network; no mail module"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "seed-volumes", "build", "bootstrap", "install", "inspect", "up", "down", "http", "multiworker", "upgrade", "backup", "fail", "check-partial", "restore", "uninstall-restored", "reopen-restored"])
    args = parser.parse_args()
    if args.action == "setup":
        setup()
        return
    state = load()
    if args.action == "seed-volumes":
        seed_volumes(state)
    elif args.action == "build":
        execute(state, "build", ["docker", "build", "-f", "deploy/Dockerfile", "-t", "modular-platform:r0", "."])
    elif args.action == "bootstrap":
        seed_volumes(state)
        execute(state, "start-db", compose() + ["up", "-d", "--wait", "db"])
        inside(state, "bootstrap")
        state["stage"] = "bootstrapped"
        save(state)
    elif args.action == "up":
        if state["stage"] not in ["bootstrapped", "installed", "upgraded"]:
            raise RuntimeError("Current state is not qualified for traffic")
        execute(state, "start-app", compose() + ["up", "-d", "app", "edge"])
    elif args.action == "down":
        execute(state, "stop", compose() + ["stop"])
    elif args.action == "http":
        http_probe(state)
    elif args.action == "multiworker":
        http_probe(state, registry_sync=True)
    elif args.action == "backup":
        backup(state)
    elif args.action == "restore":
        restore(state)
    elif args.action == "reopen-restored":
        reopen_restored(state)
    elif args.action == "uninstall-restored":
        inside(state, "uninstall", database=state["restored_db"], variant="v2")
        state["stage"] = "destructive_uninstall_observed"
        save(state)
    else:
        if args.action in ["install", "upgrade", "fail"]:
            stop(state)
        result_log = inside(state, args.action, variant="v2" if args.action in ["upgrade", "check-partial"] else None, expected_failure=args.action == "fail")
        if args.action == "install":
            state["stage"] = "installed"
        elif args.action == "upgrade":
            state["stage"], state["variant"] = "upgraded", "v2"
            write_compose_env(state)
            inside(state, "check-v2", variant="v2")
        elif args.action == "fail":
            if "MP_R0 deliberate failure after commit" not in result_log.read_text(errors="replace"):
                raise RuntimeError("Failure did not match the intended injected migration fault")
            state["stage"] = "recovery_required"
        save(state)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if STATE.exists():
            saved = json.loads(STATE.read_text())
            (ROOT / saved["evidence"] / (now() + "-harness-error.log")).write_text(traceback.format_exc())
        raise
