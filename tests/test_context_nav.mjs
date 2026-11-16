import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const source=(await readFile(new URL('../framework_addons/web/static/src/interface/context_nav.js',import.meta.url),'utf8'))
    .replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,'');
class Component {}
let serial=0,unmount;
const doc={activeElement:null};
const {ContextNav,validateContextGroups,contextHref}=new Function('Component','onWillUnmount','useRef','useState','_t','uniqueId','Icon','document',
    source+';return {ContextNav,validateContextGroups,contextHref};')(
    Component,fn=>{unmount=fn;},()=>({el:null}),v=>v,v=>v,()=>String(++serial),Component,doc);
const groups=()=>[{id:'directory',label:'Directory',items:[{id:'all',label:'All',href:'/odoo/action-1',count:0},
    {id:'folder',label:'Group',children:[{id:'child',label:'Child',href:'/odoo/action-2'}]}]}];
function fixture(extra={}){const c=new ContextNav();c.props={groups:groups(),...extra};c.setup();return c;}

test('presentation accepts truthful zero counts and internal destinations without changing input',()=>{
    const data=groups(),before=structuredClone(data);assert.equal(validateContextGroups(data),data);assert.deepEqual(data,before);
    for(const href of ['/odoo/action-3?workspace=scope','#page'])assert.equal(contextHref(href),true);
    for(const href of ['https://outside.invalid','javascript:alert(1)','//outside.invalid','/\\outside','/x\n'])assert.equal(contextHref(href),false);
});

test('invalid labels, keys, cycles, unsafe destinations and non-integer counters refuse',()=>{
    const variants=[x=>x[0].items.push({...x[0].items[0]}),x=>x[0].items[0].href='javascript:alert(1)',
        x=>x[0].items[0].label={},x=>x[0].items[0].id='unsafe id',x=>x[0].items[0].count=-1,
        x=>x[0].items[0].count=1.5,x=>x[0].items[0].count=Number.MAX_SAFE_INTEGER+1,
        x=>x[0].items[0].countLabel={},x=>x[0].items[0].disabled='yes',
        x=>x[0].items[1].children.push(x[0].items[1])];
    for(const mutate of variants){const data=groups();mutate(data);assert.throws(()=>validateContextGroups(data),/Context/);}
});

test('owner navigation decisions are awaited and modified links retain native new-tab behavior',async()=>{
    let prevented=0,calls=0;const c=fixture({onNavigate:async(item)=>{calls++;assert.equal(item.id,'all');return false;}});
    const event={button:0,preventDefault(){prevented++;}};
    assert.equal(await c.navigate(c.groups[0].items[0],event),false);assert.equal(prevented,1);assert.equal(calls,1);
    assert.equal(await c.navigate(c.groups[0].items[0],{...event,ctrlKey:true}),true);assert.equal(calls,1);assert.equal(prevented,1);
    const removed=c.props.groups[0].items.shift();assert.equal(await c.navigate(removed,event),false);assert.equal(calls,1);
});

test('disclosure cancellation and repeated clicks preserve state until the owner finishes',async()=>{
    let done,calls=0;const c=fixture({onToggle:()=>{calls++;return new Promise(resolve=>done=resolve);}}),item=c.groups[0].items[1];
    const pending=c.toggle(item);assert.equal(c.expanded(item),true);assert.equal(await c.toggle(item),false);assert.equal(calls,1);
    done(false);assert.equal(await pending,false);assert.equal(c.expanded(item),true);assert.equal(c.state.pending.folder,false);
    c.props.onToggle=async()=>true;assert.equal(await c.toggle(item),true);assert.equal(c.expanded(item),false);
});

test('removed or disposed navigation cannot be resurrected by a late disclosure result',async()=>{
    for(const dispose of [false,true]){
        let done;const c=fixture({onToggle:()=>new Promise(resolve=>done=resolve)}),item=c.groups[0].items[1];
        const pending=c.toggle(item);if(dispose)unmount();else c.props.groups=[];
        done(true);assert.equal(await pending,false);assert.equal(Object.hasOwn(c.state.expanded,'folder'),false);
    }
});

test('legal object-property-like keys do not appear busy through the prototype',async()=>{
    const c=fixture();const item=c.props.groups[0].items[1];item.id='constructor';
    assert.equal(await c.toggle(item),true);assert.equal(c.expanded(item),false);
});

test('navigation keys traverse visible controls without capturing modified keys or activation',()=>{
    const c=fixture(),focused=[];
    const nodes=['first','second','hidden','last'].map(name=>({name,getClientRects:()=>name==='hidden'?[]:[{}],focus(){focused.push(name);doc.activeElement=this;}}));
    c.root.el={querySelectorAll:()=>nodes};doc.activeElement=nodes[0];let prevented=0;
    const press=(key,extra={})=>c.onKeydown({key,preventDefault(){prevented++;},...extra});
    press('ArrowDown');press('End');press('ArrowDown');press('ArrowUp');press('Home');
    assert.deepEqual(focused,['second','last','first','last','first']);assert.equal(prevented,5);
    press('ArrowDown',{ctrlKey:true});press('ArrowDown',{defaultPrevented:true});press('Enter');assert.equal(prevented,5);
});
