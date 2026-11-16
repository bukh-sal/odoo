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

test('shared writing and library controls have declared pinned geometry instead of fallback boxes',async()=>{
 const provenance=JSON.parse(await read('framework_addons/web/static/lib/lucide/provenance.json'));
 const {createHash}=await import('node:crypto');
 assert.equal(createHash('sha256').update(await read('framework_addons/web/static/src/interface/icons/lucide.js')).digest('hex'),provenance.generated_data_sha256);
 for(const name of ['house','files','layout-template','bold','italic','underline','strikethrough','code','list-ordered',
  'quote','undo-2','redo-2','grip-vertical','list-tree','type','heading-1','heading-2','heading-3','table']) {
  assert.ok(geometry[name]?.length,name);assert.match(provenance.selected_module_sha256[name],/^[0-9a-f]{64}$/);
  for(const node of geometry[name]) {assert.ok(['path','rect','circle','line','polyline','polygon','ellipse'].includes(node.tag));assert.equal(Object.hasOwn(node.attrs,'key'),false);}
 }
 assert.equal(provenance.version,'0.468.0');assert.deepEqual(provenance.runtime_dependencies_added,[]);
});


test('legal manifest underscore atoms resolve pinned glyphs without accepting paths or markup',async()=>{
 const raw=await readFile(new URL('../framework_addons/web/static/src/interface/icon.js',import.meta.url),'utf8');
 const cleaned=raw.replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,'');
 const resolve=new Function('Component','ICON_NODES',cleaned+';return iconName;')(class{},geometry);
 assert.equal(resolve('building_2'),'building-2');assert.equal(resolve('grid_2x2'),'grid-2x2');
 assert.equal(resolve('fa fa-users fa-fw'),'users');assert.equal(resolve('columns'),'columns-3');
 assert.equal(resolve('oi oi-archive'),'archive');assert.equal(resolve('oi oi-unarchive'),'archive');
 assert.equal(resolve('fa fa-clone'),'copy');assert.equal(resolve('fa fa-print'),'printer');
 for(const value of ['https://x/box','<svg/>','../users','__proto__','constructor','made_up_glyph',null,{}])assert.equal(resolve(value),'box');
});
