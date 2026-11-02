// Real installed UI in an isolated, project-owned headless Edge profile.
import {spawn} from 'node:child_process';
import {readFile,writeFile,open,stat} from 'node:fs/promises';
import path from 'node:path';
const root=process.cwd(),privateDir=path.join(root,'.local/g6-events/g7-native-browser-01');
const profile=path.join(root,'.local/g6-events/headless-ui-05/profile');
const previousPortTime=await stat(path.join(profile,'DevToolsActivePort')).then(s=>s.mtimeMs).catch(()=>null);
const readJSON=async p=>JSON.parse(await readFile(p,'utf8'));
const state=await readJSON(path.join(root,'.local/g6-events/state.json'));
const fixture=await readJSON(path.join(root,'.local/g6-events/fixtures.json'));
const password=(await readFile(path.join(root,'.local/g6-events/bootstrap-password'),'utf8')).trim();
const config=await readJSON(path.join(root,'.local/g6-events/operator/target.json'));
if(config.generation!==25||state.active_db!==config.sites[0].database)throw Error('Unexpected current test target');
const base=`http://127.0.0.1:${state.port}`;
const log=await open(path.join(privateDir,'edge.log'),'wx');
const args=['--headless=new','--disable-gpu','--disable-extensions','--disable-sync','--disable-background-networking',
    '--no-first-run','--no-default-browser-check','--no-proxy-server','--remote-debugging-address=127.0.0.1',
    '--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'];
const child=spawn(path.join(process.env['ProgramFiles(x86)'],'Microsoft/Edge/Application/msedge.exe'),args,
    {windowsHide:true,stdio:['ignore',log.fd,log.fd]});
let socket,sequence=0,session,exit=null;const waiting=new Map(),exceptions=[];
child.on('exit',(code,signal)=>{exit={code,signal};});
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const save=async(name,data)=>writeFile(path.join(privateDir,name),JSON.stringify(data,null,2)+'\n');
await save('process.json',{state:'running',pid:child.pid,profile,args,native_generation:25});
async function until(fn,label,timeout=45000){const end=Date.now()+timeout;let last;while(Date.now()<end){if(exit)throw Error('Owned Edge exited before '+label);try{const result=await fn();if(result)return result;}catch(e){last=e;}await delay(200);}throw Error('Timed out: '+label+(last?' ('+last.message+')':''));}
function rpc(method,params={},sessionId=session){
    const id=++sequence;return new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>{waiting.delete(id);reject(Error('CDP timeout '+method));},30000);
        waiting.set(id,{resolve:v=>{clearTimeout(timer);resolve(v);},reject:e=>{clearTimeout(timer);reject(e);}});
        socket.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));
    });
}
async function evaluate(expression){const value=await rpc('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(value.exceptionDetails)throw Error('Evaluation failed: '+value.exceptionDetails.text);return value.result.value;}
async function navigate(url){await rpc('Page.navigate',{url});await until(()=>evaluate('document.readyState==="complete"'),'document complete');}
try{
    const port=await until(async()=>{if((await stat(path.join(profile,'DevToolsActivePort'))).mtimeMs===previousPortTime)return null;const value=(await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).trim().split('\n');return value.length===2?value:null;},'owned debugging endpoint');
    if(!/^\d+$/.test(port[0])||!port[1].startsWith('/devtools/browser/'))throw Error('Invalid owned endpoint');
    socket=new WebSocket(`ws://127.0.0.1:${port[0]}${port[1]}`);
    await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
    socket.addEventListener('message',event=>{const value=JSON.parse(event.data);if(value.id){const pending=waiting.get(value.id);if(!pending)return;waiting.delete(value.id);if(value.error)pending.reject(Error(value.error.message));else pending.resolve(value.result);}else if(value.method==='Runtime.exceptionThrown')exceptions.push(value.params.exceptionDetails);});
    const {targetId}=await rpc('Target.createTarget',{url:'about:blank'},null);
    ({sessionId:session}=await rpc('Target.attachToTarget',{targetId,flatten:true},null));
    await rpc('Page.enable');await rpc('Runtime.enable');await rpc('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});
    await navigate(base+'/web/login');
    const auth={jsonrpc:'2.0',method:'call',id:1,params:{db:state.active_db,login:fixture.users.alice.login,password}};
    const authenticated=await evaluate(`fetch('/web/session/authenticate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(${JSON.stringify(auth)})}).then(r=>r.json()).then(v=>({uid:v.result?.uid,error:!!v.error}))`);
    if(authenticated.uid!==fixture.users.alice.id||authenticated.error)throw Error('Fixture authentication failed');
    await navigate(base+'/app/org.example.notes/?workspace='+fixture.workspaces.C.public_id);
    await until(()=>evaluate('!!document.querySelector(".o_list_view")'),'real native Notes list');
    await evaluate(`(()=>{const row=[...document.querySelectorAll('.o_data_row')].find(e=>e.innerText.includes('Owned restored native job'));if(!row)throw Error('Known fixture note not visible');row.querySelector('.o_data_cell').click();return true;})()`);
    await until(()=>evaluate(`!!document.querySelector('.o_form_view')&&[...document.querySelectorAll('button')].some(e=>e.textContent==='Analyze saved note')`),'native form and real contribution');
    await evaluate(`[...document.querySelectorAll('button')].find(e=>e.textContent==='Analyze saved note').click()`);
    await until(()=>evaluate(`document.body.innerText.includes('Saved revision 2: characters 50, words 7, lines 1.')`),'actual cached result notification');
    const dom=await evaluate(`({url:location.href,title:document.title,text:document.body.innerText,nativeForm:!!document.querySelector('.o_form_view'),notification:[...document.querySelectorAll('.o_notification')].map(e=>e.innerText)})`);
    await save('healthy-dom.json',dom);
    const screenshot=await rpc('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    await writeFile(path.join(privateDir,'healthy.png'),Buffer.from(screenshot.data,'base64'));
    await save('healthy-result.json',{result:'actual_native_form_analysis_result_rendered',owned_profile:true,personal_browser_used:false,
        native_generation:25,nativeForm:dom.nativeForm,expected_saved_revision_statistics_visible:true,exception_count:exceptions.length});
    console.log('Actual native Notes form contribution displayed correct saved revision2 statistics via Odoo notification.');
}catch(error){
    if(socket?.readyState===WebSocket.OPEN){try{await save('failure-dom.json',await evaluate('({text:document.body.innerText,url:location.href})'));const shot=await rpc('Page.captureScreenshot',{format:'png'});await writeFile(path.join(privateDir,'failure.png'),Buffer.from(shot.data,'base64'));}catch{}}
    await save('failure.json',{error:error.message,exceptions});throw error;
}finally{
    if(socket?.readyState===WebSocket.OPEN){try{await rpc('Browser.close',{},null);}catch{}socket.close();}
    if(!exit){await Promise.race([new Promise(resolve=>child.once('exit',resolve)),delay(5000)]);}
    if(!exit){child.kill();await Promise.race([new Promise(resolve=>child.once('exit',resolve)),delay(5000)]);}
    await save('process.json',{state:exit?'stopped':'termination_requested_verify_pid',pid:child.pid,profile,exit});await log.close();
}
