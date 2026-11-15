import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const read=p=>readFile(new URL('../framework_addons/web/static/src/'+p,import.meta.url),'utf8');
const clean=s=>s.replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,'');
const parent=clean(await read('views/view_dialogs/form_view_dialog.js'));
const source=clean(await read('views/view_dialogs/record_create_dialog.js'));
const helper=clean(await read('views/view_dialogs/record_creation.js'));
const turn=()=>new Promise(resolve=>setImmediate(resolve));

function fixture({dirty=false,save=async()=>true,refresh=async()=>{}}={}) {
    const calls=[],prompts=[],listeners=[],childEnvs=[];
    class Component {setup() {}}
    class Dialog {static props={size:{type:String,optional:true}};get contentStyle(){return 'original';}}
    class ConnectionLostError extends Error {}
    class ConnectionAbortedError extends Error {}
    class ConfirmationDialog {}
    const services={action:{doAction:()=>assert.fail('Presentation must not navigate/save on expansion')},dialog:{add:(Class,props,options)=>{
        const p={Class,props,options};prompts.push(p);return ()=>options?.onClose?.();
    }}};
    const args={Component,Dialog,View:class{},Icon:class{},ConfirmationDialog,ConnectionLostError,ConnectionAbortedError,
        useService:n=>services[n],useChildRef:()=>({el:{}}),CallbackRecorder:class{},useState:v=>v,
        useChildSubEnv:env=>childEnvs.push(env),useBus:(bus,event,fn)=>listeners.push({event,fn}),
        useExternalListener:(target,event,fn)=>listeners.push({event,fn}),window:{},_t:s=>s};
    const classes=new Function(...Object.keys(args),parent+'\n'+source+'\nreturn {RecordCreateDialog,CreationSurfaceDialog};')(...Object.values(args));
    let closed=0;
    const props={...classes.RecordCreateDialog.defaultProps,close:()=>{closed++;},resModel:'owned.example',
        context:{workspace:'A',language:'en_US'},viewId:37,title:'Create example',onRecordSaved:async r=>{calls.push('refresh');await refresh(r);}};
    const c=new classes.RecordCreateDialog();c.props=props;c.env={bus:{},dialogData:{}};c.setup();
    const record={dirty,resId:false,isDirty:async()=>{calls.push('flush-draft');return record.dirty;},save:async opts=>{calls.push(['save',opts]);return save();}};
    c.viewProps.onRecordReady(record);
    return {c,calls,prompts,listeners,record,classes,childEnvs,ConnectionLostError,ConnectionAbortedError,closed:()=>closed};
}

test('creation reuses the actual native dialog view props and selected form/model context',()=>{
    const f=fixture();
    assert.equal(f.c.viewProps.resModel,'owned.example');assert.equal(f.c.viewProps.viewId,37);
    assert.equal(f.c.viewProps.context,f.c.props.context);assert.equal(f.c.viewProps.resId,false);
    assert.equal(f.c.viewProps.preventAutoSave,true);assert.equal(f.c.viewProps.preventCreate,true);
    assert.equal(f.c.record,f.record);assert.equal(f.childEnvs[0].recordCreation.state,f.c.state);
    f.c.viewProps.onRecordReady(null);assert.equal(f.c.record,null);
});

test('fullscreen expansion changes presentation only and retains record and draft',()=>{
    const f=fixture({dirty:true});f.record.data={name:'Unsaved example'};
    f.c.toggleFullscreen();assert.equal(f.c.state.fullscreen,true);f.c.toggleFullscreen();
    assert.equal(f.c.state.fullscreen,false);assert.equal(f.c.record,f.record);
    assert.equal(f.c.record.data.name,'Unsaved example');assert.deepEqual(f.calls,[]);assert.equal(f.closed(),0);
});

test('pristine close flushes pending changes; dirty close is one decision and Keep editing retains it',async()=>{
    const empty=fixture();assert.equal(await empty.c.requestClose(),true);assert.equal(empty.closed(),1);
    const f=fixture({dirty:true});const first=f.c.requestClose(),second=f.c.requestClose();await turn();
    assert.equal(f.prompts.length,1);assert.equal(f.closed(),0);assert.equal(f.c.state.closing,true);
    f.prompts[0].props.cancel();assert.deepEqual(await Promise.all([first,second]),[false,false]);
    assert.equal(f.record.dirty,true);assert.equal(f.closed(),0);assert.equal(f.c.state.closing,false);
    const discard=f.c.requestClose();await turn();f.prompts[1].props.confirm();
    assert.equal(await discard,true);assert.equal(f.closed(),1);assert.ok(!f.calls.some(x=>Array.isArray(x)));
});

test('header and Escape use the guarded dismiss owner, including a veto',async()=>{
    const f=fixture(),dialog=new f.classes.CreationSurfaceDialog();let asked=0;
    dialog.props={requestClose:async()=>{asked++;return false;},sheet:true};
    assert.equal(await dialog.dismiss(),false);assert.equal(asked,1);assert.equal(f.closed(),0);
    assert.equal(dialog.contentStyle,'');dialog.props.sheet=false;assert.equal(dialog.contentStyle,'original');
});

