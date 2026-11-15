import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
const root=new URL('../',import.meta.url);
const source=await readFile(new URL('framework_addons/web/static/src/views/form/form_controller.js',root),'utf8');
const names=['readFirst','modelParams','editRecord','finishRecordEdit','focusRequestedRecordMode','save','saveButtonClicked','discard','create','onPagerUpdate'];
const methods=names.map(name=>{
    const match=source.match(new RegExp('^    (?:async |get )?'+name+'\\([^]*?^    }','m'));
    assert.ok(match,'actual method '+name);return match[0];
}).join('\n');
class FetchRecordError extends Error {constructor(ids){super('Missing target');this.resIds=ids;}}
function fixture({resId=20,editing=false,dirty=false,saveResult=true}={}) {
    const calls=[],body={},doc={body,activeElement:body},touch={value:false};
    const Controller=new Function('executeButtonCallback','status','hasTouch','document','FetchRecordError','return class {'+methods+'}')(
        async(element,fn)=>fn(),c=>c.destroyed?'destroyed':'mounted',()=>touch.value,doc,FetchRecordError);
    const c=new Controller();c.props={resModel:'owned.record',resId,context:{workspace:'kept'},fields:{revision:{type:'integer'}},state:{modelState:{draft:'keep'}}};
    c.display={controlPanel:{record:true}};c.env={inDialog:false,config:{historyBack:()=>calls.push(['back'])},dialogData:{close:async()=>calls.push(['close'])}};
    c.canEdit=true;c.archInfo={disableAutofocus:false};c.ui={activeElement:{}};
    for(const name of ['onWillLoadRoot','onWillSaveRecord','onRecordSaved','onWillDisplayOnchangeWarning','onSaveError'])c[name]=()=>{};
    const makeRecord=id=>({resId:id,isNew:!id,isInEdition:editing,dirty,data:{name:'original',revision:2},
        isDirty:async()=>c.model.root.dirty,
        switchMode:async mode=>{calls.push(['mode',mode]);c.model.root.isInEdition=mode==='edit';},
        discard:async()=>{calls.push(['discard']);c.model.root.dirty=false;},
        save:async options=>{
            calls.push(['save',options]);if(saveResult instanceof Error)throw saveResult;
            if(saveResult && options?.nextId)c.model.root=makeRecord(options.nextId);
            return saveResult;
        }});
    c.model={root:makeRecord(resId),config:{resIds:[10,20,30]},load:async args=>{
        calls.push(['load',args]);if('resId' in args)c.model.root=makeRecord(args.resId);
        if(args.mode)c.model.root.isInEdition=args.mode==='edit';
    }};
    const field={focus:options=>{calls.push(['focus','field',options]);doc.activeElement=field;}};
    const command={focus:options=>{calls.push(['focus','command',options]);doc.activeElement=command;}};
    const inside=new Set([field,command]);
    c.rootRef={el:{contains:el=>inside.has(el),querySelector:selector=>{calls.push(['selector',selector]);return field;}}};
    c.editButton={el:command};c.requestedRecordFocus=null;
    return {c,calls,doc,touch,field,command};
}

test('actual initial-mode producer reads existing records; new and explicit readonly retain proper mode/state',()=>{
    for(const resId of [false,20]) {
        const {c}=fixture({resId});const state=c.props.state.modelState,context=c.props.context,fields=c.props.fields;
        const before=structuredClone(c.props);const params=c.modelParams;
        assert.equal(params.config.mode,resId?'readonly':'edit');assert.equal(params.state,state);
        assert.equal(params.config.context,context);assert.equal(params.config.fields,fields);assert.deepEqual(c.props,before);
        c.props.readonly=true;assert.equal(c.modelParams.config.mode,'readonly');
    }
});

