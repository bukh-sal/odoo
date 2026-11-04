// Owned Edge/CDP test plumbing. No personal browser, extensions or app overrides.
import {spawn} from 'node:child_process';
import {readFile,writeFile,open,stat} from 'node:fs/promises';
import path from 'node:path';
export async function browserRuntime(outdir){
 const parent=path.join(process.cwd(),'.local/g7-ui-core24-01');
 const load=async name=>JSON.parse(await readFile(name,'utf8'));
 const input=await load(path.join(parent,'browser-input.json')),before=await load(path.join(parent,'tables-before.json'));
 const origin=new URL(input.base).origin,profile=input.profile,log=await open(path.join(outdir,'edge.log'),'wx');
 const args=['--headless=new','--disable-gpu','--disable-extensions','--disable-sync','--disable-background-networking','--no-first-run','--no-default-browser-check','--no-proxy-server','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--host-resolver-rules=MAP '+new URL(origin).hostname+' 127.0.0.1','--user-data-dir='+profile,'about:blank'];
 const started=Date.now(),child=spawn(path.join(process.env['ProgramFiles(x86)'],'Microsoft/Edge/Application/msedge.exe'),args,{windowsHide:true,stdio:['ignore',log.fd,log.fd]});
 let exit=null,socket,sequence=0,sid=null,holdNavigation=false,held=null;
 const waiters=new Map(),network=[],blocked=[],websockets=[],exceptions=[];
 child.on('exit',(code,signal)=>{exit={code,signal};});
 const delay=ms=>new Promise(r=>setTimeout(r,ms));
 const save=async(name,value)=>writeFile(path.join(outdir,name),JSON.stringify(value,null,2)+'\n',{flag:'wx'});
 await save('process-running.json',{pid:child.pid,profile,args,started_at:new Date(started).toISOString()});
 function rpc(method,params={},session=sid){const id=++sequence;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{waiters.delete(id);reject(Error('CDP timeout '+method));},30000);waiters.set(id,{resolve:v=>{clearTimeout(timer);resolve(v);},reject:e=>{clearTimeout(timer);reject(e);}});socket.send(JSON.stringify({id,method,params,...(session?{sessionId:session}:{})}));});}
 async function evaluate(expression){const r=await rpc('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error('UI evaluation: '+r.exceptionDetails.text);return r.result.value;}
 async function until(fn,label,timeout=20000){const end=Date.now()+timeout;while(Date.now()<end){if(exit)throw Error('Owned browser exited: '+label);if(await fn())return;await delay(40);}throw Error('Timed out: '+label);}
 async function key(key,code=key,vk=undefined,modifiers=0){for(const type of ['keyDown','keyUp'])await rpc('Input.dispatchKeyEvent',{type,key,code,modifiers,...(vk?{windowsVirtualKeyCode:vk}:{}),...(type==='keyDown'&&!modifiers&&(key==='Enter'||key.length===1)?{text:key==='Enter'?'\r':key,unmodifiedText:key==='Enter'?'\r':key}:{})});}
 async function navigate(url){const previous=await evaluate('performance.timeOrigin');await rpc('Page.navigate',{url});await until(()=>evaluate(`performance.timeOrigin!==${previous}&&location.href===${JSON.stringify(url)}&&document.readyState==='complete'`),'navigation commit');}
 async function screenshot(name){const r=await rpc('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(path.join(outdir,name),Buffer.from(r.data,'base64'),{flag:'wx'});}
 async function select(selector,value){const ok=await evaluate(`(()=>{const e=document.querySelector(${JSON.stringify(selector)});if(!e)return false;e.value=${JSON.stringify(value)};e.dispatchEvent(new Event('change',{bubbles:true}));return true})()`);if(!ok)throw Error('Select control unavailable: '+selector);}
 async function clickText(selector,text){const ok=await evaluate(`(()=>{const e=[...document.querySelectorAll(${JSON.stringify(selector)})].find(e=>e.textContent.trim()===${JSON.stringify(text)});if(!e)return false;e.click();return true})()`);if(!ok)throw Error('Control unavailable: '+text);}
 async function ax(selector){const r=await rpc('Runtime.evaluate',{expression:`document.querySelector(${JSON.stringify(selector)})`,returnByValue:false});if(!r.result.objectId)return null;try{const a=await rpc('Accessibility.getPartialAXTree',{objectId:r.result.objectId,fetchRelatives:false});return a.nodes.map(n=>({role:n.role?.value,name:n.name?.value,ignored:n.ignored}));}finally{await rpc('Runtime.releaseObject',{objectId:r.result.objectId});}}
 async function close(){if(socket?.readyState===WebSocket.OPEN){try{await rpc('Browser.close',{},null);}catch{}socket.close();}if(!exit)await Promise.race([new Promise(resolve=>child.once('exit',resolve)),delay(5000)]);if(!exit){child.kill();await Promise.race([new Promise(resolve=>child.once('exit',resolve)),delay(5000)]);}await save('process.json',{state:exit?'stopped':'termination_requested_verify_pid',pid:child.pid,profile,exit});await log.close();}
 try{
  let endpoint;await until(async()=>{try{const p=path.join(profile,'DevToolsActivePort');if((await stat(p)).mtimeMs<started)return false;endpoint=(await readFile(p,'utf8')).trim().split('\n');return endpoint.length===2;}catch{return false;}},'new owned debugger endpoint');
  socket=new WebSocket(`ws://127.0.0.1:${endpoint[0]}${endpoint[1]}`);await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
  socket.addEventListener('message',event=>{const v=JSON.parse(event.data);if(v.id){const w=waiters.get(v.id);if(!w)return;waiters.delete(v.id);v.error?w.reject(Error(v.error.message)):w.resolve(v.result);return;}
   const p=v.params;
   if(v.method==='Runtime.exceptionThrown')exceptions.push({text:p.exceptionDetails.text,line:p.exceptionDetails.lineNumber});
   if(v.method==='Network.responseReceived'){const u=new URL(p.response.url);network.push({origin:u.origin,path:u.pathname,status:p.response.status,type:p.type});}
   if(v.method==='Network.webSocketCreated'){const u=new URL(p.url);websockets.push({origin:u.origin,path:u.pathname});}
   if(v.method==='Fetch.requestPaused'){const u=new URL(p.request.url);if(['http:','https:'].includes(u.protocol)&&u.origin!==origin){blocked.push({origin:u.origin,path:u.pathname,type:p.resourceType});rpc('Fetch.failRequest',{requestId:p.requestId,errorReason:'BlockedByClient'},v.sessionId).catch(()=>{});return;}if(holdNavigation&&p.responseStatusCode&&u.pathname==='/api/v1/navigation'){holdNavigation=false;held={id:p.requestId,sid:v.sessionId,status:p.responseStatusCode};return;}rpc('Fetch.continueRequest',{requestId:p.requestId},v.sessionId).catch(()=>{});}
  });
  const version=await rpc('Browser.getVersion',{},null);await save('browser-version.json',version);
  const {targetId}=await rpc('Target.createTarget',{url:'about:blank'},null);({sessionId:sid}=await rpc('Target.attachToTarget',{targetId,flatten:true},null));
  for(const method of ['Page.enable','Runtime.enable','Network.enable'])await rpc(method);
  await rpc('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});await rpc('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'},{urlPattern:origin+'/api/v1/navigation*',requestStage:'Response'}]});
  await navigate(input.base+'/web/login');const probe='https://example.invalid/mp-ui09-network-probe';if(!await evaluate(`fetch(${JSON.stringify(probe)}).then(()=>false).catch(()=>true)`))throw Error('Foreign control not refused');
  const passwords=await load(input.password_file),actor=input.fixture.users[input.actor];const auth={jsonrpc:'2.0',method:'call',id:1,params:{db:input.database,login:actor.login,password:passwords[input.actor]}};
  if(await evaluate(`fetch('/web/session/authenticate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(${JSON.stringify(auth)})}).then(r=>r.json()).then(v=>v.result?.uid)`)!==actor.id)throw Error('Authentication failed');
  return {input,before,outdir,origin,save,rpc,evaluate,until,key,navigate,screenshot,select,clickText,ax,delay,close,network,blocked,websockets,exceptions,holdNextNavigation:()=>{holdNavigation=true;held=null;},held:()=>held,releaseNavigation:async()=>{if(held){await rpc('Fetch.continueRequest',{requestId:held.id},held.sid);held=null;}}};
 }catch(error){await close();throw error;}
}
