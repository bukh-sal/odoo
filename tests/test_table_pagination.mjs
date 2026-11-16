import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const source=(await readFile(new URL('../framework_addons/web/static/src/interface/table_pagination.js',import.meta.url),'utf8')).replace(/^import .*;\r?\n/gm,'');
let serial=0;
async function fixture(props={}) {
    const focus=[]; const body={}; const root={contains:node=>node==='button',querySelector:()=>({focus:options=>focus.push(options)})};
    globalThis.paginationFixture={Icon:class{},Component:class{constructor(props){this.props=props;}},useRef:()=>({el:root}),useState:x=>x,
        _t:(text,...args)=>text.replace(/%s/g,()=>args.shift()),document:{activeElement:body,body}};
    const prefix='const {Icon,Component,useRef,useState,_t,document}=globalThis.paginationFixture;\n';
    const module=await import('data:text/javascript;base64,'+Buffer.from(prefix+source).toString('base64')+'#'+serial++);
    const calls=[];const page=new module.TablePagination({offset:0,limit:25,total:251,onUpdate:async(...args)=>calls.push(args),...props});page.setup();
    return {...module,page,calls,focus,document:globalThis.paginationFixture.document};
}
test('bounded windows keep first/current/last, do not enumerate a large collection, and gaps are unique',async()=>{
    const {pageWindow}=await fixture();
    for(const total of [1,2,7,8,131,1_000_000])for(const current of [1,2,4,total-1,total]) {
        const page=Math.max(1,Math.min(total,current));const values=pageWindow(current,total);
        const numeric=values.filter(x=>typeof x==='number');
        assert.equal(numeric[0],1);assert.equal(numeric.at(-1),total);assert.ok(numeric.includes(page));
        assert.deepEqual(numeric,[...new Set(numeric)].sort((a,b)=>a-b));assert.ok(values.length<=9);
        assert.equal(new Set(values).size,values.length);
    }
});
test('previous and next do not wrap or send out-of-range pages; existing limit is preserved',async()=>{
    const {page,calls}=await fixture();assert.equal(page.canPrevious,false);
    await page.go(0);await page.go(1);await page.go(12);await page.go(NaN);assert.equal(calls.length,0);
    await page.go(2);assert.deepEqual(calls,[[{offset:25,limit:25},true]]);
    page.props={...page.props,offset:250};assert.equal(page.current,11);assert.equal(page.canNext,false);
    await page.go(12);assert.equal(calls.length,1);await page.go(10);assert.deepEqual(calls.at(-1),[{offset:225,limit:25},true]);
});
test('empty and single page results do not expose redundant page controls',async()=>{
    const {page}=await fixture({total:0});assert.equal(page.showControls,false);assert.equal(page.range,'No records');
    page.props.total=2;assert.equal(page.showControls,false);assert.equal(page.canNext,false);assert.equal(page.range,'1–2 of 2 records');
});
test('limited counts do not fabricate a final page; count uses only the provided model callback',async()=>{
    let counted=0;const {page,calls}=await fixture({offset:75,total:100,updateTotal:async()=>{counted++;}});
    assert.equal(page.limited,true);assert.deepEqual(page.pages,[4]);assert.equal(page.canNext,true);
    assert.match(page.range,/more results may be available/);await page.go(20);assert.equal(calls.length,0);
    await page.go(5);assert.deepEqual(calls.at(-1),[{offset:100,limit:25},true]);await page.count();assert.equal(counted,1);
    page.props={...page.props,total:131,updateTotal:undefined};assert.equal(page.limited,false);assert.ok(page.pages.includes(6));
});
test('a pending request is not duplicated and a refused save never optimistically changes the page',async()=>{
    let resolve;let count=0;const {page}=await fixture({onUpdate:()=>{count++;return new Promise(r=>resolve=r);}});
    const first=page.go(2);assert.equal(page.state.busy,true);await page.go(3);assert.equal(count,1);
    resolve(false);await first;assert.equal(page.current,1);assert.equal(page.state.busy,false);assert.equal(page.state.error,'');
});
test('failure retains model position and reports a recoverable error; a later request uses the same contract',async()=>{
    let fail=true;const calls=[];const {page}=await fixture({offset:25,onUpdate:async value=>{calls.push(value);if(fail)throw Error('Current data is unavailable');}});
    await page.go(3);assert.equal(page.current,2);assert.equal(page.state.error,'Current data is unavailable');assert.equal(page.state.busy,false);
    fail=false;await page.go(3);assert.equal(page.state.error,'');assert.deepEqual(calls,[{offset:50,limit:25},{offset:50,limit:25}]);
});
test('invalid or unsafe presentation inputs cannot produce a model request',async()=>{
    for(const props of [{limit:0},{offset:-1},{total:NaN},{offset:Number.MAX_SAFE_INTEGER+1},{limit:1.5}]) {
        const {page,calls}=await fixture(props);await page.go(2);assert.equal(page.valid,false);assert.equal(calls.length,0);
    }
});
test('a shrinking collection leaves an honest empty page with a working route back to the last real page',async()=>{
    const {page,calls}=await fixture({offset:250,total:101});
    assert.match(page.range,/No records on this page/);assert.equal(page.previousPage,5);
    await page.go(page.previousPage);assert.deepEqual(calls,[[{offset:100,limit:25},true]]);
});

