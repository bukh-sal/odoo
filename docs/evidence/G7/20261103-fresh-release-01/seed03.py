"""Continue seed after confirmed pre-mutation unscoped ORM guard refusal."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from dependency_recovery import f,LOCAL,OUT,PUBLIC,PRIVATE,MARKER,context,snapshot,schema,FILE_OBSERVATION

def finish():
 state,native=context();r=f.load(MARKER);assert r['state']=='seeding'
 assert 'Attachments are not supported for workspace models in this R1 profile' in (LOCAL/'logs/g7-recovery-seed02.stderr').read_text()
 counts=json.loads(f.sql(state,'g7-recovery-seed03-precheck',"BEGIN READ ONLY;SELECT jsonb_build_array((SELECT count(*) FROM mp_example_note),(SELECT count(*) FROM mp_example_canvas_board),(SELECT count(*) FROM mp_job),(SELECT count(*) FROM mp_outbox));ROLLBACK;"));assert counts==[0,0,0,0]
 code='FIXTURE='+repr(f.load(LOCAL/'fixtures.json'))+'\nEXPECTED_DATABASE='+repr(state['active_db'])+'\n'+(OUT/'seed_native03.py').read_text()
 raw=f.native(state,'g7-recovery-seed03',[],code)
 rows=[json.loads(line.split('MP_G7_RECOVERY_SEED=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_G7_RECOVERY_SEED=')];assert len(rows)==1
 f.write(PRIVATE/'seed.json',rows[0]);f.save('seed.json',dict(result='seeded_actual_native_reference_history',**rows[0]))
 before=snapshot(state,'g7-recovery-seed-data');assert len(before['mp_example_note'])==4 and len(before['mp_example_canvas_board'])==1 and len(before['mp_job'])==1 and before['mp_job'][0]['state']=='completed'
 f.write(PRIVATE/'before.json',before);f.write(PRIVATE/'schema.json',dict(sha256=schema(state,'g7-recovery-seed-schema')))
 modules=json.loads(f.sql(state,'g7-recovery-seed-modules',"BEGIN READ ONLY;SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module;ROLLBACK;"));f.write(PRIVATE/'modules.json',modules)
 files=json.loads(f.command('g7-recovery-seed-files',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]));assert files and rows[0]['attachment_store_fname'] in files
 f.write(PRIVATE/'files.json',files);r=f.load(MARKER);r['state']='seeded';f.write(MARKER,r);f.phase(state,'g7_recovery_seeded');print('Real4Notes/1minimalCanvas/attachment/original-actor completed job and exact baseline captured',flush=True)
if __name__=="__main__":finish()
