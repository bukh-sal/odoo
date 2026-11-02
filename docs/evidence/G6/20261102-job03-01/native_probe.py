"""Trusted fixture definition through real installed native authorization/runner."""
import copy,hashlib,http.client,json,sys,time
from uuid import uuid4
from modular_platform import job_runner,durable,dispatch_lifecycle as LC
from modular_platform.tokens import ISSUER,AUDIENCE
from modular_platform.contracts import validate
import jwt

packet=json.load(sys.stdin)
database=job_runner.validate_startup()
assert database==packet['database'] and database.startswith('mp_disposable_g6_job03_')
from odoo.modules.registry import Registry
from odoo.tools import config
from odoo import api
config.parse_config(['-c','/run/secrets/odoo_config','--no-http','--workers=0','--max-cron-threads=0'])
registry=Registry(database)
from odoo.addons.mp_identity.scopes import scoped_environment,current_scope
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core import job_dispatch as jobs,external_job as bridge
from odoo.addons.mp_example_notes_stats import jobs as connector,contracts
IDENT='org.example.notes_stats:uncertain_probe'

def actor(metadata):
    env=scoped_environment(api.Environment(metadata.cr,packet['alice_uid'],{}),packet['workspace'])
    scope=current_scope(env)
    installation=metadata['mp.plugin.installation'].search([('plugin_id','=','org.example.notes_stats')]);assert len(installation)==1
    frame=CallFrame(scope.principal_public_id,scope.workspace_public_id,packet['site_id'],installation.public_id,'org.example.notes_stats',(('org.example.notes_stats','org.example.notes_stats.jobs','analyze'),))
    return env(context={**env.context,'_mp_call_frame':frame})

def compute(prepared,context):
    provenance=context['_native_job'];assert provenance['database']==database
    authority,snapshot,fingerprint=bridge._snapshot(registry,provenance,prepared,context,'stats','/run/worker-authority')
    claim=durable.Claim(**provenance['claim'])
    # Actual original-actor/provider/resource/approval checks precede the
    # committed effect marker. No cursor or transaction spans the HTTP call.
    with registry.cursor() as cr:
        metadata=api.Environment(cr,1,{})
        row=durable._lock(cr,claim);env,definition,payload,bound=jobs._authorized_job(metadata,row)
        assert definition.ident==IDENT and definition.prepare(env,payload['input'],bound)==prepared
        _,current,digest=bridge.authorization_snapshot(bound.model.env)
        assert current==snapshot and digest==fingerprint
        durable.effect_started(cr,claim);cr.commit()
    key_id,key=authority.issuer(snapshot,snapshot.endpoint['issuer_key_ref']);now=int(time.time())
    scope={k:snapshot.endpoint[k] for k in ('site_id','workspace_id','installation_id')}
    request=dict(api_version='1.0',request_id=context['request_id'],operation_id=context['job_id'],method='analyze',input=prepared['input'],endpoint_generation=snapshot.endpoint['generation'],**scope)
    claims=dict(iss=ISSUER,aud=AUDIENCE,sub=scope['installation_id'],jti=str(uuid4()),iat=now,nbf=now,exp=now+300,methods=['analyze'],endpoint_generation=snapshot.endpoint['generation'],**scope)
    validate('worker-request',request);validate('worker-claims',claims)
    credential=jwt.encode(claims,key,algorithm='RS256',headers={'kid':key_id})
    # This is an explicit private operator-owned effect fixture destination,
    # never an endpoint supplied by job input or an extra public service.
    target=packet['effect_target'];assert set(target)=={'address','host','port'} and target['port']==8080
    print('MP_EFFECT_START='+json.dumps(dict(job_id=claim.job_id,claim_generation=claim.generation,effect_started_committed=True,
        input_sha256=hashlib.sha256(json.dumps(prepared['input'],sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest())),flush=True)
    connection=http.client.HTTPConnection(target['address'],target['port'],timeout=100)
    try:
        connection.request('POST','/analyze',json.dumps(request).encode(),{'Host':target['host'],'Content-Type':'application/json','Authorization':'Bearer '+credential})
        response=connection.getresponse();raise AssertionError('Fixture must withhold the effect acknowledgement')
    finally:connection.close()

jobs.register(jobs.JobDefinition(ident=IDENT,version=1,plugin='org.example.notes_stats',service='org.example.notes_stats.jobs',api_version='1.0',method='status',
    input_schema=contracts.INPUT,prepared_schema=contracts.PREPARED,computed_schema=contracts.COMPUTED,output_schema=contracts.RESULT,
    authorize_resource=connector.resource,prepare=connector.prepare,compute=compute,apply=connector.apply,effect_mode='reconcile',max_attempts=3,timeout_seconds=180))

if packet['mode']=='produce':
    with registry.cursor() as cr:
        metadata=api.Environment(cr,1,{});env=actor(metadata)
        job=jobs.enqueue_bound(env,'jobs',IDENT,packet['input'],packet['key']);cr.commit()
    print('MP_ENQUEUED='+json.dumps(dict(job_id=job,registered_fixture_handler=True)),flush=True)
    result=job_runner.run_once(registry,str(uuid4()))
    print('MP_UNEXPECTED_RETURN='+json.dumps(result),flush=True)
    raise SystemExit(2)
else:
    assert packet['mode']=='observe'
    first=job_runner.run_once(registry,str(uuid4()));second=job_runner.run_once(registry,str(uuid4()))
    assert first==second==dict(state='idle')
    with registry.cursor() as cr:
        metadata=api.Environment(cr,1,{});status=jobs.status(actor(metadata),packet['job_id']);jobs._validate(contracts.JOB,status)
        assert status['state']=='outcome_unknown' and status['error_code']=='LEASE_EXPIRED' and status['attempts']==1 and status['result'] is None
        cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[packet['job_id']]);row=cr.fetchone()[0]
        assert row['effect_started'] and row['effect_mode']=='reconcile' and row['lease_owner'] is None
        cr.rollback()
    # Fencing is the independent operator transaction, not an Odoo business
    # transaction. Match the installed adapter's fresh READ COMMITTED contract.
    import configparser,psycopg2
    settings=configparser.ConfigParser();settings.read('/run/secrets/odoo_config');options=settings['options']
    connection=psycopg2.connect(host=options['db_host'],port=options.getint('db_port'),user=options['db_user'],password=options['db_password'],dbname=database,connect_timeout=5)
    connection.set_session(isolation_level='READ COMMITTED')
    try:
      with connection.cursor() as cr:
        scope=LC.LifecycleScope(packet['site_id'],row['release_digest'],reference=packet['reference_policy'])
        fenced=LC.fence(cr,scope,str(uuid4()));connection.commit()
        paused=LC.observe(cr,scope);assert paused['control']['state']=='paused' and paused['uncertain_jobs']==1
        try:LC.enable(cr,scope,paused['state_digest'])
        except LC.DispatchLifecycleError as error:assert str(error)=='Unreconciled effects or credentials prevent native dispatch resume'
        else:raise AssertionError('Unknown effect wrongly allowed dispatch enable')
        connection.rollback()
    finally:connection.close()
    print('MP_UNKNOWN='+json.dumps(dict(job=status,first_reclaim=first,second_reclaim=second,
        actual_native_authorization_and_status=True,actual_installed_runner_twice_idle=True,lifecycle_enable_refused=True,uncertain_jobs=1,
        reconciliation_required=True,automatic_retry_forbidden=True)),flush=True)
