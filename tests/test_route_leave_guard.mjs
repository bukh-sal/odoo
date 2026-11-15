import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const root=new URL('../framework_addons/web/static/src/',import.meta.url);
const read=path=>readFile(new URL(path,root),'utf8');
const noImports=value=>value.replace(/^import .*;\r?\n/gm,'');
let serial=0;
const load=(source)=>import('data:text/javascript;base64,'+Buffer.from(source).toString('base64')+'#'+serial++);
const objects=await load(await read('core/utils/objects.js'));
globalThis.routeObjects=objects;
const arrays=await load('const _shallowEqual=globalThis.routeObjects.shallowEqual;\n'+noImports(await read('core/utils/arrays.js')));
const strings=await load('const isObject=globalThis.routeObjects.isObject;\n'+noImports(await read('core/utils/strings.js')));
const routerSource=noImports(await read('core/browser/router.js'));
const clientSource=await read('webclient/webclient.js');
const routeHandler=clientSource.match(/useBus\(routerBus, "ROUTE_CHANGE", (async[\s\S]*?)\n        \}\);/)[1]+'\n        }';
const actionSource=await read('webclient/actions/action_service.js');
const leaveMethod=actionSource.match(/export async function clearUncommittedChanges[\s\S]*?\n\}/)[0].replace('export ','');
const clearUncommittedChanges=new Function(leaveMethod+';return clearUncommittedChanges;')();