test('dialogs, disabled controls and custom persistence preserve their original editable producer',()=>{
    for(const change of [c=>c.env.inDialog=true,c=>c.display.controlPanel=false,c=>c.display.controlPanel={table:true},c=>c.props.saveRecord=()=>{},c=>c.props.discardRecord=()=>{}]) {
        const {c}=fixture();change(c);assert.equal(c.readFirst,false);assert.equal(c.modelParams.config.mode,'edit');
    }
});

test('Edit uses existing switchMode and requests field focus without changing data or scope',async()=>{
    const {c,calls,doc,field}=fixture();const data=structuredClone(c.model.root.data),context=structuredClone(c.props.context);
    await c.editRecord();assert.equal(c.model.root.isInEdition,true);assert.deepEqual(calls,[['mode','edit']]);
    c.focusRequestedRecordMode();assert.equal(doc.activeElement,field);
    assert.deepEqual(c.model.root.data,data);assert.deepEqual(c.props.context,context);assert.equal(c.requestedRecordFocus,null);
});

test('Edit refuses readonly, denied, new, already-editing and custom-handler flows before mode mutation',async()=>{
    for(const change of [c=>c.props.readonly=true,c=>c.canEdit=false,c=>c.model.root.isNew=true,c=>c.model.root.isInEdition=true,c=>c.props.saveRecord=()=>{}]) {
        const {c,calls}=fixture();change(c);await c.editRecord();assert.deepEqual(calls,[]);
    }
});

test('successful explicit save returns same existing record to reader and restores command focus',async()=>{
    const {c,calls,doc,command}=fixture({editing:true,dirty:true});
    assert.equal(await c.saveButtonClicked({closable:false}),true);assert.equal(c.model.root.isInEdition,false);
    assert.deepEqual(calls.map(c=>c[0]),['save','mode']);c.focusRequestedRecordMode();assert.equal(doc.activeElement,command);
});

test('false and thrown saves preserve editing/draft and do not request reader focus',async()=>{
    for(const saveResult of [false,new Error('Revision changed')]) {
        const {c,calls}=fixture({editing:true,dirty:true,saveResult});
        if(saveResult===false)assert.equal(await c.saveButtonClicked(),false);
        else await assert.rejects(c.saveButtonClicked(),/Revision changed/);
        assert.equal(c.model.root.isInEdition,true);assert.equal(c.model.root.dirty,true);assert.equal(c.requestedRecordFocus,null);
        assert.equal(calls.filter(c=>c[0]==='mode').length,0);
    }
});

test('onSave navigation or destruction cannot switch another record or focus an old controller',async()=>{
    for(const after of [c=>c.model.root={resId:30,isNew:false,isInEdition:true},c=>c.destroyed=true]) {
        const {c,calls}=fixture({editing:true,dirty:true});c.props.onSave=()=>after(c);
        await c.saveButtonClicked();assert.equal(calls.filter(c=>c[0]==='mode').length,0);assert.equal(c.requestedRecordFocus,null);
    }
});

test('Discard uses normal discard then reader; New abandons through history, dialog/custom stay owned',async()=>{
    const {c,calls}=fixture({editing:true,dirty:true});await c.discard();
    assert.deepEqual(calls,[['discard'],['mode','readonly']]);assert.equal(c.model.root.dirty,false);
    const fresh=fixture({resId:false,editing:true});await fresh.c.discard();assert.deepEqual(fresh.calls,[['discard'],['back']]);
    const dialog=fixture({editing:true});dialog.c.env.inDialog=true;await dialog.c.discard();assert.deepEqual(dialog.calls,[['discard'],['close']]);
    const external=fixture({editing:true});external.c.props.discardRecord=record=>external.calls.push(['external',record.resId]);
    await external.c.discard();assert.deepEqual(external.calls,[['external',20]]);
});

