"""Minimal registered Notes domain events; content stays in the host database."""
import json
from modular_platform.contracts import CONTRACTS,ContractError
from odoo.exceptions import AccessError
from odoo.addons.mp_core.events import Topic,register_topic


def authorize(env,event,bound):
    scope=bound.model._mp_guard('read')
    if (event['workspace_id'],event['site_id'])!=(scope.workspace_id,bound.binding['site_id']):raise AccessError('Event scope mismatch')
    # R1 Notes read authority covers all minimized history in this workspace.
    # Creation/update events remain readable after deletion; a vanished current
    # row must not permanently obstruct its later deletion event. No content is
    # emitted, and native record APIs still enforce current record ownership.


def identity(aggregate_id,sequence,payload):
    if (aggregate_id,sequence)!=(payload['note_id'],payload['revision']):raise ContractError('Inconsistent Notes event identity/revision')


register_topic(Topic(ident='org.example.notes.changed',plugin='org.example.notes',model='mp.example.note',
    service='org.example.notes.documents',majors=(1,2),permission='org.example.notes:notes.read',
    payload_schema=json.loads((CONTRACTS/'event-transport.schema.json').read_text())['$defs']['notes_changed_payload'],authorize_event=authorize,validate_identity=identity))