test('successful native save runs once then refreshes and closes; validation keeps the draft',async()=>{
    const f=fixture();assert.equal(await f.c.viewProps.saveRecord(f.record),true);
    assert.deepEqual(f.calls,[['save',{reload:false}],'refresh']);assert.equal(f.closed(),1);
    assert.equal(await f.c.saveRecord(f.record),false);assert.equal(f.calls.length,2);
    const invalid=fixture({dirty:true,save:async()=>false});assert.equal(await invalid.c.saveRecord(invalid.record),false);
    assert.equal(invalid.closed(),0);assert.equal(invalid.c.state.saved,false);assert.equal(invalid.record.dirty,true);
});

test('busy save refuses a second submit or close until the actual result arrives',async()=>{
    let finish;const f=fixture({save:()=>new Promise(resolve=>{finish=resolve;})});
    const first=f.c.saveRecord(f.record);assert.equal(f.c.state.saving,true);
    assert.equal(await f.c.saveRecord(f.record),false);assert.equal(await f.c.requestClose(),false);
    assert.equal(f.calls.length,1);assert.equal(f.closed(),0);finish(true);assert.equal(await first,true);
});

test('transport uncertainty retains draft and refuses blind native create retry',async()=>{
    for(const name of ['ConnectionLostError','ConnectionAbortedError']) {
        const f=fixture({dirty:true});let count=0;f.record.save=async()=>{count++;throw new f[name]('lost');};
        assert.equal(await f.c.saveRecord(f.record),false);assert.equal(f.c.state.uncertain,true);
        assert.equal(f.closed(),0);assert.equal(f.record.dirty,true);
        assert.equal(await f.c.saveRecord(f.record),false);assert.equal(count,1);
        const close=f.c.requestClose();await turn();assert.match(f.prompts[0].props.body,/may already/);
        f.prompts[0].props.cancel();assert.equal(await close,false);
    }
});

test('server validation error stays native and does not classify as transport uncertainty',async()=>{
    const error=new Error('native validation');const f=fixture({save:async()=>{throw error;}});
    await assert.rejects(f.c.saveRecord(f.record),e=>e===error);assert.equal(f.c.state.uncertain,false);
    assert.equal(f.c.state.saving,false);assert.equal(f.closed(),0);
});

test('refresh failure reports created and cannot issue another create',async()=>{
    const f=fixture({refresh:async()=>{throw Error('offline refresh');}});
    assert.equal(await f.c.saveRecord(f.record),true);assert.equal(f.c.state.saved,true);
    assert.match(f.c.state.error,/record was created/);assert.equal(f.closed(),0);
    assert.equal(await f.c.saveRecord(f.record),false);assert.equal(f.calls.length,2);
    assert.equal(await f.c.requestClose(),true);assert.equal(f.closed(),1);
});

test('global leave uses the same close decision and unload warns without saving',async()=>{
    const f=fixture({dirty:true}),callbacks=[];
    f.listeners.find(x=>x.event==='CLEAR-UNCOMMITTED-CHANGES').fn({detail:callbacks});assert.equal(callbacks.length,1);
    const leave=callbacks[0]();await turn();f.prompts[0].props.cancel();assert.equal(await leave,false);
    let prevented=0;const event={preventDefault:()=>prevented++};
    f.listeners.find(x=>x.event==='beforeunload').fn(event);assert.equal(prevented,1);assert.equal(event.returnValue,'Unsaved creation draft');
    assert.ok(!f.calls.some(x=>Array.isArray(x)));
});

test('native policy delegates page; dialog/sheet select only the creation form without input mutation',async()=>{
    const calls=[],dialogs=[];class RecordCreateDialog {}
    const {openRecordCreation,creationSurface}=new Function('RecordCreateDialog',helper+';return {openRecordCreation,creationSurface};')(RecordCreateDialog);
    for(const value of [undefined,'page']) {
        assert.equal(openRecordCreation({context:{create_surface:value},openPage:()=>{calls.push('page');return 'page-opened';}}),'page-opened');
    }
    for(const surface of ['dialog','sheet']) {
        const context={create_surface:surface,create_form_view_ref:'owner.quick_form',workspace:'A'},before=structuredClone(context);
        const wait=openRecordCreation({context,resModel:'owned.example',viewId:20,dialog:{add:(Class,props,options)=>dialogs.push({Class,props,options})}});
        const item=dialogs.at(-1);assert.equal(item.Class,RecordCreateDialog);assert.equal(item.props.viewId,false);
        assert.equal(item.props.context.form_view_ref,'owner.quick_form');assert.equal(item.props.context.workspace,'A');
        assert.equal(item.props.surface,surface);assert.deepEqual(context,before);item.options.onClose('closed');assert.equal(await wait,'closed');
    }
    for(const value of [null,false,1,'','auto','modal']) assert.throws(()=>creationSurface(value),/create_surface/);
    for(const ref of ['',null,3,'x'.repeat(257)]) assert.throws(()=>openRecordCreation({context:{create_surface:'dialog',create_form_view_ref:ref}}),/create_form_view_ref/);
    assert.equal(calls.length,2);assert.equal(dialogs.length,2);
});

