"""Connector-owned schemas reuse the unchanged frozen document/worker shapes."""
import copy
import json
from modular_platform.contracts import CONTRACTS

DOCUMENTS=json.loads((CONTRACTS/'documents.schema.json').read_text())['$defs']
WORKER_INPUT=json.loads((CONTRACTS/'worker-request.schema.json').read_text())['properties']['input']
STATISTICS=json.loads((CONTRACTS/'worker-response.schema.json').read_text())['properties']['data']
INPUT=copy.deepcopy(DOCUMENTS['delete_input'])
STATUS_INPUT=copy.deepcopy(DOCUMENTS['get_input'])

def obj(properties):
    return dict(type='object',properties=properties,required=list(properties),additionalProperties=False)

PREPARED=obj(dict(input=WORKER_INPUT))
COMPUTED=obj(dict(statistics=STATISTICS,authority_digest=dict(type='string',pattern='^sha256:[0-9a-f]{64}$')))
RESULT=obj(dict(note_id=INPUT['properties']['note_id'],revision=INPUT['properties']['expected_revision'],statistics=STATISTICS))
JOB=obj(dict(id=INPUT['properties']['note_id'],
    state=dict(enum=['pending','retry','running','held','outcome_unknown','completed','cancelled','dead_letter']),
    progress=dict(type='integer',minimum=0,maximum=100),attempts=dict(type='integer',minimum=0,maximum=16),
    error_code=dict(anyOf=[dict(type='null'),dict(enum=['NOT_FOUND','DEPENDENCY_UNAVAILABLE','PLUGIN_SUSPENDED','CONFLICT','DEADLINE_EXCEEDED','CANCELLED','FORBIDDEN','VALIDATION_FAILED','INTERNAL_ERROR','LEASE_EXPIRED'])]),
    result=dict(anyOf=[dict(type='null'),RESULT])))
OUTPUT=obj(dict(job=dict(anyOf=[dict(type='null'),JOB])))
