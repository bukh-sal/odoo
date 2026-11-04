// Actual two-tab native view isolation; reuse exactly the owned performance profile.
import {spawn} from 'node:child_process';
import {readFile,writeFile,open,stat} from 'node:fs/promises';
import path from 'node:path';
const root=process.cwd(),dir=path.join(root,'.local/g7-ui-qualification-01');
const outdir=path.join(dir,'identity02');
const load=async p=>JSON.parse(await readFile(p,'utf8'));
const input=await load(path.join(dir,'browser-input.json')),before=await load(path.join(dir,'tables-before.json'));
const base=input.base,origin=new URL(base).origin,profile=input.profile;
const password=(await load(input.password_file))[input.actor],actor=input.fixture.users[input.actor];
const spaces=input.fixture.workspaces,notes=Object.fromEntries(['A','B'].map(k=>[k,before.mp_example_note.find(n=>n.workspace_id===spaces[k].id)]));
const save=async(name,value)=>writeFile(path.join(outdir,name),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
const log=await open(path.join(outdir,'edge-identity.log'),'wx');
const args=['--headless=new','--disable-gpu','--disable-extensions','--disable-sync','--disable-background-networking','--no-first-run','--no-default-browser-check','--no-proxy-server','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--host-resolver-rules=MAP '+new URL(base).hostname+' 127.0.0.1','--user-data-dir='+profile,'about:blank'];
const started=Date.now(),child=spawn(path.join(process.env['ProgramFiles(x86)'],'Microsoft/Edge/Application/msedge.exe'),args,{windowsHide:true,stdio:['ignore',log.fd,log.fd]});
let exit=null,socket,sequence=0,held=null,holdWanted=false,holdSID;
child.on('exit',(code,signal)=>{exit={code,signal};});
const waiting=new Map(),network=[],blocked=[],websockets=[],exceptions=[],canceled=new Set(),tabs={};
const delay=ms=>new Promise(r=>setTimeout(r,ms));
await save('process-identity-running.json',{pid:child.pid,profile,args,started_at:new Date(started).toISOString()});
function rpc(method,params={},sid=null){
 const id=++sequence;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{waiting.delete(id);reject(Error('CDP timeout '+method));},30000);waiting.set(id,{resolve:v=>{clearTimeout(timer);resolve(v);},reject:e=>{clearTimeout(timer);reject(e);}});socket.send(JSON.stringify({id,method,params,...(sid?{sessionId:sid}:{})}));});
}
async function evaluate(sid,expression){const r=await rpc('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true},sid);if(r.exceptionDetails)throw Error('UI evaluation failed: '+r.exceptionDetails.text);return r.result.value;}
async function until(fn,label,timeout=30000){const end=Date.now()+timeout;while(Date.now()<end){if(exit)throw Error('Owned Edge exited before '+label);if(await fn())return;await delay(40);}throw Error('Timed out: '+label);}
async function createTab(key){const {targetId}=await rpc('Target.createTarget',{url:'about:blank'});const {sessionId:sid}=await rpc('Target.attachToTarget',{targetId,flatten:true});tabs[key]={targetId,sid};for(const method of ['Page.enable','Runtime.enable','Network.enable'])await rpc(method,{},sid);await rpc('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false},sid);await rpc('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'},{urlPattern:origin+'/web/dataset/call_kw*',requestStage:'Response'}]},sid);return sid;}
async function navigate(sid,url){const prior=await evaluate(sid,'performance.timeOrigin');await rpc('Page.navigate',{url},sid);await until(()=>evaluate(sid,`performance.timeOrigin!==${prior}&&location.href===${JSON.stringify(url)}&&document.readyState==='complete'`),'actual navigation');}
const listURL=k=>base+'/app/org.example.notes/?workspace='+spaces[k].public_id;
async function listReady(sid,key){return evaluate(sid,`(()=>{const rows=[...document.querySelectorAll('.o_list_view .o_data_row')];return document.querySelector('.mp_root header select')?.value===${JSON.stringify(spaces[key].public_id)}&&rows.length===1&&rows[0].innerText.includes(${JSON.stringify(notes[key].title)})&&!rows[0].innerText.includes(${JSON.stringify(notes[key==='A'?'B':'A'].title)})&&!document.querySelector('.mp_notice[role="alert"]')})()`);}
async function front(sid){const tab=Object.values(tabs).find(t=>t.sid===sid);await rpc('Target.activateTarget',{targetId:tab.targetId});await rpc('Page.bringToFront',{},sid);await until(()=>evaluate(sid,`document.visibilityState==='visible'&&(!document.querySelector('.mp_main')||getComputedStyle(document.querySelector('.mp_main')).visibility!=='hidden')`),'visible foreground and authority refresh');}
async function switchWorkspace(sid,key){await front(sid);const selected=await evaluate(sid,`(()=>{const e=document.querySelector('.mp_root header select');if(!e||![...e.options].some(o=>o.value===${JSON.stringify(spaces[key].public_id)}))return false;e.value=${JSON.stringify(spaces[key].public_id)};e.dispatchEvent(new Event('change',{bubbles:true}));return true})()`);if(!selected)throw Error('Actual workspace selector unavailable');}
async function screenshot(sid,name){await front(sid);await delay(150);const {data}=await rpc('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},sid);await writeFile(path.join(outdir,name),Buffer.from(data,'base64'),{flag:'wx'});}
async function form(sid,key){await front(sid);await until(()=>listReady(sid,key),'foreground list before form');await evaluate(sid,`document.querySelector('.o_data_row .o_data_cell[name="title"]').click()`);await until(()=>evaluate(sid,`!!document.querySelector('.o_form_view .o_field_widget[name="title"]')&&location.search.includes(${JSON.stringify(notes[key].public_id)})&&!document.querySelector('.mp_notice[role="alert"]')`),'native '+key+' form');return evaluate(sid,`(()=>{const field=document.querySelector('.o_form_view .o_field_widget[name="title"]'),input=field.querySelector('input,textarea');return {title:input?.value||field.textContent.trim(),editable:!!input&&!input.readOnly&&!input.disabled,native_form:true,workspace:document.querySelector('.mp_root header select').value}})()`);}
try{
 let endpoint;await until(async()=>{try{const p=path.join(profile,'DevToolsActivePort');if((await stat(p)).mtimeMs<started)return false;const lines=(await readFile(p,'utf8')).trim().split('\n');if(lines.length===2){endpoint=lines;return true;}}catch{}return false;},'new owned debugger endpoint');
 socket=new WebSocket(`ws://127.0.0.1:${endpoint[0]}${endpoint[1]}`);await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
 socket.addEventListener('message',event=>{const v=JSON.parse(event.data);if(v.id){const item=waiting.get(v.id);if(!item)return;waiting.delete(v.id);v.error?item.reject(Error(v.error.message)):item.resolve(v.result);return;}
  const p=v.params;
  if(v.method==='Runtime.exceptionThrown')exceptions.push({text:p.exceptionDetails.text,line:p.exceptionDetails.lineNumber});
  if(v.method==='Network.loadingFailed'&&p.canceled)canceled.add(p.requestId);
  if(v.method==='Network.responseReceived'){const u=new URL(p.response.url);network.push({origin:u.origin,path:u.pathname,status:p.response.status,type:p.type});}
  if(v.method==='Network.webSocketCreated'){const u=new URL(p.url);websockets.push({origin:u.origin,path:u.pathname});}
  if(v.method==='Fetch.requestPaused'){
   const u=new URL(p.request.url);
   if(['http:','https:'].includes(u.protocol)&&u.origin!==origin){blocked.push({origin:u.origin,path:u.pathname,type:p.resourceType});rpc('Fetch.failRequest',{requestId:p.requestId,errorReason:'BlockedByClient'},v.sessionId).catch(()=>{});return;}
   // Inspect only native RPC routing metadata in memory, never store headers/body.
   if(p.responseStatusCode&&v.sessionId===holdSID&&holdWanted&&u.pathname.startsWith('/web/dataset/call_kw')){
    let body;try{body=JSON.parse(p.request.postData||'{}');}catch{}
    const headers=Object.fromEntries(Object.entries(p.request.headers).map(([k,value])=>[k.toLowerCase(),value]));
    if(body?.params?.model==='mp.example.note'&&body?.params?.method==='web_search_read'&&headers['x-mp-workspace']===spaces.B.public_id){held={requestId:p.requestId,networkId:p.networkId,sid:v.sessionId,status:p.responseStatusCode};holdWanted=false;return;}
   }
   rpc('Fetch.continueRequest',{requestId:p.requestId},v.sessionId).catch(()=>{});
  }
 });
 const version=await rpc('Browser.getVersion');const A=await createTab('A');
 await navigate(A,base+'/web/login');const probe='https://example.invalid/mp-identity-network-probe';if(!await evaluate(A,`fetch(${JSON.stringify(probe)}).then(()=>false).catch(()=>true)`))throw Error('Foreign control was not refused');
 const auth={jsonrpc:'2.0',method:'call',id:1,params:{db:input.database,login:actor.login,password}};
 const uid=await evaluate(A,`fetch('/web/session/authenticate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(${JSON.stringify(auth)})}).then(r=>r.json()).then(v=>v.result?.uid)`);if(uid!==actor.id)throw Error('Actual Alice authentication failed');
 await navigate(A,listURL('A'));await until(()=>listReady(A,'A'),'A native list');await delay(1000);
 const B=await createTab('B');await navigate(B,listURL('B'));await until(()=>listReady(B,'B'),'B native list');
 const initial={A:await listReady(A,'A'),B:await listReady(B,'B')};if(!initial.A||!initial.B)throw Error('Initial two-tab isolation failed');
 await screenshot(A,'identity-tab-A-list.png');await screenshot(B,'identity-tab-B-list.png');
 holdSID=A;holdWanted=true;await switchWorkspace(A,'B');await until(()=>!!held,'real successful B native response held');if(held.status!==200)throw Error('Held native response not successful');
 await delay(1000);await switchWorkspace(A,'A');await until(()=>evaluate(A,`location.search.includes(${JSON.stringify(spaces.A.public_id)})&&document.querySelector('.mp_root header select')?.value===${JSON.stringify(spaces.A.public_id)}`),'A route selected before delayed B response release');
 let release;try{await rpc('Fetch.continueRequest',{requestId:held.requestId},held.sid);release='continued_original_response';}catch{if(!canceled.has(held.networkId))throw Error('Held response release failed without observed cancellation');release='already_canceled_by_disposal';}
 await until(()=>listReady(A,'A'),'A native list after delayed B release');await delay(1200);const afterLate={A:await listReady(A,'A'),B:await listReady(B,'B')};if(!afterLate.A||!afterLate.B)throw Error('Late response contaminated a tab');
 const formA=await form(A,'A');const formB=await form(B,'B');
 if(formA.title!==notes.A.title||!formA.editable||formB.title!==notes.B.title||formB.editable)throw Error('Native form role/cache isolation failed');
 await screenshot(A,'identity-tab-A-form.png');await screenshot(B,'identity-tab-B-form.png');
 const foreign=blocked.filter(x=>x.path!=='/mp-identity-network-probe'),foreignWS=websockets.filter(x=>new URL(x.origin).host!==new URL(origin).host);
 if(foreign.length||foreignWS.length||exceptions.length)throw Error('Unexpected foreign requests or UI exceptions');
 const result={result:'actual_current_two_tab_workspace_native_view_and_late_response_isolation',image:input.image_id,inventory:input.inventory_digest,generation:4,browser:version,initial_native_lists:initial,after_actual_late_response:afterLate,actual_backend_response_held_status:held.status,late_response_release:release,late_request_cancellation_observed:canceled.has(held.networkId),native_forms:{A:formA,B:formB},same_authenticated_Alice_session:true,A_administrator_B_viewer:true,app_foreign_requests:foreign,foreign_websockets:foreignWS,runtime_exception_count:exceptions.length,positive_foreign_control_observed:blocked.some(x=>x.path==='/mp-identity-network-probe'),business_mutations_attempted:0,personal_browser_used:false,new_profile_or_Docker_assets:0,limits:['Real native lists/forms and selector navigation; no application function or response-body replacement.','Only actual native B response paused at response stage, then continued or observed canceled by real disposal; both tabs verified after late response.','No Note/board edit or Labels action here. UI09 and full release closure remain separate.']};
 await save('identity-result.json',result);await save('identity-network.json',{responses:network,blocked,websockets});console.log(JSON.stringify({result:result.result,late_response_release:release,forms_role_isolated:true,foreign_requests:foreign.length,exceptions:exceptions.length}));
}catch(error){const views={};for(const [key,tab]of Object.entries(tabs)){try{views[key]=await evaluate(tab.sid,`({path:location.pathname,workspace:new URL(location.href).searchParams.get('workspace'),selected:document.querySelector('.mp_root header select')?.value,visibility:document.visibilityState,main_visibility:document.querySelector('.mp_main')?getComputedStyle(document.querySelector('.mp_main')).visibility:null,list_rows:document.querySelectorAll('.o_data_row').length,form_present:!!document.querySelector('.o_form_view'),alerts:[...document.querySelectorAll('.mp_notice[role="alert"]')].map(e=>e.innerText),loading:[...document.querySelectorAll('[role="status"]')].map(e=>e.textContent.trim()).filter(t=>t==='Loading…')})`);}catch{views[key]={observation_unavailable:true};}}await save('identity-failure.json',{message:error.message,held:held?{status:held.status,requestCanceled:canceled.has(held.networkId)}:null,exceptions,views});throw error;}
finally{
 if(socket?.readyState===WebSocket.OPEN){try{await rpc('Browser.close');}catch{}socket.close();}
 if(!exit)await Promise.race([new Promise(resolve=>child.once('exit',resolve)),delay(5000)]);
 if(!exit){child.kill();await Promise.race([new Promise(resolve=>child.once('exit',resolve)),delay(5000)]);}
 await save('process-identity.json',{state:exit?'stopped':'termination_requested_verify_pid',pid:child.pid,profile,exit});await log.close();
}
