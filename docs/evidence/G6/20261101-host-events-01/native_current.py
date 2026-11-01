"""Current-image rollback/bus and scope proof; one owned stream is retained closed."""
import json
from uuid import uuid4
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core import events
from odoo.addons.mp_core.controllers import PublicError
ENV.cr.rollback();registry=ENV.registry
def actor(cr,workspace='C'):
    return scoped_environment(api.Environment(cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces'][workspace]['public_id'])
def message(kind,**values):return dict(protocol=1,kind=kind+'_request',request_id=str(uuid4()),**values)
def count_bus(cr):
    cr.execute("SELECT count(*) FROM bus_bus WHERE message::jsonb->>'type'='mp_domain_events'");return cr.fetchone()[0]
with registry.cursor() as cr:
    cr.execute('SELECT state,generation FROM mp_dispatch_control');assert cr.fetchone()==('enabled',37)
    cr.execute('SELECT count(*) FROM mp_example_note');assert cr.fetchone()[0]==27
    cr.execute('SELECT count(*) FROM mp_outbox');assert cr.fetchone()[0]==44
    before_bus=count_bus(cr)
    cr.execute("SELECT b.public_id FROM mp_service_binding b JOIN mp_plugin_installation i ON i.id=b.consumer_id WHERE i.plugin_id='org.example.notes' AND b.workspace_id=%s AND b.alias='documents' AND b.state='active'",[FIXTURE['workspaces']['C']['id']]);binding=cr.fetchone()[0]
    sub=events.dispatch(actor(cr),message('subscribe',topic='org.example.notes.changed',idempotency_key=KEY),binding_id=binding)['subscription_id'];cr.commit()
checks=[]
try:
    # The producer row exists only in its own uncommitted transaction. Poll in
    # a distinct real registry cursor cannot observe it before or after rollback.
    with registry.cursor() as producer:
        native=actor(producer);note=native['mp.example.note'].create({'title':'Rollback-only current event proof','body':'Never committed'});ident=note.public_id;native.flush_all()
        with registry.cursor() as consumer:
            value=events.dispatch(actor(consumer),message('poll',subscription_id=sub,limit=50));assert all(d['event']['aggregate_id']!=ident for d in value['deliveries']);consumer.rollback()
        producer.rollback()
    with registry.cursor() as cr:
        cr.execute('SELECT count(*) FROM mp_example_note WHERE public_id=%s',[ident]);assert cr.fetchone()[0]==0
        cr.execute('SELECT count(*) FROM mp_outbox WHERE aggregate_id=%s',[ident]);assert cr.fetchone()[0]==0
        assert count_bus(cr)==before_bus
        value=events.dispatch(actor(cr),message('poll',subscription_id=sub,limit=50));assert all(d['event']['aggregate_id']!=ident for d in value['deliveries']);cr.rollback()
    checks.append('actual distinct-cursor rollback exposes no producer envelope, delivery or native bus hint')
    with registry.cursor() as cr:
        codes=[]
        for reference in [sub,str(uuid4())]:
            try:events.dispatch(actor(cr,'B'),message('status',subscription_id=reference))
            except PublicError as error:codes.append(error.code)
            else:raise AssertionError('Foreign or missing subscription exposed status')
            cr.rollback()
        assert codes==['NOT_FOUND','NOT_FOUND']
    checks.append('current foreign workspace and missing subscription are equivalent without payload')
    with registry.cursor() as cr:
        native=actor(cr);feature=api.Environment(cr,1,{})['mp.workspace.plugin'].search([('workspace_id','=',FIXTURE['workspaces']['C']['id']),('plugin_id','=','org.example.notes')]);assert len(feature)==1
        feature.write({'availability':'suspended'})
        try:events.dispatch(native,message('poll',subscription_id=sub,limit=50))
        except (AccessError,PublicError):pass
        else:raise AssertionError('Pending native feature suspension was ignored')
        cr.rollback()
    checks.append('pending native feature revocation blocks event poll before payload/claim')
finally:
    with registry.cursor() as cr:events.dispatch(actor(cr),message('close',subscription_id=sub));cr.commit()
with registry.cursor() as cr:
    cr.execute('SELECT state FROM mp_event_subscription WHERE public_id=%s',[sub]);assert cr.fetchone()[0]=='closed'
    cr.execute('SELECT state,generation FROM mp_dispatch_control');assert cr.fetchone()==('enabled',37)
    cr.execute('SELECT count(*) FROM mp_example_note');assert cr.fetchone()[0]==27
    cr.execute('SELECT count(*) FROM mp_outbox');assert cr.fetchone()[0]==44
    assert count_bus(cr)==before_bus
print('MP_CURRENT_EVENTS='+json.dumps(dict(result='passed',checks=checks,owned_subscription=sub,subscription_retained_closed=True,all_business_policy_and_receipt_test_writes_rolled_back=True,dispatch_generation_unchanged=37,source_substitution=False)))
