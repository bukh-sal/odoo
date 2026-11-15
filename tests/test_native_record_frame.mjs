import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const root=new URL('../',import.meta.url);
const read=path=>readFile(new URL(path,root),'utf8');
const clean=source=>source.replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,'');
const translate=(text,...args)=>text.replace(/%s/g,()=>args.shift());
class Component {constructor(props){this.props=props;}}
const pagination=clean(await read('framework_addons/web/static/src/interface/table_pagination.js'));
const {TablePagination}=new Function('Component','useRef','useState','_t',pagination+';return {TablePagination};')(Component,()=>({el:null}),x=>x,translate);
const navigation=clean(await read('framework_addons/web/static/src/interface/record_navigation.js'));
const {RecordNavigation}=new Function('TablePagination','_t',navigation+';return {RecordNavigation};')(TablePagination,translate);
const formSource=await read('framework_addons/web/static/src/views/form/form_controller.js');
const producer=formSource.match(/usePager\(\(\) => \{([\s\S]*?)\n        }\);/)[1];
const getRecordProps=new Function(producer);
const updateMethod=formSource.match(/    async onPagerUpdate\(\{ offset, resIds }\) \{[\s\S]*?\n    }/)[0];
const FormPager=new Function('FetchRecordError','return class {'+updateMethod+'}')(class extends Error{});
const displaySetup=formSource.slice(formSource.indexOf('        this.display = { ...this.props.display };'),formSource.indexOf('        this.formInDialog = 0;'));
const setupDisplay=new Function(displaySetup);
test('actual form presentation selection preserves caller data and disabled/dialog control panels',()=>{
    for(const controlPanel of [false,true,{table:true,searchBar:false}])for(const inDialog of [false,true]) {
        const props={display:{controlPanel,searchPanel:false}},before=structuredClone(props);
        const controller={props,env:{inDialog}};setupDisplay.call(controller);
        if(!controlPanel||inDialog)assert.equal(controller.display.controlPanel,false);
        else {assert.equal(controller.display.controlPanel.record,true);assert.equal(controller.display.controlPanel.table,false);}
        assert.deepEqual(props,before);assert.equal(controller.display.searchPanel,false);
    }
});

function recordFixture({dirty=false,save=async()=>false}={}) {
    const calls=[],controller=new FormPager();
    controller.model={root:{isNew:false,resId:20,resIds:[10,20,30],isDirty:async()=>dirty,
        save:async options=>{calls.push(['save',options.nextId]);return save(options);}},
        load:async args=>calls.push(['load',args]),config:{resIds:[10,20,30]}};
    controller.onSaveError=()=>{};
    const page=new RecordNavigation(getRecordProps.call(controller));page.setup();
    return {page,calls,controller};
}
test('actual native producer traverses its loaded IDs, keeping count and callback scope',async()=>{
    const {page,calls,controller}=recordFixture();
    assert.equal(page.range,'Record 2 of 3 loaded');assert.equal(page.label,'Record navigation');
    await page.go(3);assert.deepEqual(calls,[['load',{resId:30}]]);
    assert.equal(page.current,2,'model still owns the resulting position');
    controller.model.root.isNew=true;assert.equal(getRecordProps.call(controller),undefined);
});
test('actual native dirty-record refusal does not load another record or advance the displayed position',async()=>{
    const {page,calls}=recordFixture({dirty:true});await page.go(3);
    assert.deepEqual(calls,[['save',30]]);assert.equal(page.current,2);assert.equal(page.state.busy,false);
});
test('record traversal is bounded and cannot accept table-sized ranges',async()=>{
    const {page,calls}=recordFixture();page.props.offset=0;
    assert.equal(page.canPrevious,false);await page.go(0);assert.equal(calls.length,0);
    page.props.offset=2;assert.equal(page.canNext,false);await page.go(4);assert.equal(calls.length,0);
    page.props.limit=80;assert.equal(page.valid,false);await page.go(1);assert.equal(calls.length,0);
});
test('navigation error retains current loaded ID position and reports recoverable failure',async()=>{
    const {page}=recordFixture({dirty:true,save:async()=>{throw Error('Revision changed');}});
    await page.go(3);assert.equal(page.current,2);assert.equal(page.state.error,'Revision changed');
});

