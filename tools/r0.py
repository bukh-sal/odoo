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
import urllib.request
from datetime import datetime, timezone
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


def inside(state, action, *, database=None, variant=None, expected_failure=False):
    return execute(state, action, compose() + ["run", "--rm", "--no-deps", "maintenance", action, "--database", database or state["active_db"], "--variant", variant or state["variant"]], expected_failure=expected_failure)


def stop(state):
    execute(state, "stop-app", compose() + ["stop", "-t", "20", "app"])


def http_probe(state):
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
        return payload["result"]

    password = (LOCAL / "bootstrap-password").read_text().strip()
    result = rpc("/web/session/authenticate", {"db": state["active_db"], "login": "admin", "password": password})
    assert result.get("uid"), "Login did not return an authenticated user"
    with client.open(base + "/odoo", timeout=90) as response:
        html = response.read().decode()
        assert response.status == 200
    assets = sorted(set(re.findall(r'''(?:src|href)=["']([^"']*/web/assets/[^"']+)["']''', html)))
    assert assets, "No standard web bundles found"
    fetched = []
    for path in assets:
        if not path.startswith("/"):
            continue
        with client.open(base + path, timeout=90) as response:
            body = response.read()
            assert response.status == 200 and body, path
            fetched.append({"path": path, "bytes": len(body), "content_type": response.headers.get("Content-Type")})
    rpc("/web/session/destroy", {})
    artifact = {"database": state["active_db"], "login": "passed", "logout": "session_destroy_returned", "assets": fetched, "source": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "variant": state["variant"]}
    path = ROOT / state["evidence"] / (now() + "-http-probe.json")
    path.write_text(json.dumps(artifact, indent=2) + "\n")
    print(json.dumps({"http_probe": "passed", "asset_count": len(fetched), "evidence": str(path.relative_to(ROOT))}))


def backup(state):
    stop(state)
    folder = ROOT / state["evidence"] / (now() + "-backup")
    folder.mkdir()
    dump = folder / "database.dump"
    execute(state, "database-backup", compose() + ["exec", "-T", "db", "pg_dump", "-U", "postgres", "--no-owner", "-Fc", state["active_db"]], binary_path=dump)
    relative = folder.relative_to(ROOT / "docs/evidence/G0").as_posix()
    archive = folder / "filestore.tar.gz"
    execute(state, "filestore-backup", compose() + ["run", "--rm", "--no-deps", "--entrypoint", "tar", "maintenance", "-czf", "/evidence/" + relative + "/filestore.tar.gz", "-C", "/var/lib/modular/filestore", state["active_db"]])
    metadata = {"database": state["active_db"], "variant": state["variant"], "image_id": subprocess.check_output(["docker", "image", "inspect", "modular-platform:r0", "--format", "{{.Id}}"], text=True).strip(), "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [dump, archive]}, "source": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    (folder / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    state["backup"] = str(folder.relative_to(ROOT))
    save(state)
    print(json.dumps({"backup": state["backup"], "coordinated": "app stopped; cron disabled; internal network"}))


def restore(state):
    stop(state)
    folder = ROOT / state["backup"]
    metadata = json.loads((folder / "manifest.json").read_text())
    for name, digest in metadata["files"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest
    target = "mp_disposable_r0_" + state["run_id"] + "_restore"
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
    relative = folder.relative_to(ROOT / "docs/evidence/G0").as_posix()
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "build", "bootstrap", "install", "inspect", "up", "down", "http", "upgrade", "backup", "fail", "check-partial", "restore", "uninstall-restored"])
    args = parser.parse_args()
    if args.action == "setup":
        setup()
        return
    state = load()
    if args.action == "build":
        execute(state, "build", ["docker", "build", "-f", "deploy/Dockerfile", "-t", "modular-platform:r0", "."])
    elif args.action == "bootstrap":
        execute(state, "start-db", compose() + ["up", "-d", "--wait", "db"])
        inside(state, "bootstrap")
        state["stage"] = "bootstrapped"
        save(state)
    elif args.action == "up":
        if state["stage"] not in ["bootstrapped", "installed", "upgraded"]:
            raise RuntimeError("Current state is not qualified for traffic")
        execute(state, "start-app", compose() + ["up", "-d", "app"])
    elif args.action == "down":
        execute(state, "stop", compose() + ["stop"])
    elif args.action == "http":
        http_probe(state)
    elif args.action == "backup":
        backup(state)
    elif args.action == "restore":
        restore(state)
    elif args.action == "uninstall-restored":
        inside(state, "uninstall", database=state["restored_db"], variant="v2")
        state["stage"] = "destructive_uninstall_observed"
        save(state)
    else:
        if args.action in ["install", "upgrade", "fail"]:
            stop(state)
        inside(state, args.action, variant="v2" if args.action in ["upgrade", "check-partial"] else None, expected_failure=args.action == "fail")
        if args.action == "install":
            state["stage"] = "installed"
        elif args.action == "upgrade":
            state["stage"], state["variant"] = "upgraded", "v2"
            write_compose_env(state)
            inside(state, "check-v2", variant="v2")
        elif args.action == "fail":
            state["stage"] = "recovery_required"
        save(state)


if __name__ == "__main__":
    main()
