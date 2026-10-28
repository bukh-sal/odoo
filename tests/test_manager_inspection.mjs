/** Execute the real panel and root transport methods without replacing behavior. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

const source=await readFile(new URL('../platform_addons/mp_shell/static/src/operations.js',import.meta.url),'utf8');
const isolated=source.replace(/import \{[^}]+\} from '@odoo\/owl';/,'const Component=class {};const xml=(text)=>text.join("");const useState=x=>x;const onMounted=()=>{};const onWillDestroy=()=>{};');
const {OperationsPanel}=await import('data:text/javascript;base64,'+Buffer.from(isolated).toString('base64'));
function panel(api){const p=new OperationsPanel();p.props={api,onSession:()=>{},onDenied:()=>{}};p.setup();return p;}

test('upload sends original bytes and exact SHA through the existing fenced API adapter',async()=>{
    const bytes=Buffer.from('reference fixture'),file=new File([bytes],'reference.mplug');let call;
    const p=panel(async(path,body,options)=>{call={path,body,options};return {result:'not_curated',artifact_digest:'sha256:'+createHash('sha256').update(bytes).digest('hex')};});
    p.selectUpload({target:{files:[file]}});await p.upload();
    assert.equal(call.path,'/api/v1/operations/validate-upload');assert.equal(call.body,file);assert.equal(call.options.binary,true);
    assert.equal(call.options.headers['X-MP-Artifact-Digest'],'sha256:'+createHash('sha256').update(bytes).digest('hex'));
    assert.equal(p.state.uploadResult.result,'not_curated');assert.equal(p.state.uploadBusy,false);
    assert.ok(p.uploadCommand.includes('ARTIFACT_FILE'));assert.ok(!p.uploadCommand.includes('reference.mplug'));
});

test('role loss cannot publish a late upload or details result',async()=>{
    let resolveUpload,resolveDetails;
    const p=panel(path=>new Promise(resolve=>{if(path.includes('validate-upload'))resolveUpload=resolve;else resolveDetails=resolve;}));
    p.selectUpload({target:{files:[new File(['fixture'],'fixture.mplug')]}});
    const uploading=p.upload();while(!resolveUpload)await new Promise(resolve=>setImmediate(resolve));
    const details=p.showDetails('sha256:'+'a'.repeat(64));p.denied();resolveUpload({result:'verified'});resolveDetails({kind:'plugin_details'});await Promise.all([uploading,details]);
    assert.equal(p.state.uploadResult,null);assert.equal(p.state.details,null);assert.equal(p.state.uploadBusy,false);
});

test('no file or oversize input sends no request',async()=>{
    let calls=0;const p=panel(async()=>{calls++;});await p.upload();
    p.uploadFile={size:100*1024*1024+1};await p.upload();assert.equal(calls,0);assert.match(p.state.error,/100 MiB/);
});

test('catalog continuation requires the same snapshot and metadata pages do not mix',async()=>{
    const p=panel(async path=>path.includes('/catalog')?{snapshot_digest:'new',items:[{artifact_digest:'other'}],next_offset:null}:{items:[{installation_id:'next'}],next_offset:40,stale:true});
    p.catalogSnapshot='original';p.state.catalog=[{artifact_digest:'old'}];p.state.catalogNext=20;await p.loadMoreCatalog();
    assert.equal(p.state.catalog.length,1);assert.match(p.state.error,/Catalog changed/);
    await p.loadInstalled(20);assert.equal(p.state.installed[0].installation_id,'next');assert.equal(p.state.installedOffset,20);assert.equal(p.state.inspectionStale,true);
});

test('component cancellation aborts an in-flight validation through the shared controller',async()=>{
    let signal;const p=panel(async(_path,_body,options)=>{signal=options.signal;return new Promise((_resolve,reject)=>signal.addEventListener('abort',()=>reject(Object.assign(new Error('aborted'),{name:'AbortError'}))));});
    const request=p.api('/api/v1/operations/validate-upload',new Blob(['fixture']),{binary:true});
    p.active=false;p.clearInspection();p.controller.abort();await assert.rejects(request,{name:'AbortError'});assert.equal(signal.aborted,true);
});

const host=await readFile(new URL('../platform_addons/mp_shell/static/src/host.js',import.meta.url),'utf8');
const method=host.slice(host.indexOf('    async json('),host.indexOf('    async blockRelease('));
const makeRoot=new Function('releaseFence','workspace','error','isReleaseError','releaseError','return new (class {'+method+'})();');
test('root binary transport preserves CSRF/session/release fences and old JSON serialization',async()=>{
    const calls=[],checks=[];const prior=globalThis.fetch;
    globalThis.fetch=async(path,options)=>{calls.push({path,options});return {ok:true,status:200,json:async()=>({api_version:'1.0',request_id:'fixture',data:{ok:true}})};};
    try{
        const root=makeRoot({assert:(...args)=>checks.push(args),headers:()=>({'X-MP-Client-Release':'pinned'})},'workspace',code=>({code}),()=>false,()=>new Error('release'));
        root.csrf='csrf';const raw=new Blob(['unchanged bytes']);await root.json('/api/v1/operations/validate-upload',raw,{binary:true,headers:{'X-MP-Artifact-Digest':'exact'}});
        assert.equal(calls[0].options.body,raw);assert.equal(calls[0].options.headers['Content-Type'],'application/octet-stream');
        assert.equal(calls[0].options.headers['X-CSRFToken'],'csrf');assert.equal(calls[0].options.headers['X-MP-Client-Release'],'pinned');assert.equal(calls[0].options.credentials,'same-origin');
        await root.json('/api/v1/operations/request',{request_id:'existing'});assert.equal(calls[1].options.body,'{"request_id":"existing"}');assert.equal(calls[1].options.headers['Content-Type'],'application/json');
        assert.equal(checks.length,4);assert.equal(checks[1][1],'unknown');
    }finally{globalThis.fetch=prior;}
});
