import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
const read=p=>readFile(new URL('../framework_addons/web/static/src/'+p,import.meta.url),'utf8');
const hook=(await read('views/fields/input_field_hook.js')).replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,'');
const hooks=await read('core/utils/hooks.js');
const useBusSource=hooks.match(/^export function useBus\([^]*?^}/m)[0].replace('export ','');
const modelSource=await read('model/relational_model/relational_model.js');
const recordSource=await read('model/relational_model/record.js');
const formSource=await read('views/form/form_controller.js');
const method=(source,name)=>source.match(new RegExp('^    (?:async )?'+name+'\\([^]*?^    }','m'))[0];
const Model=new Function('return class {'+method(modelSource,'_askChanges')+'}')();
const Record=new Function('return class {'+method(recordSource,'isDirty')+'}')();
const Controller=new Function('return class {'+method(formSource,'beforeLeave')+'}')();

function fixture({parse=x=>x,updateError=null}={}) {
    const calls=[],effects=[],cleanups=[];
    class Bus extends EventTarget {trigger(name,detail){calls.push(name);this.dispatchEvent(new CustomEvent(name,{detail}));}}
    class Input extends EventTarget {
        value='Original';tagName='INPUT';attrs=new Map();
        hasAttribute(n){return this.attrs.has(n);}setAttribute(n,v){this.attrs.set(n,v);}getAttribute(n){return this.attrs.get(n);}removeAttribute(n){this.attrs.delete(n);}
    }
    const input=new Input(),model=new Model(),record=new Record();let invalid=false;
    model.bus=new Bus();model.mutex={getUnlockedDef:()=>Promise.resolve()};
    Object.assign(record,{model,data:{name:'Original'},fields:{name:{string:'Name'}},dirty:false,
        update:async values=>{calls.push('update');if(updateError)throw updateError;Object.assign(record.data,values);record.dirty=true;},
        setInvalidField:()=>{invalid=true;},resetFieldValidity:()=>{invalid=false;},isFieldInvalid:()=>invalid});
    Object.defineProperty(record,'isValid',{get:()=>!invalid});model.root=record;
    const component={props:{name:'name',record}};
    const deps={useComponent:()=>component,useRef:()=>({el:input}),useEffect:(fn,values)=>effects.push({fn,values}),getActiveHotkey:()=>''};
    const useBus=new Function(...Object.keys(deps),useBusSource+';return useBus;')(...Object.values(deps));
    const useInputField=new Function(...Object.keys(deps),'useBus',hook+';return useInputField;')(...Object.values(deps),useBus);
    useInputField({getValue:()=>record.data.name,parse});
    for(const {fn,values} of effects)cleanups.push(fn(...(values?.()||[])));
    const c=new Controller();c.model=model;c.props={};
    c.save=async opts=>{calls.push('save');if(!record.data.name||invalid){invalid=true;return false;}record.dirty=false;return true;};
    return {c,record,input,calls,type(value){input.value=value;input.dispatchEvent(new Event('input'));},cleanup(){for(const fn of cleanups)fn?.();}};
}

test('actual input hook/model/record flush pending required-empty input before native leave save',async()=>{
    const f=fixture();f.type('');assert.equal(f.record.dirty,false); // input has not blurred into model
    assert.equal(await f.c.beforeLeave(),false);assert.equal(f.record.data.name,'');assert.equal(f.record.isValid,false);
    assert.ok(f.calls.indexOf('NEED_LOCAL_CHANGES')<f.calls.indexOf('update'));
    assert.ok(f.calls.indexOf('update')<f.calls.indexOf('save'));assert.equal(f.calls.filter(x=>x==='save').length,1);f.cleanup();
});

test('actual parser-invalid pending input cannot be abandoned just because model dirty remains false',async()=>{
    const f=fixture({parse:()=>{throw new Error('invalid number');}});f.type('bad');
    assert.equal(await f.c.beforeLeave(),false);assert.equal(f.record.dirty,false);assert.equal(f.record.data.name,'Original');
    assert.equal(f.record.isValid,false);assert.ok(f.calls.includes('save'));assert.ok(!f.calls.includes('update'));f.cleanup();
});

test('normal pending valid input reaches the existing save; no changes avoids save',async()=>{
    const f=fixture();f.type('Changed');assert.equal(await f.c.beforeLeave(),true);assert.equal(f.record.data.name,'Changed');f.cleanup();
    const clean=fixture();assert.equal(await clean.c.beforeLeave(),undefined);assert.ok(!clean.calls.includes('save'));clean.cleanup();
});

test('explicit forceLeave preserves discard semantics without flushing/saving pending fields',async()=>{
    const f=fixture();f.type('Changed');f.calls.length=0;
    assert.equal(await f.c.beforeLeave({forceLeave:true}),undefined);assert.deepEqual(f.calls,[]);assert.equal(f.record.data.name,'Original');f.cleanup();
});

test('creation preventAutoSave flushes and refuses dirty/invalid input but never saves',async()=>{
    for(const config of [{},{parse:()=>{throw new Error('invalid');}}]) {
        const f=fixture(config);f.c.props.preventAutoSave=true;f.type('New');assert.equal(await f.c.beforeLeave(),false);
        assert.ok(!f.calls.includes('save'));f.cleanup();
    }
    const f=fixture();f.c.props.preventAutoSave=true;assert.equal(await f.c.beforeLeave(),true);f.cleanup();
});

test('pending update failure rejects leaving and does not claim a save or successful navigation',async()=>{
    const f=fixture({updateError:new Error('update failed')});f.type('Changed');
    await assert.rejects(f.c.beforeLeave(),/update failed/);assert.ok(!f.calls.includes('save'));f.cleanup();
});
