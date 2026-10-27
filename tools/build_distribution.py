"""Materialize a fresh, allowlisted source tree without importing native code."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
from pathlib import Path


def build(source: Path, target: Path) -> dict:
    policy = json.loads((source / "deploy/distribution.json").read_text())
    if target.exists():
        raise ValueError("distribution target must not exist")
    selected = set(policy["addons"])
    manifests = {}
    locations = {}
    for name in sorted(selected):
        choices = [source / "odoo/addons" / name, source / "addons" / name]
        matches = [p for p in choices if (p / "__manifest__.py").is_file()]
        if len(matches) != 1:
            raise ValueError(f"missing or ambiguous addon: {name}")
        locations[name] = matches[0]
        manifest = ast.literal_eval((matches[0] / "__manifest__.py").read_text())
        depends = manifest.get("depends") or ([] if name == "base" else ["base"])
        if not set(depends) <= selected:
            raise ValueError(f"unpackaged dependencies for {name}: {set(depends) - selected}")
        manifests[name] = {"depends": depends, "auto_install": manifest.get("auto_install", False), "license": manifest.get("license", "unspecified")}
    target.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    # The source namespace remains intact; only addon discovery roots are curated.
    shutil.copytree(source / "odoo", target / "odoo", ignore=lambda p, names: set(ignore(p, names)) | ({"addons"} if Path(p) == source / "odoo" else set()))
    (target / "odoo/addons").mkdir()
    (target / "addons").mkdir()
    for name, location in locations.items():
        destination = target / ("odoo/addons" if name == "base" else "addons") / name
        shutil.copytree(location, destination, ignore=ignore)
    for name in ["odoo-bin", "LICENSE", "COPYRIGHT", "requirements.txt"]:
        shutil.copy2(source / name, target / name)
    inventory = {"policy": policy, "native_addons": manifests, "files": {}}
    for path in sorted(target.rglob("*")):
        if path.is_file():
            inventory["files"][path.relative_to(target).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (target / "distribution-inventory.json").write_text(json.dumps(inventory, sort_keys=True, indent=2) + "\n")
    return inventory


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    result = build(args.source.resolve(), args.target.resolve())
    print(json.dumps({"addons": sorted(result["native_addons"]), "file_count": len(result["files"])}))
