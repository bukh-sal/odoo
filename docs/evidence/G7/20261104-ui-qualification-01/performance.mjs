// Actual current UI; one owned browser/profile, no application replacements.
import {spawn} from 'node:child_process';
import {readFile,writeFile,open} from 'node:fs/promises';
import path from 'node:path';
import {performance} from 'node:perf_hooks';
const root=process.cwd(),privateDir=path.join(root,'.local/g7-ui-qualification-01');
const readJSON=async p=>JSON.parse(await readFile(p,'utf8'));
const input=await readJSON(path.join(privateDir,'browser-input.json'));
const base=input.base,origin=new URL(base).origin,profile=input.profile;
const passwords=await readJSON(input.password_file),actor=input.fixture.users[input.actor];
const log=await open(path.join(privateDir,'edge-performance.log'),'wx');
const args=['--headless=new','--disable-gpu','--disable-extensions','--disable-sync','--disable-background-networking',
 '--no-first-run','--no-default-browser-check','--no-proxy-server','--remote-debugging-address=127.0.0.1',
 '--remote-debugging-port=0','--host-resolver-rules=MAP '+new URL(base).hostname+' 127.0.0.1','--user-data-dir='+profile,'about:blank'];
const child=spawn(path.join(process.env['ProgramFiles(x86)'],'Microsoft/Edge/Application/msedge.exe'),args,{windowsHide:true,stdio:['ignore',log.fd,log.fd]});
let socket,session,sequence=0,exit=null;const waiting=new Map(),exceptions=[],network=[],blocked=[],websockets=[];
child.on('exit',(code,signal)=>{exit={code,signal};});
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const save=async(name,data)=>writeFile(path.join(privateDir,name),JSON.stringify(data,null,2)+'\n');
await save('process.json',{state:'running',pid:child.pid,profile,args,phase:'performance'});
function rpc(method,params={},sid=session){
 const id=++sequence;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{waiting.delete(id);reject(Error('CDP timeout '+method));},30000);
  waiting.set(id,{resolve:v=>{clearTimeout(timer);resolve(v);},reject:e=>{clearTimeout(timer);reject(e);}});
  socket.send(JSON.stringify({id,method,params,...(sid?{sessionId:sid}:{})}));});
}
async function evaluate(expression){const r=await rpc('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error('UI evaluation failed: '+r.exceptionDetails.text);return r.result.value;}
async function until(fn,label,timeout=30000){const end=Date.now()+timeout;while(Date.now()<end){if(exit)throw Error('Owned Edge exited before '+label);if(await fn())return;await delay(25);}throw Error('Timed out: '+label);}
async function navigate(url){const before=await evaluate('performance.timeOrigin');await rpc('Page.navigate',{url});await until(()=>evaluate(`performance.timeOrigin!==${before}&&location.href===${JSON.stringify(url)}&&document.readyState==='complete'`),'navigation commit');}
async function attach(targetId){({sessionId:session}=await rpc('Target.attachToTarget',{targetId,flatten:true},null));await rpc('Page.enable');await rpc('Runtime.enable');await rpc('Network.enable');await rpc('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});await rpc('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});}
async function press(key,code=key,vk=undefined){for(const type of ['keyDown','keyUp'])await rpc('Input.dispatchKeyEvent',{type,key,code,...(vk?{windowsVirtualKeyCode:vk}: {})});}
async function screenshot(name){const r=await rpc('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(path.join(privateDir,name),Buffer.from(r.data,'base64'));}
async function clickNav(text){const ok=await evaluate(`(()=>{const e=[...document.querySelectorAll('.mp_root aside nav a')].find(e=>e.textContent.trim()===${JSON.stringify(text)});if(!e)return false;e.click();return true})()`);if(!ok)throw Error('Navigation entry missing: '+text);}
const notesURL=base+'/app/org.example.notes/?workspace='+input.workspace;
const nativeReady=()=>evaluate(`(()=>{const root=document.querySelector('.mp_root');return !!root&&!!document.querySelector('.o_list_view .o_data_row')&&!!root.querySelector('aside nav a')&&[...root.querySelectorAll('header button')].some(e=>e.textContent.trim()==='Commands'&&!e.disabled)&&!root.querySelector('.mp_notice[role="alert"]')&&![...root.querySelectorAll('[role="status"]')].some(e=>e.textContent.trim()==='Loading…')})()`);
const settingsReady=()=>evaluate(`location.pathname==='/app/settings'&&!!document.querySelector('section[aria-label="Preferences"]')&&!document.querySelector('.mp_canvas')&&!!document.querySelector('#mp_workspace_name')&&![...document.querySelectorAll('[role="status"]')].some(e=>e.textContent.trim()==='Loading…')`);
const canvasReady=()=>evaluate(`location.pathname==='/app/org.example.canvas/'&&document.querySelector('.mp_canvas input[aria-label="Board name"]')?.value===${JSON.stringify(input.expected_board_name)}&&document.querySelectorAll('.mp_canvas_card').length===1&&![...document.querySelectorAll('[role="status"]')].some(e=>e.textContent.trim()==='Loading…')`);
async function cycle(){await clickNav('Canvas');await until(canvasReady,'loaded minimal Canvas');await clickNav('Settings');await until(settingsReady,'disposed Canvas and usable Settings');}
async function memory(label){await rpc('HeapProfiler.collectGarbage');await delay(150);await rpc('HeapProfiler.collectGarbage');const raw=await rpc('Performance.getMetrics');const metrics=Object.fromEntries(raw.metrics.map(m=>[m.name,m.value]));const dom=await rpc('Memory.getDOMCounters');return {label,heap_used_bytes:metrics.JSHeapUsedSize,heap_total_bytes:metrics.JSHeapTotalSize,...dom,canvas_roots:await evaluate('document.querySelectorAll(".mp_canvas").length')};}
const shellSamples=[],memorySamples=[];let result;
try{
 let endpoint;
 await until(async()=>{try{const v=(await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).trim().split('\n');if(v.length===2){endpoint=v;return true;}}catch{}return false;},'owned debugger endpoint');
 if(!/^\d+$/.test(endpoint[0])||!endpoint[1].startsWith('/devtools/browser/'))throw Error('Unexpected debugger endpoint');
 socket=new WebSocket(`ws://127.0.0.1:${endpoint[0]}${endpoint[1]}`);
 await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
 socket.addEventListener('message',event=>{const v=JSON.parse(event.data);if(v.id){const p=waiting.get(v.id);if(!p)return;waiting.delete(v.id);v.error?p.reject(Error(v.error.message)):p.resolve(v.result);return;}
  if(v.method==='Runtime.exceptionThrown')exceptions.push(v.params.exceptionDetails);
  if(v.method==='Fetch.requestPaused'){
   const p=v.params;let url;try{url=new URL(p.request.url);}catch{}
   if(url&&['http:','https:'].includes(url.protocol)&&url.origin!==origin){blocked.push({origin:url.origin,path:url.pathname,type:p.resourceType});rpc('Fetch.failRequest',{requestId:p.requestId,errorReason:'BlockedByClient'},v.sessionId).catch(()=>{});}
   else rpc('Fetch.continueRequest',{requestId:p.requestId},v.sessionId).catch(()=>{});
  }
  if(v.method==='Network.responseReceived'){const p=v.params;let u;try{u=new URL(p.response.url);}catch{}if(u)network.push({origin:u.origin,path:u.pathname,status:p.response.status,type:p.type,fromDiskCache:!!p.response.fromDiskCache});}
  if(v.method==='Network.webSocketCreated'){const u=new URL(v.params.url);websockets.push({origin:u.origin,path:u.pathname});}
 });
 socket.addEventListener('close',()=>{for(const p of waiting.values())p.reject(Error('Owned debugger socket closed'));waiting.clear();});
 const version=await rpc('Browser.getVersion',{},null);await save('browser-version.json',version);
 const created=await rpc('Target.createTarget',{url:'about:blank'},null);await attach(created.targetId);
 await navigate(base+'/web/login');
 const probe='https://example.invalid/mp-network-probe';const refused=await evaluate(`fetch(${JSON.stringify(probe)}).then(()=>false).catch(()=>true)`);
 if(!refused||!blocked.some(x=>x.origin==='https://example.invalid'&&x.path==='/mp-network-probe'))throw Error('Outbound interception control was not observed/refused');
 for(let i=0;i<4;i++){
  const started=performance.now();const auth={jsonrpc:'2.0',method:'call',id:1,params:{db:input.database,login:actor.login,password:passwords[input.actor]}};
  const authenticated=await evaluate(`fetch('/web/session/authenticate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(${JSON.stringify(auth)})}).then(r=>r.json()).then(v=>({uid:v.result?.uid,error:!!v.error}))`);
  if(authenticated.uid!==actor.id||authenticated.error)throw Error('Actual fixture authentication failed');
  await navigate(notesURL);await until(nativeReady,'real native Notes and shell controls');const nativeMs=performance.now()-started;
  await evaluate(`[...document.querySelectorAll('.mp_root header button')].find(e=>e.textContent.trim()==='Commands').click()`);
  await until(()=>evaluate('!!document.querySelector(".o_command_palette_search")'),'real Odoo command palette');
  const interactiveMs=performance.now()-started;shellSamples.push({sample:i,browser_cache:i?'warm':'cold',login_to_native_ready_ms:nativeMs,login_to_interactive_Odoo_commands_ms:interactiveMs,under3000ms:interactiveMs<3000});
  await press('Escape','Escape',27);await until(()=>evaluate('!document.querySelector(".o_command_palette_search")'),'Odoo Escape disposal');
  if(i===0)await screenshot('native-shell.png');
  console.log(JSON.stringify({shell_sample:i,native_ms:Math.round(nativeMs),interactive_ms:Math.round(interactiveMs)}));
 }
 const measurement=await rpc('Target.createTarget',{url:'about:blank'},null);await rpc('Target.closeTarget',{targetId:created.targetId},null);await attach(measurement.targetId);
 await navigate(notesURL);await until(nativeReady,'measurement native page');await clickNav('Settings');await until(settingsReady,'measurement settings');
 await rpc('Performance.enable');await rpc('HeapProfiler.enable');
 for(let i=0;i<5;i++){await cycle();await delay(500);}
 memorySamples.push(await memory('baseline_after5warmups'));
 for(let i=1;i<=100;i++){
  const started=performance.now();await cycle();await delay(Math.max(0,1000-(performance.now()-started)));
  if(i%20===0){memorySamples.push(await memory('after'+i));await save('performance-progress.json',{phase:'mount_cycles',completed:i,shellSamples,memorySamples});console.log(JSON.stringify({mount_dispose_cycles:i,memory:memorySamples.at(-1)}));}
 }
 const baseline=memorySamples[0],last=memorySamples.at(-1),sixty=memorySamples.find(s=>s.label==='after60');
 const limits={final_heap_growth:Math.max(4*1024**2,baseline.heap_used_bytes*.1),late_heap_growth:Math.max(1024**2,baseline.heap_used_bytes*.03),dom_listener_allowance:32};
 const checks={all100cycles_disposed:last.canvas_roots===0,final_heap_bounded:last.heap_used_bytes-baseline.heap_used_bytes<=limits.final_heap_growth,late_heap_bounded:last.heap_used_bytes-sixty.heap_used_bytes<=limits.late_heap_growth,documents_stable:last.documents===baseline.documents,nodes_bounded:last.nodes<=baseline.nodes+32,listeners_bounded:last.jsEventListeners<=baseline.jsEventListeners+32};
 const foreign=blocked.filter(x=>!(x.origin==='https://example.invalid'&&x.path==='/mp-network-probe'));
 const foreignWebsockets=websockets.filter(x=>new URL(x.origin).host!==new URL(origin).host);
 const assets=network.filter(x=>/\.min\.(js|css)$/.test(x.path));if(!assets.some(x=>x.path.endsWith('.min.js'))||!assets.some(x=>x.path.endsWith('.min.css')))throw Error('Production JS/CSS assets not observed');
 await screenshot('after100-settings.png');
 result={result:'actual_current_shell_and100mount_dispose_measurements',image:input.image_id,generation:input.generation,realm:base,viewport:{width:1280,height:900},shellSamples,shell_target_passed:shellSamples.every(s=>s.under3000ms),cycles:100,warmup_cycles:5,memorySamples,limits,memory_checks:checks,memory_target_passed:Object.values(checks).every(Boolean),runtime_exception_count:exceptions.length,app_foreign_requests:foreign,foreign_websockets:foreignWebsockets,outbound_control_observed_and_refused:true,production_assets:assets,network_response_count:network.length,personal_browser_used:false,
  boundaries:['Numeric post-GC diagnostics only, no heap snapshot or credential/header/body logging.','Existing minimal one-card Canvas mounted/disposed via real navigation; no board/Note edit/save or application function replacement.','Finite100cycle observation and conservative predeclared bounds, not a universal memory/browser guarantee.']};
 await save('performance-result.json',result);await save('network-sanitized.json',{responses:network,blocked,websockets});await save('performance-progress.json',{phase:'completed',cycles:100});
 console.log(JSON.stringify({result:result.result,shell_target_passed:result.shell_target_passed,memory_target_passed:result.memory_target_passed,runtime_exceptions:exceptions.length,foreign_app_requests:foreign.length}));
}catch(error){await save('performance-failure.json',{message:error.message,shellSamples,memorySamples,exceptions});throw error;}
finally{
 if(socket?.readyState===WebSocket.OPEN){try{await rpc('Browser.close',{},null);}catch{}socket.close();}
 if(!exit)await Promise.race([new Promise(resolve=>child.once('exit',resolve)),delay(5000)]);
 if(!exit){child.kill();await Promise.race([new Promise(resolve=>child.once('exit',resolve)),delay(5000)]);}
 await save('process.json',{state:exit?'stopped':'termination_requested_verify_pid',pid:child.pid,profile,exit,phase:'performance'});await log.close();
}
