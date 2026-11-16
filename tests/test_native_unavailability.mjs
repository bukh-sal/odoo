import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import test from 'node:test';

const root=fileURLToPath(new URL('../',import.meta.url));
const target=root;
const base='framework_addons/web/static/src/';
const strip=text=>text.replace(/^import[\s\S]*?from\s*["'][^"']+["'];\r?\n/gm,'').replace(/\bexport (?=(?:class|const|function)\b)/g,'');
async function evaluate(path,context,returns,at=target){
 const code=strip(await readFile(resolve(at,base+path),'utf8'));
 return new Function(...Object.keys(context),code+'\nreturn {'+returns+'};')(...Object.values(context));
}
class Component {constructor(props={}){this.props=props;}}
class EventBus {addEventListener(){}}
async function fixture(){
 const categories=new Map(),listeners=new Map(),records=[],logs=[];let reads=0;
 const registry={category(name){if(!categories.has(name))categories.set(name,new Map());const map=categories.get(name);return{add(name,value,options={}){map.set(name,{value,sequence:options.sequence??50});return this;},contains:name=>map.has(name),get:name=>map.get(name).value,getEntries:()=>[...map].sort((a,b)=>a[1].sequence-b[1].sequence).map(([name,row])=>[name,row.value])};}};
 const browser={addEventListener:(name,fn)=>listeners.set(name,fn),setTimeout(){throw Error('No timer/retry expected');},navigator:{clipboard:{writeText(){throw Error('No clipboard action expected');}}}};
 const rpc=await evaluate('core/network/rpc.js',{EventBus,browser,omit:()=>({})},'RPCError,makeErrorFromResponse,ConnectionLostError,RequestEntityTooLargeError,rpc',root);
 const service=await evaluate('core/errors/error_service.js',{browser,registry,completeUncaughtError:async(uncaught)=>{uncaught.traceback='bounded test traceback';},getErrorTechnicalName:object=>object.constructor.name,isBrowserFirefox:()=>false,isBrowserChrome:()=>false,odoo:{debug:false},console:{error:value=>logs.push(value)}},'UncaughtClientError,UncaughtPromiseError,ThirdPartyScriptError,errorService',root);
 const dialogs=await evaluate('core/errors/error_dialogs.js',{browser,Dialog:Component,_t:value=>value,registry,Tooltip:Component,usePopover:()=>({open(){},close(){}}),useService:()=>({}),capitalize:value=>value,Component,useRef:()=>({el:null}),useState:value=>value,markup:value=>value,luxon:{DateTime:{now:()=>({setZone:()=>({toFormat:()=>'<test-time>'})})}}},'RPCErrorDialog,WarningDialog,ErrorDialog,ClientErrorDialog,NetworkErrorDialog,RequestEntityTooLargeErrorDialog'+((await readFile(resolve(target,base+'core/errors/error_dialogs.js'),'utf8')).includes('export class PageUnavailableDialog')?',PageUnavailableDialog':''));
 const handlers=await evaluate('core/errors/error_handlers.js',{_t:value=>value,browser,...rpc,registry,session:{},user:{isInternalUser:true},...dialogs,...service,odoo:{debug:false}},'rpcErrorHandler');
 const env={services:{menu:{reload:async()=>{reads++;}},notification:{add:()=>{}},dialog:{add:(Class,props,options={})=>{const row={Class,props,options};records.push(row);row.instance=new Class({...props,close:()=>options.onClose?.()});row.instance.setup?.();return()=>options.onClose?.();}}}};
 service.errorService.start(env);
 async function emit(original){const event={reason:original,defaultPrevented:false,preventDefault(){this.defaultPrevented=true;}};await listeners.get('unhandledrejection')(event);await Promise.resolve();return event;}
 return{env,records,logs,registry,rpc,handlers,dialogs,emit,get reads(){return reads;}};
}
const response=(code=404,name='werkzeug.exceptions.NotFound')=>({code,message:'private customer name',data:{name,message:'private customer name',debug:'private stack',arguments:['private details']}});

