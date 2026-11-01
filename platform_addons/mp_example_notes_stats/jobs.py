"""Read-only, revision-bound external analysis through existing durable jobs."""
from odoo.addons.mp_core.controllers import PublicError
from odoo.addons.mp_core.dispatch import call_bound
from odoo.addons.mp_core.external_job import analyze
from odoo.addons.mp_core.job_dispatch import JobDefinition,register
from .contracts import INPUT,PREPARED,STATISTICS,RESULT
from .models import guard,IDENT


def resource(env,values,bound):
    guard(bound.model)
    return call_bound(bound.model.env,'documents','get',dict(note_id=values['note_id']))


def prepare(env,values,bound):
    note=resource(env,values,bound)
    if note['revision']!=values['expected_revision']:raise PublicError('CONFLICT')
    return dict(input=dict(text=note['body'],note_id=note['id'],expected_revision=note['revision']))


def apply(env,values,prepared,computed,bound):
    if prepare(env,values,bound)!=prepared:raise PublicError('CONFLICT')
    return dict(note_id=values['note_id'],revision=values['expected_revision'],statistics=computed)


register(JobDefinition(ident=IDENT,version=1,plugin='org.example.notes_stats',
    service='org.example.notes_stats.jobs',api_version='1.0',method='status',
    input_schema=INPUT,prepared_schema=PREPARED,computed_schema=STATISTICS,output_schema=RESULT,
    authorize_resource=resource,prepare=prepare,compute=analyze,apply=apply))