test('New explicitly enters editing in eligible readers; refused leave never loads a new record',async()=>{
    const {c,calls}=fixture();await c.create();assert.deepEqual(calls,[['load',{resId:false,mode:'edit'}]]);assert.equal(c.model.root.isInEdition,true);
    const refusal=fixture({editing:true,dirty:true,saveResult:false});await refusal.c.create();assert.equal(refusal.calls.filter(c=>c[0]==='load').length,0);
    const legacy=fixture();legacy.c.env.inDialog=true;await legacy.c.create();assert.deepEqual(legacy.calls,[['load',{resId:false}]]);
});

test('clean traversal chooses reader mode; legacy callback and loaded-ID scope remain unchanged',async()=>{
    const {c,calls}=fixture();await c.onPagerUpdate({offset:2,resIds:[10,20,30]});assert.deepEqual(calls,[['load',{resId:30,mode:'readonly'}]]);
    const legacy=fixture();legacy.c.display.controlPanel=false;await legacy.c.onPagerUpdate({offset:0,resIds:[10,20,30]});assert.deepEqual(legacy.calls,[['load',{resId:10}]]);
});

test('dirty traversal refuses without advancing; success exits editing on the actual replacement root without stealing pager focus',async()=>{
    const refusal=fixture({editing:true,dirty:true,saveResult:false});const original=refusal.c.model.root;
    assert.equal(await refusal.c.onPagerUpdate({offset:2,resIds:[10,20,30]}),false);assert.equal(refusal.c.model.root,original);assert.equal(original.isInEdition,true);
    const success=fixture({editing:true,dirty:true});success.c.requestedRecordFocus={kind:'field',record:success.c.model.root};await success.c.onPagerUpdate({offset:2,resIds:[10,20,30]});
    assert.equal(success.c.model.root.resId,30);assert.equal(success.c.model.root.isInEdition,false);assert.equal(success.c.requestedRecordFocus,null);
});

test('focus waits for its requested mode and never steals dialog/touch/disabled/replaced focus',async()=>{
    const waiting=fixture();waiting.c.requestedRecordFocus={kind:'field',record:waiting.c.model.root};waiting.c.focusRequestedRecordMode();assert.ok(waiting.c.requestedRecordFocus);assert.equal(waiting.calls.length,0);
    for(const change of [f=>f.doc.activeElement={},f=>f.touch.value=true,f=>f.c.archInfo.disableAutofocus=true,f=>f.c.model.root={isInEdition:true},f=>f.c.destroyed=true]) {
        const f=fixture({editing:true});f.c.requestedRecordFocus={kind:'field',record:f.c.model.root};change(f);f.c.focusRequestedRecordMode();
        assert.equal(f.calls.filter(c=>c[0]==='focus').length,0);assert.equal(f.c.requestedRecordFocus,null);
    }
});

const statusSource=(await readFile(new URL('framework_addons/web/static/src/views/form/form_status_indicator/form_status_indicator.js',root),'utf8')).replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,'');
const Indicator=new Function('Component','useRef','useState','useEffect','useBus','_t','document',statusSource+';return FormStatusIndicator;')(
    class {constructor(props){this.props=props;}},()=>({el:null}),x=>x,()=>{},()=>{},x=>x,{activeElement:null,body:{}});
test('actual status component clean editing offers Done/Cancel; legacy clean reader remains Saved without commands',()=>{
    const props={model:{root:{isNew:false,isValid:true,dirty:false},bus:{}},save:async()=>true,discard:async()=>{}};
    const status=new Indicator(props);status.setup();assert.equal(status.status,'Saved');assert.equal(status.displayButtons,false);
    props.editing=true;assert.equal(status.status,'Editing');assert.equal(status.displayButtons,true);assert.equal(status.saveLabel,'Done');assert.equal(status.discardLabel,'Cancel');
    props.model.root.dirty=true;assert.equal(status.status,'Unsaved changes');assert.equal(status.saveLabel,'Save changes');assert.equal(status.discardLabel,'Discard');
    props.model.root.isValid=false;assert.equal(status.status,'Check fields');props.model.root.isNew=true;assert.equal(status.saveLabel,'Save changes');
});
