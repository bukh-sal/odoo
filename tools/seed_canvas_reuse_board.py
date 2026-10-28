"""Create one explicit UI regression fixture via Alice's scoped native API."""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.deployment import DockerObserver
from qualify_native_upgrade import sql
from qualify_release_reader_rollout import notes_snapshot
import r1,r1_probe
r1.r0.LOCAL=ROOT/'.local/g5'


def main():
    local=ROOT/'.local/g5';marker=local/'canvas-reuse-board.json'
    if marker.exists():raise ValueError('Fixture already attempted; reconcile native result instead of creating again')
    config=json.loads((ROOT/'.local/operator/targets/g5.json').read_text());state=json.loads((local/'state.json').read_text())
    fixture=json.loads((local/'fixtures.json').read_text());observer=DockerObserver(config)
    assert config['project']=='mp-r0-r1g5fd0445d406d6' and config['generation']==16 and state['disposable']
    assert sql(observer,'SELECT count(*) FROM mp_example_canvas_board;').strip()==b'0'
    notes=notes_snapshot(observer);assert len(notes)==4
    alice=r1_probe.Client(state,fixture,'alice')
    note=alice.native('search_read',args=[[]],kwargs={'fields':['public_id'],'limit':1})
    name='G5 Canvas lifecycle fixture '+uuid4().hex[:8]
    data={'state':'nominated','name':name,'workspace_id':fixture['workspaces']['A']['public_id'],'created_utc':datetime.now(timezone.utc).isoformat()}
    with marker.open('x') as stream:json.dump(data,stream,indent=2)
    result=alice.native('create',args=[[{'name':name,'cards':[{'id':str(uuid4()),'text':'Canvas lifecycle fixture card','lane':'inbox','note_id':note[0]['public_id']}]}]],model='mp.example.canvas.board')
    ids=result if isinstance(result,list) else [result]
    rows=alice.native('read',args=[ids,['public_id','name','revision','cards']],model='mp.example.canvas.board')
    assert len(rows)==1 and rows[0]['name']==name and notes_snapshot(observer)==notes
    data.update(state='created',board=rows[0]);marker.write_text(json.dumps(data,indent=2)+'\n')
    output=ROOT/'docs/evidence/G5/20261028T155500Z-canvas-reuse-browser'
    (output/'board-fixture.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps({'result':'created_scoped_fixture','board_id':rows[0]['public_id'],'original_notes_unchanged':True}))


if __name__=='__main__':main()
