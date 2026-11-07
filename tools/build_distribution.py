"""Materialize a fresh, allowlisted source tree without importing native code."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import tempfile
import sys
from pathlib import Path


def build(source: Path, target: Path, policy_path="deploy/distribution.json") -> dict:
    policy_file = (source / policy_path).resolve()
    if not policy_file.is_relative_to(source):
        raise ValueError("distribution policy must be within the source tree")
    policy = json.loads(policy_file.read_text())
    if target.exists():
        raise ValueError("distribution target must not exist")
    selected = set(policy["addons"])
    reference_stage=tempfile.TemporaryDirectory(prefix='mp-reference-') if policy.get('reference_packages') else None
    references={};artifacts={}
    if reference_stage:
        assert Path(reference_stage.name).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
        from reference_package import materialize_reference,validate_reference_composition
        for manifest_path in policy['reference_packages']:
            descriptor,raw,location=materialize_reference(source,manifest_path,Path(reference_stage.name))
            if descriptor['addon'] in references:raise ValueError('Duplicate reference package addon')
            references[descriptor['addon']]=location;artifacts[descriptor['plugin_id']]={**descriptor,'bytes':raw}
        reference_registry=validate_reference_composition([item['bytes'] for item in artifacts.values()])
    manifests = {}
    locations = {}
    for name in sorted(selected):
        choices = [references[name]] if name in references else [source / "odoo/addons" / name, source / "addons" / name, source / "platform_addons" / name, source / "applications" / name]
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
    if artifacts:
        (target/'artifacts').mkdir()
        for item in artifacts.values():(target/'artifacts'/item['file']).write_bytes(item['bytes'])
    for name, location in locations.items():
        destination = target / ("odoo/addons" if name == "base" else "addons") / name
        shutil.copytree(location, destination, ignore=ignore)
    for name in ["odoo-bin", "LICENSE", "COPYRIGHT", "requirements.txt"]:
        shutil.copy2(source / name, target / name)
    if policy.get("platform_sdk"):
        for name in ["platform_sdk", "contracts"]:
            shutil.copytree(source / "packages" / name, target / "packages" / name, ignore=ignore)
    generated_patches=[]
    if policy.get('platform_sdk'):
        sys.path.insert(0,str(source/'packages/platform_sdk'))
        from modular_platform.native_versions import PARSER_PATH,corrected_parser,patch_record
        parser_file=target/PARSER_PATH
        parser_file.write_bytes(corrected_parser(parser_file.read_bytes()))
        generated_patches.append(patch_record())
    inventory = {"policy": policy, "native_addons": manifests, "generated_patches": generated_patches, "files": {}}
    if artifacts:inventory['artifacts']={key:{name:value for name,value in item.items() if name!='bytes'} for key,item in artifacts.items()}
    if artifacts:inventory['reference_composition']=reference_registry
    for path in sorted(target.rglob("*")):
        if path.is_file():
            inventory["files"][path.relative_to(target).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (target / "distribution-inventory.json").write_text(json.dumps(inventory, sort_keys=True, indent=2) + "\n", newline="\n")
    return inventory


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--policy", default="deploy/distribution.json")
    args = parser.parse_args()
    result = build(args.source.resolve(), args.target.resolve(), args.policy)
    print(json.dumps({"addons": sorted(result["native_addons"]), "file_count": len(result["files"])}))