async function fixture(initial='http://review.invalid/odoo/partners?workspace=A',entry=null) {
    const listeners=new Map(),events=[],traversals=[];
    let index=0;const entries=[{url:initial,state:entry}];
    const emit=(name,event)=>{for(const fn of listeners.get(name)||[])fn(event);};
    const document={title:'Review',body:{style:{}}};
    const history={get state(){return entries[index].state;},get length(){return entries.length;},
        pushState(state,_title,url){entries.splice(index+1);entries.push({state:structuredClone(state),url:new URL(url,entries[index].url).href});index++;},
        replaceState(state,_title,url){entries[index]={state:structuredClone(state),url:new URL(url,entries[index].url).href};},
        go(delta){traversals.push(delta);const next=index+delta;assert.ok(next>=0&&next<entries.length);index=next;emit('popstate',{state:history.state});}};
    const browser={history,get location(){return new URL(entries[index].url);},performance:{timeOrigin:123456},
        addEventListener:(name,fn)=>listeners.set(name,[...(listeners.get(name)||[]),fn]),clearTimeout,setTimeout};
    class EventBus {trigger(type,detail){events.push({type,detail});}}
    globalThis.routeFixture={browser,document,luxon:{DateTime:{}},session:{},shallowEqual:objects.shallowEqual};
    const urls=await load('const {browser,document,luxon,session,shallowEqual}=globalThis.routeFixture;\n'+noImports(await read('core/utils/urls.js')));
    globalThis.routeFixture={browser,document,EventBus,omit:objects.omit,pick:objects.pick,slidingWindow:arrays.slidingWindow,
        isNumeric:strings.isNumeric,compareUrls:urls.compareUrls,objectToUrlEncodedString:urls.objectToUrlEncodedString,isDisplayStandalone:()=>false};
    const prefix='const {browser,document,EventBus,omit,pick,slidingWindow,isNumeric,compareUrls,objectToUrlEncodedString,isDisplayStandalone}=globalThis.routeFixture;\n';
    const actual=await load(prefix+routerSource);
    // The initial native action commits its route through the same public router API.
    if (entry === null) actual.router.replaceState({ ...actual.router.current }, { sync: true });
    const client={env:{bus:{trigger:(type,callbacks)=>callbacks.push(async()=>false)}},loads:0,loadRouterState:async()=>{client.loads++;}};
    const factory=new Function('document','router','clearUncommittedChanges','return '+routeHandler);
    const handler=factory.call(client,document,actual.router,clearUncommittedChanges);
    const push=(action,extra={})=>actual.router.pushState({action,...extra},{sync:true});
    const last=()=>events.filter(e=>e.type==='ROUTE_CHANGE').at(-1);
    return {...actual,browser,document,entries,events,traversals,push,last,client,handler,emit,get index(){return index;}};
}
test('refused Back restores route and router scope without discarding/reloading or overwriting history entries',async()=>{
    const f=await fixture();f.push('workboard',{workboard_task:'task',workspace:'A'});const before=structuredClone(f.entries);
    f.browser.history.go(-1);assert.equal(f.router.current.action,'partners');
    await f.handler.call(f.client,{detail:f.last().detail});
    assert.equal(f.client.loads,0);assert.equal(f.router.current.action,'workboard');assert.equal(f.router.current.workspace,'A');
    assert.match(f.browser.location.href,/workboard/);assert.deepEqual(f.entries,before);assert.deepEqual(f.traversals,[-1,1]);
    assert.equal(f.document.body.style.pointerEvents,'auto');assert.equal(f.events.length,1);
});
test('refused Forward undoes in the opposite direction, preserving the future destination',async()=>{
    const f=await fixture();f.push('workboard');f.browser.history.go(-1);
    f.router.replaceState({action:'partners'},{sync:true});const before=structuredClone(f.entries);
    f.browser.history.go(1);await f.handler.call(f.client,{detail:f.last().detail});
    assert.equal(f.router.current.action,'partners');assert.match(f.browser.location.href,/partners/);assert.deepEqual(f.entries,before);
    assert.deepEqual(f.traversals,[-1,1,-1]);assert.equal(f.client.loads,0);
});
test('accepted traversal reaches the existing loader without an undo',async()=>{
    const f=await fixture();f.push('workboard');f.browser.history.go(-1);
    f.client.env.bus.trigger=(type,callbacks)=>callbacks.push(async()=>true);
    await f.handler.call(f.client,{detail:f.last().detail});assert.equal(f.client.loads,1);assert.equal(f.router.current.action,'partners');assert.deepEqual(f.traversals,[-1]);
});
test('legacy unindexed entry restores the visible committed route in place, without loading a foreign scope',async()=>{
    const f=await fixture();f.push('workboard',{workspace:'A'});f.entries[0]={url:'http://review.invalid/odoo/partners?workspace=B',state:null};
    f.browser.history.go(-1);await f.handler.call(f.client,{detail:f.last().detail});
    assert.equal(f.client.loads,0);assert.equal(f.router.current.workspace,'A');assert.match(f.browser.location.href,/workboard.*workspace=A/);
    assert.deepEqual(f.traversals,[-1]);assert.equal(f.entries.length,2);
});
test('a stale refusal cannot roll back a newly committed destination',async()=>{
    const f=await fixture();f.push('workboard');f.browser.history.go(-1);const stale=f.last().detail;
    f.router.replaceState({action:'documents'},{sync:true});const url=f.browser.location.href;
    assert.equal(f.router.cancelRouteChange(stale),false);assert.equal(f.browser.location.href,url);assert.equal(f.router.current.action,'documents');
});
test('reload retains owned positions; malformed metadata gets a fresh bounded position',async()=>{
    const old={nextState:{action:'partners',workspace:'A'},mpRouterPosition:{session:'owned-session',index:7}};
    const f=await fixture(undefined,old);f.push('documents');assert.deepEqual(f.browser.history.state.mpRouterPosition,{session:'owned-session',index:8});
    const malformed=await fixture(undefined,{mpRouterPosition:{session:'',index:NaN}});assert.equal(malformed.browser.history.state.mpRouterPosition.index,0);
    assert.notEqual(malformed.browser.history.state.mpRouterPosition.session,'');
});
test('two pending traversals cannot let an older refusal undo the latest route request',async()=>{
    const f=await fixture();f.push('workboard');f.push('documents');const before=structuredClone(f.entries);
    f.browser.history.go(-1);const first=f.last().detail;f.browser.history.go(-1);const second=f.last().detail;
    assert.equal(f.router.cancelRouteChange(first),false);assert.equal(f.router.cancelRouteChange(second),true);
    assert.match(f.browser.location.href,/documents/);assert.deepEqual(f.entries,before);assert.deepEqual(f.traversals,[-1,-1,2]);
});
test('refused internal links keep the committed address and cannot load a different workspace',async()=>{
    const f=await fixture();f.push('workboard',{workspace:'A'});const before=structuredClone(f.entries);
    const a={href:'http://review.invalid/odoo/documents?workspace=B',getAttribute:()=>'/odoo/documents?workspace=B',target:''};let prevented=false;
    f.emit('click',{defaultPrevented:false,target:{closest:selector=>selector==='a'?a:null},preventDefault:()=>prevented=true});
    await new Promise(resolve=>setTimeout(resolve,0));await f.handler.call(f.client,{detail:f.last().detail});
    assert.equal(prevented,true);assert.equal(f.client.loads,0);assert.match(f.browser.location.href,/workboard.*workspace=A/);assert.deepEqual(f.entries,before);
});
