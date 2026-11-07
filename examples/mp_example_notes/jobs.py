"""Small native reference jobs; no new document API or custom CRUD screen."""
from odoo.addons.mp_core.controllers import PublicError
from odoo.addons.mp_core.job_dispatch import JobDefinition, register

UUID={'type':'string','pattern':r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![\s\S])'}
REVISION={'type':'integer','minimum':1,'maximum':9007199254740991}


def schema(properties):
    return dict(type='object',properties=properties,required=list(properties),additionalProperties=False)


INPUT=schema(dict(note_id=UUID,expected_revision=REVISION))
IDENTITY=schema(dict(note_id=UUID,revision=REVISION))
PREPARED=schema(dict(note_id=UUID,revision=REVISION,title=dict(type='string',minLength=1,maxLength=200)))
COMPUTED=schema(dict(title=dict(type='string',minLength=1,maxLength=200)))
NORMALIZED=schema(dict(note_id=UUID,revision=REVISION,changed=dict(type='boolean')))


def resource(env,values,bound):
    return bound.model._by_public(values['note_id'],bound.spec.action)


def prepare_revision(env,values,bound):
    note=resource(env,values,bound)
    if note.revision!=values['expected_revision']:raise PublicError('CONFLICT')
    return dict(note_id=note.public_id,revision=note.revision)


def prepare_title(env,values,bound):
    identity=prepare_revision(env,values,bound)
    return dict(identity,title=resource(env,values,bound).title)


def apply_revision(env,values,prepared,computed,bound):
    current=prepare_revision(env,values,bound)
    if current!=prepared or computed!=prepared:raise PublicError('CONFLICT')
    return current


def apply_title(env,values,prepared,computed,bound):
    current=prepare_title(env,values,bound)
    if current!=prepared:raise PublicError('CONFLICT')
    if computed['title']==current['title']:
        return dict(note_id=current['note_id'],revision=current['revision'],changed=False)
    result=bound.invoke(dict(note_id=values['note_id'],expected_revision=values['expected_revision'],title=computed['title']))
    return dict(note_id=result['id'],revision=result['revision'],changed=True)


register(JobDefinition(
    ident='org.example.notes:inspect_revision',version=1,plugin='org.example.notes',
    service='org.example.notes.documents',api_version='1.0',method='get',
    input_schema=INPUT,prepared_schema=IDENTITY,computed_schema=IDENTITY,output_schema=IDENTITY,
    authorize_resource=resource,prepare=prepare_revision,compute=lambda value,context:value,apply=apply_revision))
register(JobDefinition(
    ident='org.example.notes:normalize_title',version=1,plugin='org.example.notes',
    service='org.example.notes.documents',api_version='1.0',method='update',
    input_schema=INPUT,prepared_schema=PREPARED,computed_schema=COMPUTED,output_schema=NORMALIZED,
    authorize_resource=resource,prepare=prepare_title,compute=lambda value,context:dict(title=' '.join(value['title'].split())),apply=apply_title))
