import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const source=(await readFile(new URL('../framework_addons/mp_identity/static/src/native_webclient.js',import.meta.url),'utf8')).replace(/^import .*;\r?\n/gm,'');
function fixture({workspace='workspace-A',token='pinned-release',stock=true}={}) {
    const calls=[],locked=[],categories=new Map();
    const rpc={_rpc:function(...args){calls.push({receiver:this,args});return 'native-result';}};
    const registry={category(name){if(!categories.has(name))categories.set(name,new Map());return{add:(key,value)=>categories.get(name).set(key,value)};}};
    const session={mp_client_release_token:token,mp_stock_profile:stock};
    const location={search:workspace?'?workspace='+workspace:''};
    new Function('browser','router','_t','rpc','rpcBus','registry','useBus','patch','FormController','ListController','session','odoo','window',source)(
        {},{addLockedKey:key=>locked.push(key)},text=>text,rpc,{addEventListener(){}},registry,()=>{},()=>{},class{},class{},session,{}, {location});
    return{rpc,calls,locked,session,location};
}

test('actual native transport pins the readonly breadcrumb endpoint as well as dataset calls',()=>{
    const f=fixture();assert.deepEqual(f.locked,['workspace']);
    for(const path of ['/web/action/load_breadcrumbs','/web/dataset/call_kw','/web/dataset/call_kw/partners.partner/read']) {
        const params={actions:[{action:84,resId:1}]},settings={cache:true,headers:{'X-Trace':'kept'}};
        assert.equal(f.rpc._rpc(path,params,settings),'native-result');
        const call=f.calls.at(-1);assert.equal(call.receiver,f.rpc);assert.equal(call.args[0],path);assert.equal(call.args[1],params);
        assert.deepEqual(call.args[2],{cache:false,headers:{'X-Trace':'kept','X-MP-Client-Release':'pinned-release','X-MP-Workspace':'workspace-A'}});
        assert.deepEqual(settings,{cache:true,headers:{'X-Trace':'kept'}},'Do not mutate caller settings');
    }
});
test('page pins override malicious caller headers and cannot follow later location/session changes',()=>{
    const f=fixture();f.location.search='?workspace=workspace-B';f.session.mp_client_release_token='new-release';
    f.rpc._rpc('/web/action/load_breadcrumbs',{actions:[]},{headers:{'X-MP-Workspace':'workspace-C','X-MP-Client-Release':'forged'}});
    assert.deepEqual(f.calls[0].args[2].headers,{'X-MP-Workspace':'workspace-A','X-MP-Client-Release':'pinned-release'});
});
test('unrelated, lookalike and foreign action URLs remain unmodified',()=>{
    const f=fixture();
    for(const path of ['/web/action/load','/web/action/run','/web/action/load_breadcrumbs/other','/web/action/load_breadcrumbs?scope=other','https://foreign.invalid/web/action/load_breadcrumbs','/api/v1/context']) {
        const params={},settings={cache:true,headers:{'X-Trace':'kept'}};f.rpc._rpc(path,params,settings);
        assert.equal(f.calls.at(-1).args[2],settings);
    }
});
test('missing page workspace is never invented and missing release bootstrap installs no transport wrapper',()=>{
    const f=fixture({workspace:null});f.rpc._rpc('/web/action/load_breadcrumbs',{},{});
    assert.deepEqual(f.calls[0].args[2].headers,{'X-MP-Client-Release':'pinned-release'});
    const g=fixture({token:null});const settings={};g.rpc._rpc('/web/action/load_breadcrumbs',{},settings);
    assert.equal(g.calls[0].args[2],settings);assert.deepEqual(g.locked,[]);
});
