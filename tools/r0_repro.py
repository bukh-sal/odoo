"""Prove a second uncached build and fresh database reproduce R0 inventories."""
from __future__ import annotations

import json
from pathlib import Path

import r0


def result(log: Path):
    matches = [line.split("MP_R0_RESULT=", 1)[1] for line in log.read_text(errors="replace").splitlines() if line.startswith("MP_R0_RESULT=")]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one structured probe result")
    return json.loads(matches[0])


def main():
    state = r0.load()
    if state.get("repro_db"):
        raise RuntimeError("Reproduction target already reserved; inspect its evidence before any new run")
    image = "modular-platform:r0-repro-" + state["run_id"]
    r0.execute(state, "uncached-reproduction-build", ["docker", "build", "--no-cache", "-f", "deploy/Dockerfile", "-t", image, "."])
    code = """import hashlib, importlib.metadata, json, pathlib, sys
root=pathlib.Path('/opt/modular')
files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
result={'python':sys.version.split()[0], 'runtime_tree_sha256':hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest(), 'file_count':len(files), 'packages':sorted((d.metadata['Name'].lower(),d.version) for d in importlib.metadata.distributions())}
print('MP_R0_RESULT='+json.dumps(result,sort_keys=True))
"""
    inventories = []
    for label, target_image in [("primary", "modular-platform:r0"), ("reproduction", image)]:
        log = r0.execute(state, label + "-image-inventory", ["docker", "run", "--rm", "--network", "none", "--entrypoint", "python", target_image, "-c", code])
        inventories.append(result(log))
    assert inventories[0] == inventories[1], "Independent image inventories differ; inspect before qualification"
    database = "mp_disposable_r0_" + state["run_id"] + "_fresh"
    state["repro_db"] = database
    state["databases"].append(database)
    state["repro_stage"] = "fresh_database_pending"
    r0.save(state)
    # Compose run --entrypoint retains service volumes/network; run the second
    # image explicitly with the same narrow mounts, without replacing primary.
    command = ["docker", "run", "--rm", "--network", state["project"] + "_runtime", "--mount", f"type=volume,source={state['project']}_appconfig,target=/run/secrets,readonly", "--mount", f"type=volume,source={state['project']}_bootstrap,target=/run/mp-bootstrap,readonly", "--mount", f"type=volume,source={state['project']}_filestore,target=/var/lib/modular", "--entrypoint", "python", image, "/opt/modular/tools/r0_inside.py"]
    r0.execute(state, "reproduction-fresh-bootstrap", command + ["bootstrap", "--database", database])
    fresh = result(r0.execute(state, "reproduction-installed-inventory", command + ["inspect", "--database", database]))
    current = result(r0.inside(state, "inspect"))
    expected = set(json.loads((r0.ROOT / "deploy/distribution.json").read_text())["addons"])
    assert set(fresh["installed"]) == expected
    assert fresh["installed"] == current["installed"]
    assert not fresh["nonfinal"] and not current["nonfinal"]
    # Native registry objects and parameter values must remain database-specific.
    probe = f"""import json
from odoo.orm.registry import Registry
from odoo import api, SUPERUSER_ID
first=Registry({state['active_db']!r}); second=Registry({database!r})
assert first is not second
observed=[]
for registry in [first,second]:
    with registry.cursor() as cr:
        e=api.Environment(cr,SUPERUSER_ID,{{}})
        observed.append(e['ir.config_parameter'].sudo().get_param('mp.r0.database'))
assert observed == [{state['active_db']!r},{database!r}], observed
print('MP_R0_RESULT='+json.dumps({{'registry_database_isolation':True,'databases':observed}}))
"""
    r0.execute(state, "two-database-registry-proof", r0.compose() + ["run", "--rm", "--no-deps", "--entrypoint", "python", "maintenance", "odoo-bin", "shell", "-c", "/run/secrets/odoo_config", "-d", state["active_db"], "--no-http", "--workers=0", "--max-cron-threads=0", "--addons-path=/opt/modular/addons,/opt/modular/fixtures/v2"], input_bytes=probe.encode())
    summary = {"independent_build_inventory_equal": True, "fresh_database_inventory_equal": True, "expected_addons": sorted(expected), "image_inventory": inventories[0], "reproduction_image": image, "fresh_database": database}
    path = r0.ROOT / state["evidence"] / (r0.now() + "-reproduction-summary.json")
    path.write_text(json.dumps(summary, indent=2) + "\n")
    state["repro_stage"] = "passed"
    r0.save(state)
    print(json.dumps({"reproduction": "passed", "evidence": str(path.relative_to(r0.ROOT))}))


if __name__ == "__main__":
    main()
