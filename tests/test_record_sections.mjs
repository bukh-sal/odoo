import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const path=new URL('../framework_addons/web/static/src/interface/record_sections.js',import.meta.url);
const source=(await readFile(path,'utf8')).replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,'');
class Component {}
let direction='ltr';
const callbacks=[];
const {RecordTabs}=new Function('Component','Icon','onWillUpdateProps','useEffect','useRef','useState','_t','document','getComputedStyle',source+';return {RecordTabs};')(
    Component,class{},fn=>callbacks.push(fn),()=>{},()=>({el:null}),x=>x,x=>x,{activeElement:null},()=>({direction}));
const items=()=>[{id:'overview',label:'Overview',panelId:'record-overview'},{id:'work',label:'Related work',panelId:'record-work'},{id:'unavailable',label:'Unavailable',panelId:'record-unavailable',disabled:true},{id:'contacts',label:'Contacts',panelId:'record-contacts'}];
function fixture(onSelect=async()=>true){
    const c=new RecordTabs(),focused=[];
    c.props={idPrefix:'record-1',items:items(),selectedId:'overview',onSelect};c.setup();
    const buttons=c.props.items.map(item=>({dataset:{recordTab:item.id},focus:()=>focused.push(item.id)}));
    c.root.el={querySelectorAll:()=>buttons};
    return {c,focused};
}
test('controlled tabs select only through the owner and await its leave decision',async()=>{
    let resolve,calls=0;const f=fixture(async id=>{calls++;assert.equal(id,'work');return new Promise(done=>resolve=done);});
    const pending=f.c.choose(f.c.props.items[1]);assert.equal(f.c.state.pending,true);assert.equal(f.c.activeId,'overview');
    assert.equal(await f.c.choose(f.c.props.items[3]),false);assert.equal(calls,1);
    resolve(false);assert.equal(await pending,false);assert.equal(f.c.activeId,'overview');assert.equal(f.c.state.pending,false);
});
test('successful selection remains controlled and never navigates or creates record state',async()=>{
    const f=fixture(async id=>{f.c.props.selectedId=id;return true;});
    assert.equal(await f.c.choose(f.c.props.items[1]),true);assert.equal(f.c.activeId,'work');assert.equal(f.c.focusId,'work');
    assert.deepEqual(f.focused,[]);
});
test('left/right/home/end move focus manually and skip disabled sections',()=>{
    direction='ltr';let selected=0,prevented=0;const f=fixture(()=>selected++);
    const key=(key,id)=>f.c.onKeydown({key,preventDefault:()=>prevented++},id);
    key('ArrowRight','overview');key('ArrowRight','work');key('ArrowRight','contacts');key('End','overview');key('Home','contacts');
    assert.deepEqual(f.focused,['work','contacts','overview','contacts','overview']);assert.equal(prevented,5);assert.equal(selected,0);
    key('ArrowDown','overview');assert.equal(prevented,5,'Vertical scrolling is not captured');
});
test('RTL arrows follow visual direction, with no translated identity or persistent state',()=>{
    direction='rtl';const f=fixture();f.c.onKeydown({key:'ArrowRight',preventDefault(){}},'overview');
    assert.equal(f.focused[0],'contacts');f.c.onKeydown({key:'ArrowLeft',preventDefault(){}},'contacts');assert.equal(f.focused[1],'overview');direction='ltr';
});
test('a removed or disabled selected section falls back to a present enabled section',async()=>{
    const f=fixture();f.c.props.selectedId='work';f.c.state.focusId='work';f.c.props.items=f.c.props.items.filter(item=>item.id!=='work');
    assert.equal(f.c.activeId,'overview');assert.equal(f.c.focusId,'overview');
    assert.equal(await f.c.choose({id:'work'}),false);assert.equal(await f.c.choose(f.c.props.items.find(i=>i.disabled)),false);
});
test('duplicate keys/panel destinations and broken identity/label shapes refuse',()=>{
    for(const broken of [
        x=>x.push({...x[0],panelId:'other'}),x=>x.push({...x[0],id:'other'}),
        x=>x[0].id='unsafe id',x=>x[0].panelId='',x=>x[0].label='',x=>x[0].disabled='yes',
    ]){const f=fixture();broken(f.c.props.items);assert.throws(()=>f.c.items,/unique keys/);}
    const f=fixture();f.c.props.idPrefix='';assert.throws(()=>f.c.items,/DOM identity/);
});
test('owner exceptions clear pending without claiming selection success',async()=>{
    const f=fixture(async()=>{throw new Error('Owner refused');});await assert.rejects(f.c.choose(f.c.props.items[1]),/Owner refused/);
    assert.equal(f.c.state.pending,false);assert.equal(f.c.activeId,'overview');
});
test('empty sections render no artificial destination and pending retirement cannot resurrect a tab',async()=>{
    const empty=fixture();empty.c.props.items=[];assert.equal(empty.c.activeId,undefined);assert.equal(empty.c.focusId,undefined);
    let done;const f=fixture(()=>new Promise(resolve=>done=resolve));const pending=f.c.choose(f.c.props.items[1]);f.c.props.items=f.c.props.items.filter(i=>i.id!=='work');done(true);await pending;
    assert.equal(f.c.activeId,'overview');assert.notEqual(f.c.state.focusId,'work');
});
