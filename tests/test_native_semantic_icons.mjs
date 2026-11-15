import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
const root=new URL('../',import.meta.url),read=p=>readFile(new URL(p,root),'utf8');
const source=await read('framework_addons/web/static/src/views/list/list_renderer.js');
const methods=['isSortable','getSortableIconClass','getSortableIconName','getSortDirection'].map(name=>source.match(new RegExp('^    '+name+'\\([^]*?^    }','m'))[0]).join('\n');
const Renderer=new Function('return class {'+methods+'}')();
const geometry=(await import(new URL('../framework_addons/web/static/src/interface/icons/lucide.js',import.meta.url))).ICON_NODES;
test('actual native sort presentation uses pinned semantic SVG states and keeps neutral/unsortable visibility',()=>{
 const r=new Renderer(),column={name:'name',hasLabel:true,options:{}};r.fields={name:{sortable:true}};r.props={list:{orderBy:[]}};
 assert.equal(r.getSortableIconName(column),'chevrons-up-down');assert.match(r.getSortableIconClass(column),/opacity-0/);
 assert.equal(r.getSortDirection(column),'none');
 for(const [asc,name] of [[true,'arrow-up'],[false,'arrow-down']]) {
  r.props.list.orderBy=[{name:'name',asc}];assert.equal(r.getSortableIconName(column),name);assert.equal(r.getSortableIconClass(column),'');assert.ok(geometry[name]?.length);
  assert.equal(r.getSortDirection(column),asc?'ascending':'descending');
 }
 r.fields.name.sortable=false;assert.match(r.getSortableIconClass(column),/d-none/);assert.equal(r.getSortDirection(column),undefined);column.options.allow_order=true;assert.doesNotMatch(r.getSortableIconClass(column),/d-none/);
 column.hasLabel=false;assert.match(r.getSortableIconClass(column),/d-none/);
});
test('selected native action/account icons use existing reviewed geometry without a new icon source',()=>{
 for(const name of ['ellipsis','printer','server','chevrons-up-down']) assert.ok(geometry[name]?.length,name);
});
