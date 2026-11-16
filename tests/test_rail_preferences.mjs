import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const root=new URL('../framework_addons/web/static/src/',import.meta.url);
const source=async path=>(await readFile(new URL(path,root),'utf8')).replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,'');
const preference=await source('interface/rail_preferences.js');
const editor=await source('interface/rail_customization.js');
const A='84fa4ab9-24d7-4bc2-bf5b-4dde890494b5',B='39b81592-aac8-4918-8e15-349679c1a2db';
const apps=[{id:1,xmlid:'a.root',name:'Alpha'},{id:2,pluginID:'example.b',name:'Beta'},{id:3,name:'Gamma'}];
function fixture() {
    const values=new Map(),events=[],effects=[],listeners=[],user={userId:5},session={db:'local database'};
    const browser={localStorage:{getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)},location:{search:'?workspace='+A}};
    const bus={trigger:(...args)=>events.push(args)};
    const api=new Function('useComponent','useEffect','useExternalListener','useState','browser','user','session','window',
        preference+';return {railPreferenceKey,railAppId,validRailPins,readRailPins,writeRailPins,pinnedRailApps,useRailPreferences};')(
        ()=>({env:{bus}}),(fn,deps)=>effects.push({fn,deps}),(target,name,fn)=>listeners.push({target,name,fn}),x=>x,browser,user,session,{});
    return {api,values,events,effects,listeners,user,session,browser,bus};
}
const api=fixture().api;

test('rail identity is stable and its key isolates account, database and workspace',()=>{
    assert.deepEqual(apps.map(api.railAppId),['xmlid:a.root','plugin:example.b','menu:3']);
    const keys=[api.railPreferenceKey(5,'db',A),api.railPreferenceKey(6,'db',A),api.railPreferenceKey(5,'other',A),api.railPreferenceKey(5,'db',B)];
    assert.equal(new Set(keys).size,4);assert.match(api.railPreferenceKey(5,'a:b c',A),/a%3Ab%20c/);
    for(const args of [[0,'db',A],[5,'',A],[5,'db\n',A],[5,'db','bad'],[NaN,'db',A]])assert.equal(api.railPreferenceKey(...args),null);
    assert.equal(api.railAppId({id:'bad/id'}),null);
});

test('default and explicit empty pins differ, reloading preserves order without restoring unavailable apps',()=>{
    const f=fixture(),key=api.railPreferenceKey(5,'db',A);
    assert.equal(api.readRailPins(f.browser.localStorage,key),null);
    assert.equal(api.pinnedRailApps(apps,null),apps);
    for(const pins of [[],['menu:3','xmlid:a.root'],null]) {
        assert.equal(api.writeRailPins(f.browser.localStorage,key,pins),true);
        assert.deepEqual(api.readRailPins(f.browser.localStorage,key),pins);
    }
    assert.deepEqual(api.pinnedRailApps(apps,[]),[]);
    assert.deepEqual(api.pinnedRailApps(apps.slice(1),['xmlid:a.root','menu:3']),[apps[2]]);
});

test('corruption, duplicates, oversized data and unavailable storage fall back without mutation',()=>{
    const f=fixture(),key='key';
    for(const raw of ['{bad','{}','["same","same"]','["bad/id"]','"'+('x'.repeat(65537))+'"']) {
        f.values.set(key,raw);assert.equal(api.readRailPins(f.browser.localStorage,key),null);
    }
    const before=new Map(f.values);
    for(const bad of [{},['bad/id'],['a','a'],Array.from({length:200},(_,i)=>'a'+i+'x'.repeat(500))])assert.equal(api.writeRailPins(f.browser.localStorage,key,bad),false);
    assert.deepEqual(f.values,before);assert.equal(api.writeRailPins(null,key,[]),false);assert.equal(api.readRailPins(null,key),null);
    assert.equal(api.writeRailPins(f.browser.localStorage,null,[]),false);
});