// Execute the actual native producer closure, not a second pagination model.
const controllerSource=await readFile(new URL('../framework_addons/web/static/src/views/list/list_controller.js',import.meta.url),'utf8');
const producerBody=controllerSource.match(/usePager\(\(\) => \{([\s\S]*?)\n        \}\);/)[1];
const nativeProducer=new Function(producerBody);
test('native paging still saves/refuses an edited row before loading, preserving its existing model scope',async()=>{
    const calls=[];const root={count:131,hasLimitedCount:false,isGrouped:false,limit:25,offset:25,
        domain:['workspace=current','active=true'],orderBy:['name','id'],load:async args=>calls.push(['load',args])};
    const controller={model:{root},editedRecord:{save:async()=>{calls.push(['save']);return false;}},onPageChangeScroll:()=>calls.push(['scroll'])};
    await nativeProducer.call(controller).onUpdate({offset:50,limit:25},true);assert.deepEqual(calls,[['save']]);
    calls.length=0;controller.editedRecord.save=async()=>{calls.push(['save']);return true;};
    await nativeProducer.call(controller).onUpdate({offset:50,limit:25},true);
    assert.deepEqual(calls,[['save'],['load',{limit:25,offset:50}],['scroll']]);
    assert.deepEqual(root.domain,['workspace=current','active=true']);assert.deepEqual(root.orderBy,['name','id']);
});
test('native limited count callback remains unavailable to grouped roots and absent for sample data',async()=>{
    let counted=0;const controller={model:{root:{count:100,hasLimitedCount:true,isGrouped:false,limit:25,offset:0,fetchCount:()=>++counted}}};
    assert.equal(nativeProducer.call(controller).updateTotal(),1);assert.equal(counted,1);
    controller.model.root.isGrouped=true;assert.equal(nativeProducer.call(controller).updateTotal,undefined);
    controller.model.useSampleModel=true;assert.equal(nativeProducer.call(controller),undefined);
});

