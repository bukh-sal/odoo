import {readFileSync,existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const source=readFileSync('platform_addons/mp_shell/static/src/host.js','utf8');
const releaseSource=readFileSync('platform_addons/mp_shell/static/src/client_release.js','utf8');
const {ClientReleaseFence,isReleaseError,releaseError}=await import('data:text/javascript;base64,'+Buffer.from(releaseSource).toString('base64'));
const errorSource=source.slice(source.indexOf('function error('),source.indexOf('function freeze('));
const requestSource=source.slice(source.indexOf('    async json('),source.indexOf('    async blockRelease('));
const serviceSource=source.slice(source.indexOf('    async callService('),source.indexOf('    facade('));
let generation=1,workspace,releaseFence;
function obsolete(){return new DOMException('Obsolete page context','AbortError');}
const methods=eval('(()=>{'+errorSource+'; return ({'+requestSource+','+serviceSource+'});})()');
assert.equal(typeof methods.json,'function');assert.equal(typeof methods.callService,'function');
if(process.argv.includes('--verify-source')){
 console.log(JSON.stringify({result:'request_source_compiles',host_sha256:createHash('sha256').update(source).digest('hex')}));
}else{
 const cfg=JSON.parse(readFileSync(0,'utf8'));
 workspace=cfg.workspace;releaseFence=new ClientReleaseFence(cfg.release);
 const originalFetch=globalThis.fetch;let requests=0;
 globalThis.fetch=(path,options)=>{requests++;return originalFetch(cfg.base+path,{...options,headers:{...options.headers,Cookie:cfg.cookie}});};
 const shell={...methods,csrf:cfg.csrf,controller:new AbortController(),bindings:[cfg.binding],state:{context:{installation_id:cfg.binding.consumer_installation_id}}};
 const before=new AbortController();before.abort();
 await assert.rejects(shell.callService('documents','create',cfg.values,{signal:before.signal,idempotencyKey:cfg.key}),e=>e.code==='CANCELLED'&&e.details.outcome==='not_started');
 assert.equal(requests,0);console.log(JSON.stringify({phase:'pre_aborted',code:'CANCELLED',outcome:'not_started',requests}));
 const controller=new AbortController();const timer=setInterval(()=>{if(existsSync(cfg.trigger))controller.abort();},25);
 const expiry=setTimeout(()=>controller.abort(),25000);
 try{
  await assert.rejects(shell.callService('documents','create',cfg.values,{signal:controller.signal,idempotencyKey:cfg.key}),e=>e.code==='CANCELLED'&&e.details.outcome==='unknown');
  assert.ok(existsSync(cfg.trigger),'Abort must follow operator observation of committed server effect');
  assert.equal(requests,1);console.log(JSON.stringify({phase:'cancelled_after_observed_commit',code:'CANCELLED',outcome:'unknown',requests,host_sha256:createHash('sha256').update(source).digest('hex')}));
 }finally{clearInterval(timer);clearTimeout(expiry);}
}