test('actual hook saves locally then notifies, follows current access and rejects failed storage',()=>{
    const f=fixture();let available=apps;const hook=f.api.useRailPreferences(()=>available);
    const pins=['menu:3','xmlid:a.root'];assert.equal(hook.save(pins),true);pins.reverse();
    assert.deepEqual(hook.apps,[apps[2],apps[0]]);assert.equal(f.events.length,1);
    const key=f.events[0][1].key;assert.deepEqual(JSON.parse(f.values.get(key)),['menu:3','xmlid:a.root']);
    available=apps.slice(1);assert.deepEqual(hook.apps,[apps[2]]);
    f.browser.localStorage.setItem=()=>{throw Error('Blocked');};assert.equal(hook.save([]),false);
    assert.deepEqual(hook.pins,['menu:3','xmlid:a.root']);assert.equal(f.events.length,1);
    Object.defineProperty(f.browser,'localStorage',{get(){throw Error('Denied');}});
    assert.equal(hook.save(null),false);assert.deepEqual(hook.pins,['menu:3','xmlid:a.root']);
});

test('actual hook reloads other-tab/local changes and never carries pins into a different workspace',()=>{
    const f=fixture(),hook=f.api.useRailPreferences(()=>apps),key=f.api.railPreferenceKey(5,f.session.db,A);
    f.values.set(key,'[]');f.listeners.find(x=>x.name==='storage').fn({key});assert.deepEqual(hook.apps,[]);
    f.values.set(key,'["menu:3"]');f.listeners.find(x=>x.target===f.bus).fn({detail:{key}});assert.deepEqual(hook.apps,[apps[2]]);
    f.browser.location.search='?workspace='+B;assert.equal(hook.pins,null);assert.equal(hook.apps,apps);
    assert.equal(hook.save([]),true);assert.deepEqual(hook.apps,[]);
    f.browser.location.search='?workspace='+A;assert.deepEqual(hook.apps,[apps[2]]);
});

function edit(pins=null,onSave=async()=>true) {
    let unmount,closed=0;class Component {constructor(props){this.props=props;}}
    const {RailCustomization}=new Function('Component','onWillUnmount','useState','_t','Dialog','Icon','railAppId',editor+';return {RailCustomization};')(
        Component,fn=>unmount=fn,x=>x,(s,v)=>s.replace('%s',v),class{},class{},api.railAppId);
    const instance=new RailCustomization({apps,pins,onSave,close:()=>closed++});instance.setup();
    return {instance,unmount:()=>unmount(),closed:()=>closed};
}
test('editor clones pins, supports accessible ordering and reset without saving until requested',async()=>{
    const pins=['xmlid:a.root','menu:3'],saved=[],f=edit(pins,async x=>{saved.push(x);return true;}),c=f.instance;
    c.move(apps[2],-1);assert.deepEqual(c.state.ids,['menu:3','xmlid:a.root']);assert.deepEqual(pins,['xmlid:a.root','menu:3']);
    assert.equal(c.canMove(apps[2],-1),false);c.toggle(apps[0]);assert.deepEqual(c.state.ids,['menu:3']);
    assert.deepEqual(saved,[]);c.reset();assert.equal(await c.save(),true);assert.deepEqual(saved,[null]);assert.equal(f.closed(),1);
    const empty=edit([]).instance;assert.deepEqual(empty.state.ids,[]);assert.equal(empty.state.defaults,false);
});
test('editor failed save retains choices, serializes pending saves and does not close after disposal',async()=>{
    let finish,calls=0;const f=edit([],()=>{calls++;return new Promise(r=>finish=r);}),c=f.instance;
    c.toggle(apps[1]);const pending=c.save();c.toggle(apps[0]);await c.save();assert.equal(calls,1);
    finish(false);assert.equal(await pending,false);assert.deepEqual(c.state.ids,['plugin:example.b']);assert.match(c.state.error,/still here/);assert.equal(f.closed(),0);
    const second=c.save();f.unmount();finish(true);assert.equal(await second,false);assert.equal(f.closed(),0);
});
