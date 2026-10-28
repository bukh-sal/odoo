/** Real OperationsPanel methods with isolated Owl hooks and an API boundary. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const source=await readFile(new URL('../platform_addons/mp_shell/static/src/operations.js',import.meta.url),'utf8');
const isolated=source.replace(/import \{[^}]+\} from '@odoo\/owl';/,
    'const Component=class {};const xml=(text)=>text.join("");const useState=x=>x;const onMounted=()=>{};const onWillDestroy=()=>{};');
const {OperationsPanel}=await import('data:text/javascript;base64,'+Buffer.from(isolated).toString('base64'));
const id='00000000-0000-4000-8000-000000000001',nonce='00000000-0000-4000-8000-000000000002';
const site='00000000-0000-4000-8000-000000000003',alice='00000000-0000-4000-8000-000000000004',bob='00000000-0000-4000-8000-000000000005';
const hash='sha256:'+'a'.repeat(64);
function environment(){
    const storage=new Map();globalThis.sessionStorage={getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)};
    globalThis.document={hidden:false};return storage;
}
function fixture({actor=alice,canRequest=true,status={operation_id:id,plan_hash:hash,state:'completed',phase:'completed',source:'operator_journal_mirror',history:[]},reject=false,postError=false}={}){
    const calls=[];let denied=false;
    const api=async(path,body)=>{
        calls.push({path,body});
        if(path==='/api/v1/session')return {principal_id:actor};
        if(path==='/api/v1/operations/context')return {can_request:canRequest,site_id:site,workspaces:[]};
        if(path==='/api/v1/operations/catalog')return {items:[]};
        if(path==='/api/v1/operations/installed?offset=0')return {items:[],next_offset:null,stale:false};
        if(path.startsWith('/api/v1/operations/status/')){if(reject)throw Object.assign(new Error('Not found'),{code:'NOT_FOUND'});return status;}
        if(path==='/api/v1/operations/request'){if(postError)throw Object.assign(new Error('Timeout'),{name:'AbortError'});return status;}
        throw new Error('Unexpected path '+path);
    };
    const panel=Object.create(OperationsPanel.prototype);panel.props={api,onSession:()=>{},onDenied:()=>{denied=true;}};panel.setup();
    return {panel,calls,denied:()=>denied};
}

test('activation reload restores the same owned operation and continues polling without a prepared form',async()=>{
    const storage=environment();const first=fixture();await first.panel.authority();first.panel.requestId=nonce;first.panel.state.prepared={operation_id:id,plan_hash:hash};await first.panel.submit();
    assert.deepEqual(JSON.parse(storage.get('mp.operation.'+site+'.'+alice)),{operation_id:id,request_id:nonce});
    const fresh=fixture();await fresh.panel.load();assert.equal(fresh.panel.state.prepared,null);assert.equal(fresh.panel.state.status.state,'completed');
    await fresh.panel.poll();assert.equal(fresh.calls.filter(row=>row.path.endsWith('/status/'+id)).length,2);
    const commands=fresh.panel.approvalCommand;assert.match(commands,/operations import-request/);assert.match(commands,/plugin apply/);assert.match(commands,/operations mirror-status/);assert.ok(commands.includes('--plan-hash '+hash));
});

test('another principal never loads the previous actor resume hint',async()=>{
    const storage=environment();storage.set('mp.operation.'+site+'.'+alice,JSON.stringify({operation_id:id,request_id:nonce}));
    const fresh=fixture({actor:bob});await fresh.panel.load();assert.equal(fresh.panel.state.status,null);assert.equal(fresh.calls.filter(row=>row.path.includes('/status/')).length,0);
});

test('role revocation and own-request denial clear the hint without exposing a result',async()=>{
    for(const options of [{canRequest:false},{reject:true}]){
        const storage=environment();const key='mp.operation.'+site+'.'+alice;storage.set(key,JSON.stringify({operation_id:id,request_id:nonce}));
        const fresh=fixture(options);await fresh.panel.load();assert.equal(fresh.panel.state.status,null);assert.ok(fresh.denied());assert.equal(storage.has(key),false);
    }
});

test('an uncertain request resumes using the same nonce and never invents approval',async()=>{
    environment();const first=fixture({postError:true});await first.panel.authority();first.panel.requestId=nonce;first.panel.state.prepared={operation_id:id,plan_hash:hash};await first.panel.submit();
    const pending={operation_id:id,plan_hash:hash,state:'awaiting_operator_approval',phase:'prepared',source:'application_request',history:[{code:'prepared'}]};
    const fresh=fixture({status:pending});await fresh.panel.load();assert.equal(fresh.panel.state.submitted,false);assert.equal(fresh.panel.requestId,nonce);
    await fresh.panel.submit();const post=fresh.calls.find(row=>row.path==='/api/v1/operations/request');assert.equal(post.body.request_id,nonce);assert.equal(post.body.operation_id,id);assert.equal(fresh.panel.state.status.state,'awaiting_operator_approval');
});

test('extra authority fields in storage are ignored rather than sent to an API',async()=>{
    const storage=environment();storage.set('mp.operation.'+site+'.'+alice,JSON.stringify({operation_id:id,request_id:nonce,approved:true}));
    const fresh=fixture();await fresh.panel.load();assert.equal(fresh.panel.state.status,null);assert.equal(fresh.calls.filter(row=>row.path.includes('/status/')).length,0);
});
