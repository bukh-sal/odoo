"""Materialize a fresh, allowlisted source tree without importing native code."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import shutil
import tempfile
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def seed_category_metadata(category_file: Path, catalog_file: Path) -> list[str]:
    """Retain catalog references whose categories excluded addon scans created."""
    text = category_file.read_text()
    tree = ET.fromstring(text)
    known = {record.attrib["id"].removeprefix("base.") for record in tree.iter("record") if record.attrib.get("model") == "ir.module.category"}
    referenced = {field.attrib["ref"].removeprefix("base.") for field in ET.parse(catalog_file).iter("field") if field.attrib.get("name") == "category_id" and field.attrib.get("ref", "").startswith("base.module_category_")}
    missing = sorted(referenced - known)
    records = []
    for ident in missing:
        parents = [p for p in known if ident.startswith(p + "_")]
        parent = max(parents, key=len) if parents else None
        suffix = ident[len(parent) + 1:] if parent else ident.removeprefix("module_category_")
        record = ET.Element("record", {"model": "ir.module.category", "id": ident})
        ET.SubElement(record, "field", {"name": "name"}).text = suffix.replace("_", " ").title()
        if parent:
            ET.SubElement(record, "field", {"name": "parent_id", "ref": parent})
        records.append(ET.tostring(record, encoding="unicode"))
        known.add(ident)
    if records:
        addition = "\n        <!-- Modular Platform: metadata retained for excluded addon categories. -->\n        " + "\n        ".join(records) + "\n    "
        if text.count("</data>") != 1:
            raise ValueError("Unexpected upstream category data layout")
        category_file.write_text(text.replace("</data>", addition + "</data>"), newline="\n")
    return missing


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
        choices = [references[name]] if name in references else [source / "odoo/addons" / name, source / "addons" / name, source / "platform_addons" / name]
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
    category_file = target / "odoo/addons/base/data/ir_module_category_data.xml"
    category_hash = hashlib.sha256(category_file.read_bytes()).hexdigest()
    seeded = seed_category_metadata(category_file, target / "odoo/addons/base/data/ir_module_module.xml")
    generated_patches=[{"path": "odoo/addons/base/data/ir_module_category_data.xml", "source_sha256": category_hash, "seeded_categories": seeded}]
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