const statusSource=clean(await read('framework_addons/web/static/src/views/form/form_status_indicator/form_status_indicator.js'));
function statusFixture(callbacks={}) {
    const events=[];
    const body={},button={},outside={};const document={body,activeElement:body};let focused=0;
    const statusLabel={focus:()=>{focused++;document.activeElement=statusLabel;}};
    const refs={save:{disabled:false},statusRoot:{contains:e=>e===button||e===statusLabel},statusLabel};
    const {FormStatusIndicator}=new Function('Component','useState','useBus','_t','useRef','useEffect','document',statusSource+';return {FormStatusIndicator};')(
        Component,x=>x,(_bus,name,fn)=>events.push({name,fn}),translate,name=>({el:refs[name]}),()=>{},document);
    const model={root:{isNew:false,isValid:true,dirty:false},bus:{}};
    const status=new FormStatusIndicator({model,save:async()=>true,discard:async()=>{},...callbacks});status.setup();
    return {status,model,events,document,button,outside,focused:()=>focused};
}
test('status follows actual model/local field validity and never calls an invalid clean field saved',()=>{
    const {status,model,events}=statusFixture();assert.equal(status.status,'Saved');
    events[0].fn({detail:true});assert.equal(status.status,'Unsaved changes');
    events[0].fn({detail:false});model.root.isValid=false;
    assert.equal(status.indicatorMode,'invalid');assert.equal(status.status,'Check fields');
    model.root.isValid=true;model.root.isNew=true;assert.equal(status.status,'New record');
});
test('pending Save is not duplicated or discarded, and a refused callback keeps the model dirty',async()=>{
    let finish,calls=0,discards=0;
    const {status,model}=statusFixture({save:()=>{calls++;return new Promise(r=>finish=r);},discard:async()=>discards++});
    model.root.dirty=true;const first=status.save();assert.equal(status.status,'Saving changes…');
    await status.save();await status.discard();assert.equal(calls,1);assert.equal(discards,0);
    finish(false);assert.equal(await first,false);assert.equal(status.status,'Unsaved changes');assert.equal(model.root.dirty,true);
});
test('failed Save propagates normally and clears only its pending marker; Discard remains the caller operation',async()=>{
    let discarded=0;const error=Error('Conflict');
    const {status,model}=statusFixture({save:async()=>{throw error;},discard:async()=>{discarded++;model.root.dirty=false;}});
    model.root.dirty=true;await assert.rejects(status.save(),e=>e===error);
    assert.equal(status.state.pending,null);assert.equal(status.status,'Unsaved changes');
    await status.discard();assert.equal(discarded,1);assert.equal(status.status,'Saved');
});
test('explicit status commands retain a meaningful focus target without stealing an opened dialog focus',async()=>{
    const f=statusFixture();f.document.activeElement=f.button;await f.status.save();assert.equal(f.focused(),1);
    const g=statusFixture({save:async()=>{g.document.activeElement=g.outside;}});
    g.document.activeElement=g.button;await g.status.save();assert.equal(g.focused(),0);
});

const inputSource=clean(await read('framework_addons/web/static/src/views/fields/input_field_hook.js'));
function inputFixture({labels=[],name,refName='input',fieldName,explicitLabel,explicitReference,explicitTitle,missing=false}={}) {
    const effects=[],attrs=new Map(),updates=[];let value='Retained text';
    if(explicitLabel)attrs.set('aria-label',explicitLabel);if(explicitReference)attrs.set('aria-labelledby',explicitReference);
    if(explicitTitle)attrs.set('title',explicitTitle);
    const input={labels,get value(){return value;},set value(v){value=v;},hasAttribute:k=>attrs.has(k),getAttribute:k=>attrs.get(k)??null,
        setAttribute:(k,v)=>attrs.set(k,v),removeAttribute:k=>attrs.delete(k),addEventListener:()=>{},removeEventListener:()=>{}};
    const component={props:{name:name||'notes',record:{fields:{notes:{string:'Notes'},other:{string:'Other information'}},data:{notes:value},model:{bus:{}},isFieldInvalid:()=>false,update:args=>updates.push(args)}}};
    const ref={el:missing?null:input};
    const {useInputField}=new Function('getActiveHotkey','useBus','useComponent','useEffect','useRef',inputSource+';return {useInputField};')(
        ()=>'',()=>{},()=>component,(fn,deps)=>effects.push({fn,deps}),actual=>{assert.equal(actual,refName);return ref;});
    useInputField({refName,fieldName,getValue:()=>value});
    return {effects,attrs,input,updates};
}
test('actual input hook names an otherwise label-free native field without changing data',()=>{
    const f=inputFixture({refName:'textarea'});const cleanup=f.effects[0].fn();
    assert.equal(f.attrs.get('title'),'Notes');assert.equal(f.attrs.has('aria-label'),false);assert.equal(f.input.value,'Retained text');assert.deepEqual(f.updates,[]);
    cleanup();assert.equal(f.attrs.has('title'),false);
});
test('existing labels and explicit accessible names remain authoritative',()=>{
    for(const options of [{explicitTitle:'App-specific help'},{explicitLabel:'App-specific notes'},{explicitReference:'record-notes-heading'}]) {
        const f=inputFixture(options),before=new Map(f.attrs);assert.equal(f.effects[0].fn(),undefined);assert.deepEqual(f.attrs,before);
    }
});
test('label reassociation and explicit later names are preserved on cleanup',()=>{
    const label={};const f=inputFixture({labels:[label]});let cleanup=f.effects[0].fn();
    assert.equal(f.attrs.get('title'),'Notes');assert.equal(f.attrs.has('aria-label'),false);
    assert.equal(f.input.labels[0],label);cleanup();f.input.labels=[];
    cleanup=f.effects[0].fn();f.attrs.set('title','New explicit help');cleanup();
    assert.equal(f.attrs.get('title'),'New explicit help');
});
test('missing/readonly controls are inert and the explicit fieldName metadata is used',()=>{
    const missing=inputFixture({missing:true});assert.equal(missing.effects[0].fn(),undefined);
    const override=inputFixture({fieldName:'other'});override.effects[0].fn();assert.equal(override.attrs.get('title'),'Other information');
});
