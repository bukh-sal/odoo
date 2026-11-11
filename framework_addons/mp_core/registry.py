"""Explicit registered service seams; never dispatch arbitrary model attributes."""
from dataclasses import dataclass
import copy
import json
from jsonschema import Draft202012Validator
from modular_platform.artifacts import ArtifactValidator
from modular_platform.contracts import CONTRACTS, checked_path


@dataclass(frozen=True)
class Method:
    model: str
    handler: str
    input_schema: str | dict
    schema_file: str | None
    permission: str
    mutation: bool
    action: str
    output_schema: dict


SERVICES = {}


def input_schema_for(method):
    """App-owned literal schemas or the existing registered core definitions.

    Only trusted addon registration supplies these values, never HTTP input.
    App schemas retain their own $defs; validation performs no remote lookup.
    """
    if isinstance(method.input_schema, dict):
        if method.schema_file is not None:
            raise ValueError('Owned input schema cannot also select a core schema file')
        schema = copy.deepcopy(method.input_schema)
        Draft202012Validator.check_schema(schema)
        # The same local-reference policy already owns packaged app schemas.
        ArtifactValidator._local_refs(schema)
        return schema
    if not isinstance(method.input_schema, str) or not isinstance(method.schema_file, str):
        raise ValueError('Registered input schema required')
    name = checked_path(method.schema_file)
    return json.loads((CONTRACTS / name).read_text())['$defs'][method.input_schema]


def register(service, version, plugin, methods):
    key = service, version, plugin
    if key in SERVICES: raise ValueError('Duplicate registered service')
    if any(not method.handler.startswith('_mp_service_') for method in methods.values()):
        raise ValueError('Only private explicitly registered handlers are supported')
    for method in methods.values():
        if isinstance(method.input_schema, dict):
            input_schema_for(method)
    SERVICES[key] = dict(methods)