function method(source,name,globals={}){return new Function(...Object.keys(globals),'return class {'+source.match(new RegExp('    '+name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'[\\s\\S]*?\\n    }'))[0]+'}')(...Object.values(globals));}
const rendererSource=await readFile(new URL('../framework_addons/web/static/src/views/list/list_renderer.js',import.meta.url),'utf8');
const GroupProducer=method(rendererSource,'getGroupPagerProps(group)');
const GridNavigation=method(rendererSource,'findFocusFutureCell(cell, cellIsInGroupRow, direction)',{getElementToFocus:cell=>cell});
test('native grid arrows skip the new group footer while its controls stay in the normal Tab order',()=>{
    const cell=()=>({classList:{contains:()=>false}});
    const row=(kind,cells)=>{const value={classList:{contains:name=>name===kind},children:cells,parentElement:{}};cells.forEach(c=>c.parentElement=value);return value;};
    const first=row('o_data_row',[cell(),cell()]),footer=row('mp-group-pagination',[cell()]),last=row('o_data_row',[cell(),cell()]);
    first.nextElementSibling=footer;footer.previousElementSibling=first;footer.nextElementSibling=last;last.previousElementSibling=footer;
    const navigation=new GridNavigation();navigation.tableRef={el:{querySelector:()=>null}};
    assert.equal(navigation.findFocusFutureCell(first.children[1],false,'down'),last.children[1]);
    assert.equal(navigation.findFocusFutureCell(last.children[1],false,'up'),first.children[1]);
});
test('group page callbacks stay bound to their own group and retain exact count semantics',async()=>{
    const calls=[];const producer=new GroupProducer();producer.render=value=>calls.push(['render',value]);
    const group={count:151,list:{offset:25,limit:25,count:3,isGrouped:false,load:async input=>calls.push(['load',input])}};
    const props=producer.getGroupPagerProps(group);assert.equal(props.total,151);assert.equal(props.withAccessKey,false);
    await props.onUpdate({offset:50,limit:25});assert.deepEqual(calls,[['load',{limit:25,offset:50}],['render',true]]);
    group.list.isGrouped=true;assert.equal(producer.getGroupPagerProps(group).total,3);
});

test('actual root and nested producers distinguish group counts from record counts',async()=>{
    const controller={model:{root:{count:3,isGrouped:true,limit:25,offset:0}}};
    const rootProps=nativeProducer.call(controller);
    const {page}=await fixture(rootProps);
    assert.equal(page.range,'1–3 of 3 groups');
    controller.model.root.count=0;Object.assign(page.props,nativeProducer.call(controller));
    assert.equal(page.range,'No groups');
    const producer=new GroupProducer();
    const nested={displayName:'Organizations',count:151,list:{count:8,isGrouped:true,offset:0,limit:5}};
    Object.assign(page.props,producer.getGroupPagerProps(nested));
    assert.equal(page.range,'1–5 of 8 groups');
    nested.list.isGrouped=false;Object.assign(page.props,producer.getGroupPagerProps(nested));
    assert.equal(page.range,'1–5 of 151 records');
    page.props.isGrouped=true;page.props.offset=160;
    assert.match(page.range,/No groups on this page/);
});
const relationalSource=await readFile(new URL('../framework_addons/web/static/src/views/fields/x2many/x2many_field.js',import.meta.url),'utf8');
const RelationalProducer=method(relationalSource,'get pagerProps()');
test('embedded table paging retains its own edit refusal and abandoned-new-row limit correction',async()=>{
    const calls=[];const producer=new RelationalProducer();producer.render=()=>calls.push(['render']);
    const list={offset:0,limit:80,count:200,leaveEditMode:async()=>false,load:async args=>calls.push(['load',args])};producer.list=list;
    await producer.pagerProps.onUpdate({offset:80,limit:80});assert.equal(calls.length,0);
    list.leaveEditMode=async()=>{list.limit=79;return true;};
    await producer.pagerProps.onUpdate({offset:80,limit:80});assert.deepEqual(calls,[['load',{limit:79,offset:79}],['render']]);
    assert.equal(producer.pagerProps.withAccessKey,false);
});

