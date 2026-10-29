/** Actual OperationsPanel methods; native rendering remains a live browser check. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const source=await readFile(new URL('../platform_addons/mp_shell/static/src/operations.js',import.meta.url),'utf8');
const isolated=source.replace(/import \{[^}]+\} from '@odoo\/owl';/,
    'const Component=class {};const xml=text=>text.join("");const useState=x=>x;const onMounted=()=>{};const onWillDestroy=()=>{};');
const {OperationsPanel}=await import('data:text/javascript;base64,'+Buffer.from(isolated).toString('base64'));
const operation='00000000-0000-4000-8000-000000000001',site='00000000-0000-4000-8000-000000000002';
const workspace='00000000-0000-4000-8000-000000000003',installation='00000000-0000-4000-8000-000000000004';
const hash='sha256:'+'a'.repeat(64),digest='sha256:'+'b'.repeat(64);

function panel({action='uninstall',badImpact=false,badStates=false,late=false}={}){
    globalThis.document={hidden:false};globalThis.sessionStorage={getItem:()=>null,setItem:()=>{},removeItem:()=>{}};
    const calls=[];
    const prepared={operation_id:operation,plan_hash:hash,plan:{operation_id:operation,operation_type:action,destructive:action==='uninstall'},
        targets:[{site_id:site,workspace_id:workspace,installation_id:installation,plugin_id:'org.example.notes_labels',action}]};
    const impact={schema_version:1,kind:'native_uninstall_impact',operation_id:operation,plan_hash:badImpact?'sha256:'+'f'.repeat(64):hash,
        destructive:true,requires_backup:true,artifact_action:'retain_in_runtime',impact:Object.fromEntries(
            ['plugins','models','fields','constraints','foreign_references','metadata_records','assets','warnings','native_closure','requested_addons'].map(k=>[k,[]]))};
    let finish;
    const api=async(path,body)=>{
        calls.push({path,body});
        if(path.endsWith('/prepare'))return prepared;
        if(path.includes('/bundle/'))return {plan_hash:hash,plan:prepared.plan,operation_lock:{feature_states:action==='install'?
            [{site_id:site,workspace_id:workspace,installation_id:installation,availability:badStates?'removed':'suspended'}]:[]}};
        if(path.includes('/impact/'))return late?new Promise(resolve=>{finish=()=>resolve(impact);}):impact;
        if(path.endsWith('/request'))return {operation_id:operation,plan_hash:hash,state:'awaiting_operator_approval',history:[],phase:'prepared'};
        throw new Error('Unexpected API '+path);
    };
    const p=Object.create(OperationsPanel.prototype);p.props={api,onSession:()=>{},onDenied:()=>{}};p.setup();
    p.state.context={site_id:site,workspaces:[]};p.state.catalog=[{artifact_digest:digest,plugin_id:'org.example.notes_labels',version:'0.2.1'}];
    p.state.digest=digest;p.state.action=action;p.state.workspace=workspace;
    return {p,calls,finish:()=>finish()};
}

test('native request requires the bound impact and explicit destructive acknowledgment',async()=>{
    const {p,calls}=panel();await p.prepare();assert.equal(p.state.impact.operation_id,operation);
    assert.equal(p.requestAllowed,false);await p.submit();assert.equal(calls.filter(c=>c.path.endsWith('/request')).length,0);
    p.state.destructiveConfirmed=true;assert.equal(p.requestAllowed,true);await p.submit();
    const call=calls.find(c=>c.path.endsWith('/request'));
    assert.deepEqual(Object.keys(call.body).sort(),['operation','operation_id','plan_hash','request_id','schema_version']);
    assert.equal(p.state.status.state,'awaiting_operator_approval');
    p.clearPlan();assert.equal(p.state.destructiveConfirmed,false);assert.equal(p.state.impact,null);assert.equal(p.requestAllowed,false);
});

test('mismatched impact and invalid retained-scope states fail before a request is possible',async()=>{
    for(const options of [{badImpact:true},{action:'install',badStates:true}]){
        const {p,calls}=panel(options);await p.prepare();assert.equal(p.state.prepared,null);assert.ok(p.state.error);
        assert.equal(p.requestAllowed,false);assert.equal(calls.some(c=>c.path.endsWith('/request')),false);
    }
});

test('retained-scope map is displayed separately from the unchanged public prepared DTO',async()=>{
    const {p,calls}=panel({action:'install'});await p.prepare();assert.equal(p.state.featureStates[0].availability,'suspended');
    assert.equal(p.featurePlugin(p.state.featureStates[0]),'org.example.notes_labels');assert.equal(p.requestAllowed,true);
    assert.equal(calls.some(c=>c.path.includes('/impact/')),false);
});

test('a late impact cannot restore a cleared or changed proposal',async()=>{
    const f=panel({late:true});const task=f.p.prepare();await new Promise(resolve=>setImmediate(resolve));
    f.p.clearPlan();f.finish();await task;assert.equal(f.p.state.prepared,null);assert.equal(f.p.state.impact,null);
    assert.equal(f.p.requestAllowed,false);
});
