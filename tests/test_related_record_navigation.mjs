import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const root=new URL('../framework_addons/web/static/src/',import.meta.url);
const read=p=>readFile(new URL(p,root),'utf8');
const objectSource=await read('core/utils/objects.js');
const objects=await import('data:text/javascript;base64,'+Buffer.from(objectSource).toString('base64'));
const navigation=(await read('webclient/actions/record_navigation.js')).replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,'');
const findRecordAncestor=new Function('deepEqual',navigation+';return findRecordAncestor;')(objects.deepEqual);
const userContext={uid:5,lang:'en_US',allowed_company_ids:[1]};
const action=(extra={})=>({type:'ir.actions.act_window',target:'current',res_model:'sample.record',res_id:2,views:[[false,'form']],context:{...userContext},...extra});
const parent=(extra={})=>({jsId:'parent',view:{type:'form'},views:[{type:'form'}],action:action({res_id:undefined,views:[[false,'list'],[false,'form']]}),props:{type:'form',resModel:'sample.record',resId:2,context:{}},...extra});
const current=()=>parent({jsId:'current',props:{type:'form',resModel:'sample.record',resId:16,context:{}}});
const options={preferExistingRecord:true};

test('exact related form prefers its real ancestor, not a matching name or the current controller',()=>{
    const p=parent(),stack=[p,current()];assert.equal(findRecordAncestor(stack,action(),options,userContext),p);
    assert.equal(findRecordAncestor([p],action(),options,userContext),undefined);
    assert.equal(findRecordAncestor([parent({props:{...p.props,resId:3},displayName:'Same title'}),current()],action(),options,userContext),undefined);
    const nearest=parent({jsId:'nearest'});assert.equal(findRecordAncestor([p,nearest,current()],action(),options,userContext),nearest);
});

test('effective exported record and exact form selection match the native restore producer',()=>{
    const p=parent({exportedState:{resId:7}}),stack=[p,current()];
    assert.equal(findRecordAncestor(stack,action({res_id:2}),options,userContext),undefined);
    assert.equal(findRecordAncestor(stack,action({res_id:7}),options,userContext),p);
    for(const resId of [false,undefined,null,0]) {
        p.exportedState={resId};assert.equal(findRecordAncestor(stack,action(),options,userContext),undefined);
    }
    p.exportedState={resId:2};p.props.viewId=20;
    assert.equal(findRecordAncestor(stack,action(),options,userContext),undefined);
    assert.equal(findRecordAncestor(stack,action({views:[[20,'form']]}),options,userContext),p);
    delete p.props.viewId;p.action.views=[[20,'form']];assert.equal(findRecordAncestor(stack,action({views:[[20,'form']]}),options,userContext),p);
});

test('full context including nested values is retained with no private-key exceptions',()=>{
    const p=parent(),stack=[p,current()];
    p.props.context={mode:'detail',nested:{ids:[1,2]}};
    assert.equal(findRecordAncestor(stack,action({context:{...userContext,mode:'detail',nested:{ids:[1,2]}}}),options,userContext),p);
    for(const context of [{...userContext},{...userContext,mode:'detail',nested:{ids:[2,1]}},{...userContext,mode:'detail',nested:{ids:[1,2]},workspace:'other'},{...userContext,uid:7,mode:'detail',nested:{ids:[1,2]}}]) {
        assert.equal(findRecordAncestor(stack,action({context}),options,userContext),undefined);
    }
    p.props.context={default_kind:'person'};assert.equal(findRecordAncestor(stack,action(),options,userContext),undefined);
});

test('virtual/non-form/model mismatch and non-record actions cannot be reused',()=>{
    for(const change of [{virtual:true},{props:{type:'list',resModel:'sample.record',resId:2}},{props:{type:'form',resModel:'other.record',resId:2}},{action:action({target:'new'})},{action:{type:'ir.actions.client'}}]) {
        assert.equal(findRecordAncestor([parent(change),current()],action(),options,userContext),undefined);
    }
    for(const change of [{res_id:false},{res_id:0},{res_id:'2'},{res_id:NaN},{res_model:''},{res_model:undefined},{views:[[false,'list']]},{views:[[false,'form'],[false,'search']]},{views:[null]},{views:[[0,'form']]},{target:'new'},{target:'main'},{type:'ir.actions.client'}]) {
        assert.equal(findRecordAncestor([parent(),current()],action(change),options,userContext),undefined);
    }
});

test('unknown action semantics and explicit stack/leave/props options fall back unchanged',()=>{
    for(const change of [{flags:{}},{domain:[['active','=',true]]},{help:'Custom'},{id:83},{cache:false},{_noBreadcrumbs:false},{custom:'owned'}]) {
        assert.equal(findRecordAncestor([parent(),current()],action(change),options,userContext),undefined);
    }
    for(const opt of [{},{preferExistingRecord:false},{...options,newWindow:true},{...options,index:0},{...options,newStack:[]},{...options,stackPosition:'replaceCurrentAction'},{...options,clearBreadcrumbs:false},{...options,props:{}},{...options,forceLeave:true},{...options,additionalContext:{}}]) {
        assert.equal(findRecordAncestor([parent(),current()],action(),opt,userContext),undefined);
    }
});