const togglerSource=(await readFile(new URL('../framework_addons/web/static/src/search/search_bar/search_bar_toggler.js',import.meta.url),'utf8')).replace(/^import .*;\r?\n/gm,'');
async function toggler(alwaysVisible){
    const ui={isSmall:true};const effects=[];let resize;
    globalThis.togglerFixture={Icon:class{},Component:class{},useEffect:fn=>effects.push(fn),useState:x=>x,useService:()=>ui,useDebounced:fn=>fn,browser:{addEventListener:(name,fn)=>resize=fn,removeEventListener:()=>{}}};
    const prefix='const {Component,useEffect,useState,useService,useDebounced,browser}=globalThis.togglerFixture;\n';
    const {useSearchBarToggler}=await load(prefix+togglerSource);const result=useSearchBarToggler({alwaysVisible});effects[0]();
    return {ui,result,resize:()=>resize()};
}
const load=source=>import('data:text/javascript;base64,'+Buffer.from(source).toString('base64')+'#toggle'+serial++);
test('native table search stays visible on narrow/resized views without a duplicate toggler',async()=>{
    const f=await toggler(true);assert.equal(f.result.state.showSearchBar,true);assert.equal(f.result.props.isSmall,false);
    f.result.props.toggleSearchBar();assert.equal(f.result.state.showSearchBar,true);
    f.ui.isSmall=false;f.resize();f.ui.isSmall=true;f.resize();assert.equal(f.result.state.showSearchBar,true);
});
test('other native views retain their existing narrow search disclosure behavior',async()=>{
    const f=await toggler(false);assert.equal(f.result.state.showSearchBar,false);assert.equal(f.result.props.isSmall,true);
    f.result.props.toggleSearchBar();assert.equal(f.result.state.showSearchBar,true);
});


test('optional native page size delegates to the real model and preserves a nonstandard current limit',async()=>{
    const {page,calls}=await fixture({offset:80,limit:80,total:151,withPageSize:true});
    assert.equal(page.showPageSize,true);assert.deepEqual(page.pageSizes,[10,25,50,80,100]);
    const event={target:{value:'10'}};await page.changePageSize(event);
    assert.deepEqual(calls,[[{offset:0,limit:10},true]]);assert.equal(page.props.limit,80);assert.equal(event.target.value,'80');
    page.props.limit=10;await page.go(2);assert.deepEqual(calls.at(-1),[{offset:10,limit:10},true]);
});

test('size changes keep selection/focus and current value through save veto, error and busy state',async()=>{
    for(const outcome of [false,Error('kept current rows')]){
        const {page,calls}=await fixture({withPageSize:true,onUpdate:async()=>{if(outcome instanceof Error)throw outcome;return outcome;}});
        const event={target:{value:'50'}};await page.changePageSize(event);
        assert.equal(page.props.limit,25);assert.equal(event.target.value,'25');assert.equal(page.state.busy,false);
        assert.equal(page.state.error,outcome instanceof Error?outcome.message:'');
    }
    const {page,calls}=await fixture({withPageSize:true});page.state.busy=true;
    await page.changePageSize({target:{value:'50'}});assert.equal(calls.length,0);
});

test('size controls are opt-in, unavailable to grouped/empty/invalid/readonly roots, and reject unreviewed values',async()=>{
    for(const props of [{},{withPageSize:true,isGrouped:true},{withPageSize:true,total:0},{withPageSize:true,isEditable:false},{withPageSize:true,limit:0}]){
        const {page,calls}=await fixture(props);assert.ok(!page.showPageSize);await page.changePageSize({target:{value:'10'}});assert.equal(calls.length,0);
    }
    const {page,calls}=await fixture({withPageSize:true});
    for(const value of ['0','-5','1000000','2.5','NaN','25'])await page.changePageSize({target:{value}});
    assert.equal(calls.length,0);
});

test('real native size update preserves domain/order and refuses dirty-row discard',async()=>{
    const calls=[];const root={count:15,hasLimitedCount:false,isGrouped:false,limit:80,offset:0,domain:['scope=A'],orderBy:['name','id'],
        load:async values=>{calls.push(values);Object.assign(root,values);}};
    const controller={model:{root},editedRecord:{save:async()=>false},onPageChangeScroll:()=>{}};
    const {page}=await fixture({...nativeProducer.call(controller),withPageSize:true});
    await page.changePageSize({target:{value:'10'}});assert.equal(root.limit,80);assert.equal(calls.length,0);
    controller.editedRecord.save=async()=>true;await page.changePageSize({target:{value:'10'}});
    assert.deepEqual(calls,[{offset:0,limit:10}]);assert.deepEqual(root.domain,['scope=A']);assert.deepEqual(root.orderBy,['name','id']);
});