test('real RPC construction/service path turns concurrent removed-model404 into one private-free page message',async()=>{
 const f=await fixture();const error=f.rpc.makeErrorFromResponse(response());await f.emit(error);await f.emit(f.rpc.makeErrorFromResponse(response()));
 assert.equal(f.records.length,1);const row=f.records[0];assert.equal(row.instance.title,'Page unavailable');assert.match(row.instance.message,/no longer available/);assert.match(row.instance.message,/unsaved changes/);
 assert.deepEqual(row.props,{});assert.doesNotMatch(row.instance.message,/private|stack|customer name/);assert.equal(f.reads,1);
});
test('real access and missing-action failures share the open message without changing the failed request',async()=>{
 const f=await fixture();const first=f.rpc.makeErrorFromResponse(response(200,'odoo.exceptions.AccessError'));const before=Object.getOwnPropertyDescriptors(first);
 const event=await f.emit(first);await f.emit(f.rpc.makeErrorFromResponse(response(200,'odoo.addons.web.controllers.action.MissingActionError')));
 assert.equal(f.records.length,1);assert.equal(f.records[0].instance.title,'Page unavailable');assert.equal(event.defaultPrevented,true);
 for(const key of ['code','data','message','exceptionName'])assert.deepEqual(Object.getOwnPropertyDescriptor(first,key),before[key]);
});
test('closing permits a later failure; independent web environments are never silenced',async()=>{
 const f=await fixture();await f.emit(f.rpc.makeErrorFromResponse(response()));f.records[0].options.onClose?.();await f.emit(f.rpc.makeErrorFromResponse(response()));assert.equal(f.records.length,2);assert.equal(f.records[1].instance.title,'Page unavailable');
 const other=await fixture();await other.emit(other.rpc.makeErrorFromResponse(response()));assert.equal(other.records.length,1);assert.equal(other.reads,1);
});
test('nullable missing-model data is expected; nullable500 remains the diagnostic RPC path',async()=>{
 const f=await fixture();await f.emit(f.rpc.makeErrorFromResponse({code:404,message:'404: Not Found'}));assert.equal(f.records[0].instance.title,'Page unavailable');
 const g=await fixture();await g.emit(g.rpc.makeErrorFromResponse({code:500,message:'Unexpected fault'}));assert.equal(g.records.length,1);assert.equal(g.records[0].Class,g.dialogs.RPCErrorDialog);assert.equal(g.records[0].props.code,500);
});
test('validation, conflict, release, session, network and caller lookalikes never select the expected-page message',async()=>{
 const names=['odoo.exceptions.ValidationError','odoo.exceptions.UserError','odoo.addons.mp_identity.release.ClientReleaseMismatch','odoo.http.SessionExpiredException'];
 for(const name of names){const f=await fixture();await f.emit(f.rpc.makeErrorFromResponse(response(200,name)));assert.notEqual(f.records[0]?.instance.title,'Page unavailable',name);assert.equal(f.reads,0);}
 const f=await fixture();const handler=f.registry.category('error_handlers').getEntries().find(([name])=>name==='pageUnavailableHandler')?.[1];
 for(const error of [{code:404,exceptionName:'werkzeug.exceptions.NotFound'},new Error('404'),new f.rpc.ConnectionLostError('/owned')])assert.equal(handler?.(f.env,{},error)||false,false);
});
test('failed navigation refresh neither retries nor creates another unhandled error',async()=>{
 const f=await fixture();let reads=0;f.env.services.menu.reload=async()=>{reads++;throw Error('read unavailable');};await f.emit(f.rpc.makeErrorFromResponse(response()));await Promise.resolve();await Promise.resolve();assert.equal(f.records.length,1);assert.equal(f.records[0].instance.title,'Page unavailable');assert.equal(reads,1);assert.equal(f.logs.length,0);
});
test('explicit owner dialog and notification choices keep their existing dispatch',async()=>{
 class OwnerDialog extends Component {}
 const f=await fixture();const explicit=f.rpc.makeErrorFromResponse(response());explicit.Component=OwnerDialog;await f.emit(explicit);assert.equal(f.records[0].Class,OwnerDialog);assert.equal(f.reads,0);
 const g=await fixture();g.registry.category('error_dialogs').add('odoo.exceptions.AccessError',OwnerDialog);await g.emit(g.rpc.makeErrorFromResponse(response(200,'odoo.exceptions.AccessError')));assert.equal(g.records[0].Class,OwnerDialog);assert.equal(g.reads,0);
 const h=await fixture();let notified=0;h.env.services.notification.add=()=>notified++;h.registry.category('error_notifications').add('odoo.exceptions.AccessError',{message:'Owner decision'});await h.emit(h.rpc.makeErrorFromResponse(response(200,'odoo.exceptions.AccessError')));assert.equal(notified,1);assert.equal(h.records.length,0);assert.equal(h.reads,0);
});
test('a failed dialog mount releases the latch and leaves the original error diagnosable',async()=>{
 const f=await fixture();const add=f.env.services.dialog.add;let failed=true;f.env.services.dialog.add=(...args)=>{if(failed){failed=false;throw Error('mount failed');}return add(...args);};await f.emit(f.rpc.makeErrorFromResponse(response()));assert.equal(f.logs.length,1);await f.emit(f.rpc.makeErrorFromResponse(response()));assert.equal(f.records.length,1);assert.equal(f.records[0].instance.title,'Page unavailable');
});
test('actual Shell retains its inline hidden-canvas contract without opening a second blocking dialog',async()=>{
 const effects=[],dialogs=[],actions=[];const model={dirty:true,text:'owned unsaved draft'};const controller={model};const services={menu:{unavailable:true,getApps:()=>[],getCurrentApp:()=>null},action:{currentController:controller,doAction:(...a)=>actions.push(a)},command:{},dialog:{add:(...a)=>dialogs.push(a)},ui:{isSmall:false}};const blank=class{};
 const module=await evaluate('webclient/shell/shell.js',{Component,useEffect:fn=>effects.push(fn),useExternalListener(){},useRef:()=>({el:{focus(){},contains:()=>false}}),useState:x=>x,useSubEnv(){},xml:parts=>parts.join(''),browser:{},useBus(){},useService:name=>services[name],registry:{category:()=>({contains:()=>false})},Dropdown:blank,DropdownItem:blank,ErrorHandler:blank,UserMenu:blank,user:{},Dialog:Component,_t:x=>x,PageHeader:blank,StatusMessage:blank,Icon:blank,ContextNav:blank,useContextPreference:()=>({collapsed:false}),useRailPreferences:()=>({pins:null,apps:[]}),window:{},document:{activeElement:null}},'Shell');
 const shell=new module.Shell();shell.env={bus:{}};shell.setup();effects.forEach(fn=>fn());assert.equal(shell.blocked,true);assert.equal(dialogs.length,0);assert.equal(services.action.currentController,controller);assert.equal(controller.model,model);assert.equal(model.text,'owned unsaved draft');assert.deepEqual(actions,[]);
 const template=await readFile(resolve(root,base+'webclient/shell/shell.xml'),'utf8');assert.match(template,/class="mp-shell-action" t-att-hidden="blocked"[^>]*><t t-slot="default"/);assert.match(template,/t-if="blocked"[^>]*role="alert"/);assert.match(template,/t-on-click="reopenWorkspace"/);
});