const serviceSource=await read('webclient/actions/action_service.js');
const extract=name=>{
    const result=serviceSource.match(new RegExp('^    (?:async )?function '+name+'\\([^]*?^    }','m'));
    assert.ok(result,name);return result[0];
};
const clearSource=serviceSource.match(/^export async function clearUncommittedChanges\([^]*?^}/m)[0].replace('export ','');

// Execute the real doAction/load/preprocess/restore/leave functions together.
// RPC, UI mounting and scheduler are explicit external boundaries; this is not
// an installed authorization or browser-history qualification.
function fixture({allow=true,dialog=null}={}) {
    const calls=[],p=parent({exportedState:{resId:2,remember:'list position'}}),stack=[p,current()];
    const env={bus:{trigger(name,callbacks){assert.equal(name,'CLEAR-UNCOMMITTED-CHANGES');calls.push(['leave']);callbacks.push(async()=>{if(allow instanceof Error)throw allow;return allow;});}}};
    const params={env,user:{context:userContext},keepLast:{add:p=>p},dialog,controllerStack:stack,id:0,
        actionRegistry:{contains:()=>false},rpc:async()=>{throw new Error('not loaded');},makeContext:contexts=>Object.assign({},...contexts),markup:x=>x,isHtmlEmpty:()=>false,evaluateExpr:()=>{throw new Error('not expected');},
        findRecordAncestor,pick:objects.pick,
        _executeActWindowAction:async(a,o)=>{calls.push(['new',a,o]);return 99;},
        _getViewInfo:(...args)=>{calls.push(['reconstruct',args[3]]);return {props:args[3]};},
        _updateUI:async(c,{index})=>{calls.push(['restore',c.jsId,index]);stack.splice(index+1);return 42;},
    };
    const code=[clearSource,...['_loadAction','_preprocessAction','doAction','restore'].map(extract)].join('\n');
    const create=new Function(...Object.keys(params),code+';return {doAction,restore};');
    return {...create(...Object.values(params)),calls,stack,p};
}

test('actual doAction reuses native restore, reconstructs exported state and checks leaving exactly once',async()=>{
    const f=fixture();assert.equal(await f.doAction(action(),{...options}),42);
    assert.deepEqual(f.calls.map(c=>c[0]),['leave','reconstruct','restore']);assert.equal(f.calls[1][1].resId,2);
    assert.deepEqual(f.stack.map(c=>c.jsId),['parent']);
});

test('actual native leave refusal/error keeps stack and never opens or reconstructs destination',async()=>{
    for(const allow of [false,new Error('leave failed')]) {
        const f=fixture({allow});
        if(allow===false)assert.equal(await f.doAction(action(),{...options}),undefined);
        else await assert.rejects(f.doAction(action(),{...options}),/leave failed/);
        assert.deepEqual(f.calls,[['leave']]);assert.equal(f.stack.length,2);
    }
});

test('ordinary/new-window/dialog/custom-context paths preserve native new-action behavior',async()=>{
    for(const [config,a,opt,expected] of [
        [{},action(),{},['leave','new']],
        [{},action(),{...options,newWindow:true},['new']],
        [{dialog:{}},action(),{...options},['leave','new']],
        [{},action({target:'new'}),{...options},['new']],
        [{},action({context:{changed:true}}),{...options},['leave','new']],
    ]) {
        const f=fixture(config);assert.equal(await f.doAction(a,opt),99);assert.deepEqual(f.calls.map(c=>c[0]),expected);assert.equal(f.stack.length,2);
    }
    const f=fixture();await assert.rejects(f.doAction(83,{...options}),/not loaded/);assert.deepEqual(f.calls,[]);
});

const manySource=await read('views/fields/many2one/many2one.js');
const openMethod=manySource.match(/^    async openRecordInAction\([^]*?^    }/m)[0];
const Many=new Function('return class {'+openMethod+'}')();
test('actual many2one producer requests a fresh action first and only reuses same-page non-dialog links',async()=>{
    for(const [newWindow,inDialog,reuse] of [[false,false,true],[true,false,false],[false,true,false]]) {
        const calls=[],m=new Many(),a=action();m.env={inDialog};m.props={relation:'sample.record',value:{id:2},openActionContext:()=>({owned:'exact'})};
        m.orm={call:async(...args)=>{calls.push(['server',...args]);return a;}};m.action={doAction:async(...args)=>calls.push(['action',...args])};
        await m.openRecordInAction(newWindow);
        assert.deepEqual(calls[0],['server','sample.record','get_formview_action',[[2]],{context:{owned:'exact'}}]);
        assert.equal(calls[1][1],a);assert.deepEqual(calls[1][2],{newWindow,preferExistingRecord:reuse});
    }
    const m=new Many();m.props={value:{id:2},openActionContext:()=>({})};m.orm={call:async()=>{throw new Error('denied');}};
    m.action={doAction:()=>assert.fail('must not navigate after refusal')};await assert.rejects(m.openRecordInAction(false),/denied/);
});
