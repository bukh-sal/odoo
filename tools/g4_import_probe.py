"""Native shared-table extension export/import with real ownership/revisions."""
import json
from uuid import uuid4

import r1
from r1_probe import Client


def main():
    state=r1.setup();fixture=json.loads((r1.r0.LOCAL/'fixtures.json').read_text());client=Client(state,fixture)
    out=r1.r0.ROOT/state['evidence']/(r1.r0.now()+'-extension-import-export.json');checks=[];ids=[];export_added=False
    def passed(name):checks.append({'name':name,'result':'passed'})
    def policy(code,label):return r1.shell(state,label,f"assert env.cr.dbname=={state['active_db']!r}\n"+code+'\nenv.cr.commit()\nenv.registry.signal_changes()\n')
    try:
        policy(f"actor=env['res.users'].browse({fixture['users']['alice']['id']!r});assert actor.login=='r1_alice'\ngroup=env.ref('base.group_allow_export');assert group not in actor.group_ids\nactor.write({{'group_ids':[(4,group.id)]}})",'g4-export-permission');export_added=True
        title='Import proof '+uuid4().hex
        result=client.native('load',[['title','body','x_notes_labels'],[[title,'Original\nUnicode café','[bad JSON']]])
        assert not result['ids'] and result['messages']
        assert client.native('search_count',[[('title','=',title)]])==0
        result=client.native('load',[['title','body','x_notes_labels'],[[title,'Original\nUnicode café',json.dumps(['Cafe','TAG'])]]])
        assert result['ids'] and not result['messages'],result
        ident=result['ids'][0];ids.append(ident)
        row=client.native('read',[[ident],['public_id','title','body','x_notes_labels','revision','workspace_id']])[0]
        assert row['x_notes_labels']==['cafe','tag'] and row['revision']==1 and row['workspace_id'][0]==fixture['workspaces']['A']['id']
        passed('new native import preserves declared base/extension fields and normalizes labels; invalid JSON has no effect')
        export=client.native('export_data',[[ident],['title','body','x_notes_labels']])
        assert export['datas'][0][:2]==[title,'Original\nUnicode café'] and json.loads(export['datas'][0][2])==['cafe','tag']
        update=client.native('load',[['.id','title','body','x_notes_labels'],[[str(ident),'Imported update','Base and extension retained',json.dumps(['Roundtrip','VALUE'])]]],{'context':{'expected_revision':1}})
        assert update['ids']==[ident],update
        current=client.native('read',[[ident],['title','body','x_notes_labels','revision']])[0]
        assert current['title']=='Imported update' and current['body']=='Base and extension retained' and current['x_notes_labels']==['roundtrip','value'] and current['revision']==2
        stale=client.native('load',[['.id','title'],[[str(ident),'Stale import']]],{'context':{'expected_revision':1}})
        assert not stale['ids'] and stale['messages']
        assert client.native('read',[[ident],['title','body','x_notes_labels','revision']])[0]==current
        passed('export roundtrip and existing-ID import preserve both owners; stale import cannot overwrite and revision advances once')
        unsafe=client.native('load',[['.id','x_notes_labels'],[[str(fixture['objects']['B']['id']),json.dumps(['Denied'])]]],{'context':{'expected_revision':1}})
        assert not unsafe['ids'] and unsafe['messages']
        viewer=client.native('load',[['title','x_notes_labels'],[['Denied viewer import',json.dumps(['Denied'])]]],workspace='B')
        assert not viewer['ids'] and viewer['messages']
        moved=client.native('load',[['.id','workspace_id/.id'],[[str(ident),str(fixture['workspaces']['B']['id'])]]],{'context':{'expected_revision':2}})
        assert not moved['ids'] and moved['messages']
        assert client.native('read',[[ident],['title','body','x_notes_labels','revision']])[0]==current
        passed('foreign ID, viewer import and ownership transfer fail atomically through native load')
        out.write_text(json.dumps({'state':'passed','checks':checks},indent=2)+'\n');print(json.dumps({'result':'passed','checks':len(checks),'evidence':str(out.relative_to(r1.r0.ROOT))}))
    except Exception:out.write_text(json.dumps({'state':'failed','checks':checks},indent=2)+'\n');raise
    finally:
        for ident in ids:
            revision=client.native('read',[[ident],['revision']])[0]['revision']
            client.native('unlink',[[ident]],{'context':{'expected_revision':revision}})
        if export_added:policy(f"actor=env['res.users'].browse({fixture['users']['alice']['id']!r});assert actor.login=='r1_alice'\nactor.write({{'group_ids':[(3,env.ref('base.group_allow_export').id)]}})",'g4-export-permission-restore')


if __name__=='__main__':main()