const controllerSource=await read('views/form/form_controller.js');
test('creation-only lifecycle suppresses auto saves while ordinary native lifecycle is retained',async()=>{
    const names=['beforeVisibilityChange','beforeLeave','beforeUnload'];
    const methods=names.map(n=>controllerSource.match(new RegExp('^    (?:async )?'+n+'\\([^]*?^    }','m'))[0]).join('\n');
    const doc={visibilityState:'hidden'},Controller=new Function('document','return class{'+methods+'}')(doc);
    const c=new Controller(),calls=[];c.props={preventAutoSave:true};c.formInDialog=0;
    c.model={root:{dirty:true,activeFields:{},isDirty:async()=>true,save:()=>calls.push('visibility-save'),urgentSave:async()=>{calls.push('unload-save');return true;}}};c.save=async()=>calls.push('leave-save');
    const ev={preventDefault:()=>assert.fail('Wrapper owns synchronous unload warning')};
    c.beforeVisibilityChange();assert.equal(await c.beforeLeave(),false);await c.beforeUnload(ev);assert.deepEqual(calls,[]);
    c.props.preventAutoSave=false;c.beforeVisibilityChange();await c.beforeLeave();await c.beforeUnload(ev);
    assert.deepEqual(calls,['visibility-save','leave-save','unload-save']);
});

const listSource=await read('views/list/list_controller.js');
test('explicit native list creation overrides inline only by author choice; save callback reloads',async()=>{
    const method=listSource.match(/^    async createRecord\([^]*?^    }/m)[0];class DynamicRecordList {}
    const {creationSurface}=new Function('RecordCreateDialog',helper+';return {creationSurface};')(class{});
    const Controller=new Function('DynamicRecordList','creationSurface','return class{'+method+'}')(DynamicRecordList,creationSurface),c=new Controller();
    let created=0,reloaded=0;const group=Object.assign(new DynamicRecordList(),{isGrouped:false,editedRecord:null,leaveEditMode:async()=>{},addNewRecord:async()=>created++});
    c.props={context:{create_surface:'sheet'},createRecord:async options=>{await options.onRecordSaved();}};
    c.model={isReady:true,config:{groupBy:[]},root:group,load:async()=>reloaded++};c.editable='top';c.render=()=>{};
    await c.createRecord();assert.equal(reloaded,1);assert.equal(created,0);
    c.props.context={};await c.createRecord();assert.equal(created,1);assert.equal(reloaded,1);
    c.props.context={create_surface:'dialog'};group.leaveEditMode=async()=>false;
    await c.createRecord();assert.equal(reloaded,1,'Refused existing-row leave must not open a dialog or reload away its draft');
    let settled=0;group.leaveEditMode=async()=>{settled++;};c.props.context={create_surface:'unknown'};
    await assert.rejects(c.createRecord(),/create_surface/);assert.equal(settled,0,'Invalid author policy must refuse before settling an edited row');
});

test('actual native action producer applies creation policy without changing existing-record routing',async()=>{
    const source=await read('webclient/actions/action_service.js');
    const producer=source.match(/^    function _getViewInfo\([^]*?^    }/m)[0];
    class RecordCreateDialog {}const {openRecordCreation}=new Function('RecordCreateDialog',helper+';return {openRecordCreation};')(RecordCreateDialog);
    const opened=[],dialogs=[];
    const produce=new Function('openRecordCreation','switchView','doAction','env','_getView','shallowEqual','pushState',producer+';return _getViewInfo;')(
        openRecordCreation,(...args)=>opened.push(args),()=>assert.fail('Existing declared form should be reused'),
        {services:{dialog:{add:(Class,props,options)=>dialogs.push({Class,props,options})}}},()=>({type:'form'}),()=>true,()=>{});
    const view={type:'list',multiRecord:true},action={id:9,name:'Example records',res_model:'owned.example',views:[[11,'list'],[37,'form']],context:{workspace:'A',create_surface:'sheet'},target:'current'};
    const info=produce(view,action,[view,{type:'form',multiRecord:false}]);
    const pending=info.props.createRecord();assert.equal(dialogs[0].props.resModel,'owned.example');assert.equal(dialogs[0].props.viewId,37);assert.equal(dialogs[0].props.context.workspace,'A');
    dialogs[0].options.onClose();await pending;
    info.props.selectRecord(44,{activeIds:[44,45]});assert.equal(opened[0][0],'form');assert.equal(opened[0][1].resId,44);assert.deepEqual(opened[0][1].resIds,[44,45]);assert.equal(dialogs.length,1);
    const ordinary=produce(view,{...action,context:{workspace:'A'}},[view]);ordinary.props.createRecord();assert.equal(opened[1][1].resId,false);assert.equal(dialogs.length,1);
});
