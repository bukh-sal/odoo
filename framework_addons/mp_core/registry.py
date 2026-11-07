"""Explicit registered service seams; never dispatch arbitrary model attributes."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Method:
    model: str
    handler: str
    input_schema: str
    schema_file: str
    permission: str
    mutation: bool
    action: str
    output_schema: dict


SERVICES = {}


def register(service, version, plugin, methods):
    key = service, version, plugin
    if key in SERVICES: raise ValueError('Duplicate registered service')
    if any(not method.handler.startswith('_mp_service_') for method in methods.values()):
        raise ValueError('Only private explicitly registered handlers are supported')
    SERVICES[key] = dict(methods)
