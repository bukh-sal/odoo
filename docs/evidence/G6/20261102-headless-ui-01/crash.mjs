// Real installed UI in an isolated, project-owned headless Edge profile.
import {spawn} from 'node:child_process';
import {readFile,writeFile,open} from 'node:fs/promises';
import path from 'node:path';
const root=process.cwd(),privateDir=path.join(root,'.local/g6-events/headless-ui-05');
const profile=path.join(privateDir,'profile');
const readJSON=async p=>JSON.parse(await readFile(p,'utf8'));
const state=await readJSON(path.join(root,'.local/g6-events/state.json'));
const fixture=await readJSON(path.join(root,'.local/g6-events/fixtures.json'));
const password=(await readFile(path.join(root,'.local/g6-events/bootstrap-password'),'utf8')).trim();
const config=await readJSON(path.join(root,'.local/g6-events/operator/target.json'));
if(config.generation!==24||state.active_db!==config.sites[0].database)throw Error('Unexpected current test target');
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
await save('process.json',{state:'running',pid:child.pid,profile,args,native_generation:24});
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
    const port=await until(async()=>{const value=(await readFile(path.join(profile,'DevToolsActivePort'),'utf8')).trim().split('\n');return value.length===2?value:null;},'owned debugging endpoint');
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
    const targets=await readJSON(path.join(privateDir,'targets.json'));
    const phase=value=>save('node-phase.json',{state:value});
    const operator=async expected=>(await readJSON(path.join(privateDir,'operator-phase.json'))).state===expected;
    const clickButton=text=>evaluate(`(()=>{const button=[...document.querySelectorAll('button')].find(e=>e.textContent===${JSON.stringify(text)});if(!button)throw Error('Button absent');button.click();return true;})()`);
    const openNote=async target=>{
        await until(()=>evaluate('!!document.querySelector(".o_list_view")'),'native list');
        const title=target.title.replace(/\s+/g,' ').trim();
        await evaluate(`(()=>{const row=[...document.querySelectorAll('.o_data_row')].find(e=>e.innerText.replace(/\\s+/g,' ').includes(${JSON.stringify(title)}));if(!row)throw Error('Known fixture note not visible');row.querySelector('.o_data_cell').click();return true;})()`);
        await until(()=>evaluate(`!!document.querySelector('.o_form_view')&&[...document.querySelectorAll('button')].some(e=>e.textContent==='Analyze saved note')`),'native form and actual action');
    };
    const capture=async name=>{
        await save(name+'-dom.json',await evaluate('({text:document.body.innerText,url:location.href,nativeList:!!document.querySelector(".o_list_view"),nativeForm:!!document.querySelector(".o_form_view")})'));
        const screenshot=await rpc('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
        await writeFile(path.join(privateDir,name+'.png'),Buffer.from(screenshot.data,'base64'));
    };
    await openNote(targets.outage);await clickButton('Analyze saved note');
    await until(()=>evaluate(`document.body.innerText.includes('Analysis is queued for the saved note.')`),'queued outage job');
    await phase('crash_waiting_runner');
    await until(()=>operator('crash_completed'),'independent killed-worker failure',180000);
    await until(()=>evaluate(`document.body.innerText.includes('Analysis is unavailable. Notes are still available.')`),'actual degraded Odoo notification');
    await capture('crash-degraded');await clickButton('All notes');
    await until(()=>evaluate('!!document.querySelector(".o_list_view")'),'native Notes remains usable after outage');
    await capture('crash-native-list');await openNote(targets.outage);await phase('crash_UI_verified');
    await until(()=>operator('worker_recovered'),'independent worker recovery',180000);
    await clickButton('Analyze saved note');await until(()=>evaluate(`document.body.innerText.includes('Analysis is queued for the saved note.')`),'explicit post-recovery analysis queued');
    await phase('recovery_waiting_runner');await until(()=>operator('recovery_completed'),'independent recovery job',180000);
    const stat=targets.outage.statistics;const expected=`Saved revision ${targets.outage.revision}: characters ${stat.characters}, words ${stat.words}, lines ${stat.lines}.`;
    await until(()=>evaluate(`document.body.innerText.includes(${JSON.stringify(expected)})`),'actual post-recovery statistics');await capture('crash-recovered-result');
    if(exceptions.length)throw Error('Unexpected uncaught UI exceptions');
    await save('lifecycle-result.json',{result:'actual_UI_crash_native_survival_and_recovered_result',native_generation:24,
        personal_browser_used:false,nativeViews:true,crash_degraded_notification_verified:true,
        native_list_usable_during_outage:true,explicit_post_recovery_result_verified:true,exception_count:0});
    await phase('complete');console.log('Actual browser worker-crash degraded notification, usable native Notes and post-restart result verified.');
}catch(error){
    if(socket?.readyState===WebSocket.OPEN){try{await save('failure-dom.json',await evaluate('({text:document.body.innerText,url:location.href})'));const shot=await rpc('Page.captureScreenshot',{format:'png'});await writeFile(path.join(privateDir,'failure.png'),Buffer.from(shot.data,'base64'));}catch{}}
    await save('failure.json',{error:error.message,exceptions});throw error;
}finally{
    if(socket?.readyState===WebSocket.OPEN){try{await rpc('Browser.close',{},null);}catch{}socket.close();}
    if(!exit){await Promise.race([new Promise(resolve=>child.once('exit',resolve)),delay(5000)]);}
    if(!exit){child.kill();await Promise.race([new Promise(resolve=>child.once('exit',resolve)),delay(5000)]);}
    await save('process.json',{state:exit?'stopped':'termination_requested_verify_pid',pid:child.pid,profile,exit});await log.close();
}