test('empty canvas allocation never hides or unmounts a loaded controller or draft',async()=>{
 const blank=class{};
 const {Shell}=await evaluate('webclient/shell/shell.js',{Component,Dropdown:blank,DropdownItem:blank,ErrorHandler:blank,UserMenu:blank,PageHeader:blank,StatusMessage:blank,Icon:blank,ContextNav:blank,_t:text=>text},'Shell');
 const shell=Object.create(Shell.prototype);let apps=[],current=null;
 shell.menu={getApps:()=>apps,getCurrentApp:()=>current,unavailable:false};
 shell.action={currentController:null};assert.equal(shell.emptyCanvas,true);
 apps=[{id:1}];current=apps[0];assert.equal(shell.emptyCanvas,false);
 apps=[];current=null;
 const model={dirty:true,text:'keep this draft'};const controller={model};
 shell.action.currentController=controller;assert.equal(shell.emptyCanvas,false);
 shell.menu.unavailable=true;assert.equal(shell.blocked,true);assert.equal(shell.emptyCanvas,false);
 assert.equal(shell.action.currentController,controller);assert.equal(controller.model,model);
 assert.equal(model.text,'keep this draft');
 const template=await readFile(resolve(root,base+'webclient/shell/shell.xml'),'utf8');
 assert.match(template,/t-att-class="\{'is-empty': emptyCanvas\}"/);
 assert.match(template,/class="mp-shell-action" t-att-hidden="blocked"[^>]*><t t-slot="default"/);
});

test('actual Shell distinguishes no selected page from an empty or unavailable workspace',async()=>{
 const blank=class{};
 const {Shell}=await evaluate('webclient/shell/shell.js',{Component,Dropdown:blank,DropdownItem:blank,ErrorHandler:blank,UserMenu:blank,PageHeader:blank,StatusMessage:blank,Icon:blank,ContextNav:blank,_t:text=>text},'Shell');
 const shell=Object.create(Shell.prototype);let apps=[];
 shell.menu={getApps:()=>apps,unavailable:false,currentAppUnavailable:false};
 assert.equal(shell.noAppsTitle,'No applications available in this workspace');
 assert.match(shell.noAppsDescription,/Background jobs/);
 apps=[{id:1,name:'Available application'}];
 assert.equal(shell.noAppsTitle,'Choose a page to continue');
 assert.match(shell.noAppsDescription,/sidebar, All apps, or search/);
 assert.equal(shell.blocked,false);
 shell.menu.unavailable=true;assert.equal(shell.blocked,true);
 const template=await readFile(resolve(root,base+'webclient/shell/shell.xml'),'utf8');
 assert.match(template,/t-if="blocked"/);
 assert.match(template,/t-elif="!current and !action.currentController"/);
 assert.ok(template.indexOf('t-if="blocked"')<template.indexOf('t-elif="!current and !action.currentController"'));
});
