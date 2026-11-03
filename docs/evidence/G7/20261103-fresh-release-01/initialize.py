"""Check actual empty owned storage, preserve original fingerprints, then init."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from fixture import ROOT,OUT,LOCAL,f
state=f.load(LOCAL/'state.json');f.guard(state);assert state['phase']=='configured'
volume=state['project']+'_pgdata'
info=json.loads(f.command('init-pgdata-ownership',['docker','volume','inspect',volume]))[0]
assert info['Labels']['com.modular.disposable']==state['project'] and info['Labels']['com.docker.compose.project']==state['project']
code="from pathlib import Path;r=Path('/check');assert not list(r.iterdir());print('Owned PostgreSQL volume is empty')"
f.command('init-pgdata-empty',['docker','run','--rm','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+volume+',target=/check,readonly','--entrypoint','/venv/bin/python',state['image_id'],'-c',code])
original=f.load(ROOT/'.local/g6-events/state.json')
tables=['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary','mp_plugin_installation','mp_workspace_plugin','mp_service_binding','mp_plugin_grant','mp_service_credential','mp_workspace','mp_membership','mp_principal','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption','mp_event_consumer_state','mp_job']
query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SELECT jsonb_build_object('+','.join("'"+t+"',(SELECT jsonb_build_object('count',count(*),'sha256',encode(sha256(convert_to(COALESCE(jsonb_agg(to_jsonb(t) ORDER BY id),'[]'::jsonb)::text,'UTF8')),'hex')) FROM "+t+' t)' for t in tables)+');ROLLBACK;'
raw=f.command('original-preserved-baseline',['docker','exec','-i',original['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',original['active_db'],'-v','ON_ERROR_STOP=1'],input=query.encode())
baseline=json.loads(raw);assert baseline['mp_job']['count']==38 and baseline['mp_example_note']['count']==30
f.write(LOCAL/'original-preservation-query.json',dict(project=original['project'],database=original['active_db'],query=query,expected=baseline))
f.save('site/original-preservation-baseline.json' if f.OUTPUT==OUT else 'original-preservation-baseline.json',dict(result='captured_read_only_original_baseline',tables=baseline,protected_configs=f.load(LOCAL/'state.json')['protected_configurations']))
f.initialize()
