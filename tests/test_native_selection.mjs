import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
const root=new URL('../framework_addons/web/static/src/',import.meta.url);
const read=p=>readFile(new URL(p,root),'utf8');
const code=(await read('views/view_components/selection_box.js')).replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,'');
const SelectionBox=new Function('Component','Icon',code+';return SelectionBox;')(class{},class{});

test('actual clear-selection callback uses native record/domain selection only',()=>{
    const calls=[],records=[1,2].map(id=>({selected:true,toggleSelection(value){calls.push([id,value]);this.selected=value;}}));
    const root={records,get selection(){return records.filter(r=>r.selected);},selectDomain:value=>calls.push(['domain',value])};
    const c=new SelectionBox();c.props={root};c.setup();assert.equal(c.nbSelected,2);
    c.onUnselectAll();assert.deepEqual(calls,[[1,false],[2,false],['domain',false]]);assert.equal(c.nbSelected,0);
});

test('actual domain/count semantics retain limited/grouped and page-selected behavior',()=>{
    const calls=[],root={records:[1,2],selection:[1,2],count:15,recordCount:8,isGrouped:false,isRecordCountTrustable:true,hasLimitedCount:true,selectDomain:value=>calls.push(value)};
    const c=new SelectionBox();c.props={root};c.setup();assert.equal(c.isPageSelected,true);assert.equal(c.nbTotal,15);assert.equal(c.hasLimitedCount,true);
    c.onSelectDomain();assert.deepEqual(calls,[true]);root.isGrouped=true;assert.equal(c.nbTotal,8);
    root.isDomainSelected=true;assert.equal(c.isDomainSelected,true);
    root.isGrouped=false;root.count=2;assert.equal(c.isPageSelected,false);
});

test('actual row class keeps semantic selection, independent editing/decorations and drag behavior',async()=>{
    const source=await read('views/list/list_renderer.js');
    const method=source.match(/^    getRowClass\([^]*?^    }/m)[0];
    const Renderer=new Function('evaluateBooleanExpr','return class {'+method+'}')((expr)=>expr===true);
    const r=new Renderer();r.props={archInfo:{decorations:[{condition:true,class:'text-danger'}]}};r.canResequenceRows=true;
    const result=r.getRowClass({selected:true,isInEdition:true});
    assert.match(result,/o_data_row_selected/);assert.match(result,/o_selected_row/);assert.match(result,/text-danger/);assert.match(result,/o_row_draggable/);
    assert.doesNotMatch(result,/table-info/);assert.doesNotMatch(r.getRowClass({selected:false,isInEdition:false}),/o_data_row_selected|o_selected_row/);
});

test('actual native display keeps query during selection and honors explicit author hiding',async()=>{
    const source=await read('views/list/list_controller.js');
    const method=source.match(/^    get display\([^]*?^    }/m)[0];
    const Producer=new Function('return class {'+method+'}')();
    const p=new Producer();p.hasSelectedRecords=true;p.collectionMeta='15 matching records';
    const flags={searchBar:true};p.props={display:{controlPanel:flags}};
    assert.equal(p.display.controlPanel.layoutActions,true);assert.equal(p.display.controlPanel.table,true);assert.deepEqual(flags,{searchBar:true});
    flags.layoutActions=false;assert.equal(p.display.controlPanel.layoutActions,false);
    p.props.display.controlPanel=false;assert.equal(p.display,p.props.display);
});
