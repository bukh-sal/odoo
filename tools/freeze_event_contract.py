"""Once-only additive G2 revision13 materialization, before event consumers."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONTRACTS=ROOT/'packages/contracts/v1';EXAMPLES=ROOT/'packages/contracts/examples/v1'
freeze_path=ROOT/'docs/contracts/freeze-v1.json';freeze=json.loads(freeze_path.read_text())
assert freeze['revision']==12 and len(freeze['files'])==87
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())

def write(path,value):
    assert not path.exists();path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')

uuid=json.loads((CONTRACTS/'binding.schema.json').read_text())['properties']['binding_id']
plugin=json.loads((CONTRACTS/'binding.schema.json').read_text())['properties']['provider_plugin_id']
topic=dict(type='string',maxLength=200,pattern=r'^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*){2,15}(?![\s\S])')
utc=dict(type='string',format='date-time',maxLength=35,pattern=r'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z(?![\s\S])')
integer=lambda lo=0,hi=9007199254740991:dict(type='integer',minimum=lo,maximum=hi)
ref=lambda name:{'$ref':'#/$defs/'+name}
array=lambda schema,lo=0,hi=50,unique=False:dict(type='array',items=schema,minItems=lo,maxItems=hi,**({'uniqueItems':True} if unique else {}))
obj=lambda properties:dict(type='object',properties=properties,required=list(properties),additionalProperties=False)
definitions={}
definitions['json_value']={'anyOf':[{'type':'null'},{'type':'boolean'},dict(type='number',minimum=-9007199254740991,maximum=9007199254740991),dict(type='string',maxLength=2048),array(ref('json_value'),hi=32),dict(type='object',maxProperties=32,additionalProperties=ref('json_value'))]}
definitions['notes_changed_payload']=obj(dict(note_id=uuid,revision=integer(1),change=dict(enum=['created','updated','deleted'])))
definitions['event']=obj(dict(id=uuid,topic=topic,schema_version=integer(1,1000),owner_plugin_id=plugin,aggregate_id=uuid,aggregate_sequence={'anyOf':[{'type':'null'},integer(1)]},site_id=uuid,workspace_id=uuid,occurred_at=utc,correlation_id=uuid,causation_id={'anyOf':[{'type':'null'},uuid]},payload=dict(type='object',maxProperties=32,additionalProperties=ref('json_value'))))
definitions['event']['allOf']=[dict(**{'if':dict(properties=dict(topic=dict(const='org.example.notes.changed'))),'then':dict(properties=dict(schema_version=dict(type='integer',const=1),owner_plugin_id=dict(const='org.example.notes'),payload=ref('notes_changed_payload')))})]
definitions['receipt']=obj(dict(delivery_id=uuid,receipt=uuid,generation=integer(1)))
definitions['delivery']=obj(dict(id=uuid,receipt=uuid,generation=integer(1),attempt=integer(1,5),lease_expires_at=utc,event=ref('event')))
definitions['delivery_status']=obj(dict(id=uuid,event_id=uuid,state=dict(enum=['pending','leased','acknowledged','dead_letter']),attempts=integer(0,5),replays=integer(0,3),error_code=dict(enum=[None,'ACK_EXPIRED','CONSUMER_FAILED'])))

def message(kind,**properties):
    return obj(dict(protocol=dict(type='integer',const=1),kind=dict(const=kind),**properties))

for operation in ['subscribe','poll','ack','status','replay','close']:
    props=dict(request_id=uuid)
    if operation=='subscribe':props.update(topic=topic,idempotency_key=uuid)
    else:props['subscription_id']=uuid
    if operation=='poll':props['limit']=integer(1,50)
    if operation=='ack':props['receipts']=array(ref('receipt'),1,unique=True)
    if operation=='replay':props['event_ids']=array(uuid,1,unique=True)
    definitions[operation+'_request']=message(operation+'_request',**props)

definitions['subscribe_result']=message('subscribe_result',subscription_id=uuid,topic=topic,expires_at=utc,replay_window_seconds=dict(type='integer',const=604800),ack_lease_seconds=dict(type='integer',const=15),max_attempts=dict(type='integer',const=5),max_replays=dict(type='integer',const=3))
definitions['poll_result']=message('poll_result',subscription_id=uuid,deliveries=array(ref('delivery')),has_more=dict(type='boolean'),dead_letter_count=integer(),next_poll_ms=integer(1000,10000))
definitions['ack_result']=message('ack_result',subscription_id=uuid,acknowledged=array(uuid,unique=True))
definitions['status_result']=message('status_result',subscription_id=uuid,state=dict(enum=['active','closed','expired']),deliveries=array(ref('delivery_status')),truncated=dict(type='boolean'))
definitions['replay_result']=message('replay_result',subscription_id=uuid,replayed=array(uuid,unique=True))
definitions['close_result']=message('close_result',subscription_id=uuid,closed=dict(const=True))
schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'https://modularplatform.invalid/contracts/v1/event-transport.schema.json','oneOf':[ref(k) for k in definitions if k.endswith(('_request','_result'))],'$defs':definitions}
write(CONTRACTS/'event-transport.schema.json',schema)

u=lambda number:f'00000000-0000-4000-8000-{number:012d}'
event=dict(id=u(1),topic='org.example.notes.changed',schema_version=1,owner_plugin_id='org.example.notes',aggregate_id=u(2),aggregate_sequence=2,site_id=u(3),workspace_id=u(4),occurred_at='2026-10-29T15:00:00Z',correlation_id=u(5),causation_id=None,payload=dict(note_id=u(2),revision=2,change='updated'))
receipt=dict(delivery_id=u(6),receipt=u(7),generation=1)
valid={}
for operation in ['subscribe','poll','ack','status','replay','close']:
    values=dict(protocol=1,kind=operation+'_request',request_id=u(8))
    if operation=='subscribe':values.update(topic=event['topic'],idempotency_key=u(9))
    else:values['subscription_id']=u(10)
    if operation=='poll':values['limit']=50
    if operation=='ack':values['receipts']=[receipt]
    if operation=='replay':values['event_ids']=[event['id']]
    valid[operation+'_request']=values
valid['subscribe_result']=dict(protocol=1,kind='subscribe_result',subscription_id=u(10),topic=event['topic'],expires_at='2026-10-29T16:00:00Z',replay_window_seconds=604800,ack_lease_seconds=15,max_attempts=5,max_replays=3)
valid['poll_result']=dict(protocol=1,kind='poll_result',subscription_id=u(10),deliveries=[dict(id=u(6),receipt=u(7),generation=1,attempt=1,lease_expires_at='2026-10-29T15:00:15Z',event=event)],has_more=False,dead_letter_count=0,next_poll_ms=2000)
valid['ack_result']=dict(protocol=1,kind='ack_result',subscription_id=u(10),acknowledged=[u(6)])
valid['status_result']=dict(protocol=1,kind='status_result',subscription_id=u(10),state='active',deliveries=[dict(id=u(6),event_id=u(1),state='dead_letter',attempts=5,replays=0,error_code='ACK_EXPIRED')],truncated=False)
valid['replay_result']=dict(protocol=1,kind='replay_result',subscription_id=u(10),replayed=[u(6)])
valid['close_result']=dict(protocol=1,kind='close_result',subscription_id=u(10),closed=True)
write(EXAMPLES/'event-transport.json',valid['poll_result'])
write(ROOT/'packages/contracts/fixtures/v1/event-transport-cases.json',dict(valid=valid))
print('Materialized additive schema/12 golden messages; inventory is intentionally not frozen until protocol/types/negative tests exist.')
