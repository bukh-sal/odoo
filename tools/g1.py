"""Small G1 proof runner; reuse isolated R0 transport without touching its site."""
from __future__ import annotations

import argparse
import configparser
import json
import secrets
import subprocess
import sys
from pathlib import Path

import r0

r0.LOCAL = r0.ROOT / ".local/g1"
r0.STATE = r0.LOCAL / "state.json"
original_compose_env = r0.write_compose_env


def compose_env(state):
    original_compose_env(state)
    with (r0.LOCAL / "compose.env").open("a") as handle:
        handle.write("MP_IMAGE=modular-platform:g1\n")


r0.write_compose_env = compose_env


def setup():
    if not r0.STATE.exists():
        r0.setup()
        state = r0.load()
        nonce = secrets.token_hex(6)
        state.update(profile="G1", project="mp-r0-g1" + nonce, active_db="mp_disposable_r0_g1_" + nonce, databases=["mp_disposable_r0_g1_" + nonce], image="modular-platform:g1", evidence="docs/evidence/G1/" + state["run_id"])
        (r0.ROOT / state["evidence"]).mkdir(parents=True)
        r0.save(state)
        config = configparser.ConfigParser()
        config.read(r0.LOCAL / "odoo.conf")
        config["options"]["db_name"] = state["active_db"]
        config["options"]["dbfilter"] = "^" + state["active_db"] + "$"
        with (r0.LOCAL / "odoo.conf").open("w") as handle:
            config.write(handle)
        (r0.LOCAL / "service-token").write_text(secrets.token_urlsafe(48) + "\n")
        compose_env(state)
    state = r0.load()
    if state.get("profile") != "G1":
        raise RuntimeError("Unexpected proof state")
    print(json.dumps({"profile": "G1", "project": state["project"], "database": state["active_db"], "port": state["port"]}))
    return state


def seed(state):
    r0.seed_volumes(state)
    code = "import pathlib,sys; p=pathlib.Path('/bootstrap/service_token'); p.write_bytes(sys.stdin.buffer.read()); p.chmod(0o444); print('Technical proof credential staged; value not displayed')"
    r0.execute(state, "seed-technical-credential", ["docker", "run", "--rm", "-i", "--network", "none", "--mount", f"type=volume,source={state['project']}_bootstrap,target=/bootstrap", "python:3.12-slim-bookworm@sha256:6dd8b6dab6b3adc7812bab69eca5dbdc1a5cc690ad28306d234ffb4ef8ac9753", "python", "-c", code], input_bytes=(r0.LOCAL / "service-token").read_bytes())


def shell(state, label, code):
    return r0.execute(state, label, r0.compose() + ["run", "--rm", "--no-deps", "--entrypoint", "python", "maintenance", "odoo-bin", "shell", "-c", "/run/secrets/odoo_config", "-d", state["active_db"], "--no-http", "--workers=0", "--max-cron-threads=0"], input_bytes=code.encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["setup", "build", "init", "seed", "up", "down", "renew-credential"])
    args = parser.parse_args()
    state = setup()
    if args.action == "setup":
        return
    if args.action == "build":
        r0.execute(state, "g1-build", ["docker", "build", "-f", "deploy/Dockerfile", "--build-arg", "DISTRIBUTION_POLICY=deploy/distribution-g1.json", "-t", "modular-platform:g1", "."])
    elif args.action == "init":
        if state.get("g1_install_status"):
            raise RuntimeError("G1 installation already attempted; inspect/reconcile instead of blindly replaying")
        seed(state)
        r0.execute(state, "g1-db", r0.compose() + ["up", "-d", "--wait", "db"])
        r0.inside(state, "bootstrap")
        state["g1_install_status"] = "installing"
        r0.save(state)
        r0.execute(state, "g1-install", r0.compose() + ["run", "--rm", "--no-deps", "--entrypoint", "python", "maintenance", "odoo-bin", "-c", "/run/secrets/odoo_config", "-d", state["active_db"], "-i", "mp_feas", "--stop-after-init", "--no-http", "--workers=0", "--without-demo"])
        state["g1_install_status"] = "installed_unseeded"
        r0.save(state)
    elif args.action == "seed":
        if state.get("g1_install_status") != "installed_unseeded":
            raise RuntimeError("Provisioning requires an installed, unseeded proof site")
        log = shell(state, "g1-provision", (r0.ROOT / "tools/g1_seed.py").read_text())
        results = [line.split("MP_G1_RESULT=", 1)[1] for line in log.read_text(errors="replace").splitlines() if line.startswith("MP_G1_RESULT=")]
        if len(results) != 1:
            raise RuntimeError("Uncertain fixture provisioning; inspect native log before retry")
        (r0.LOCAL / "fixtures.json").write_text(json.dumps(json.loads(results[0]), indent=2) + "\n")
        state["g1_install_status"] = "seeded"
        r0.save(state)
    elif args.action == "up":
        if state.get("g1_install_status") != "seeded":
            raise RuntimeError("Proof site is not provisioned")
        r0.execute(state, "g1-up", r0.compose() + ["up", "-d", "app", "edge"])
    elif args.action == "down":
        r0.execute(state, "g1-stop", r0.compose() + ["stop"])
    elif args.action == "renew-credential":
        fixture = json.loads((r0.LOCAL / "fixtures.json").read_text())
        shell(state, "g1-renew-proof-credential", f"from datetime import timedelta\nfrom odoo import fields\nc=env['mp.service.credential'].browse({fixture['credential_id']!r})\nassert c.name == 'G1 restricted worker'\nc.write({{'expires_at':fields.Datetime.now()+timedelta(minutes=5),'state':'active'}})\nenv.cr.commit()\nprint('MP_G1_RESULT=credential-renewed')\n")


if __name__ == "__main__":
    main()
