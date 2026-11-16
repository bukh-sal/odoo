import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const root=new URL('../framework_addons/web/static/src/',import.meta.url);
const read=p=>readFile(new URL(p,root),'utf8');
const compiler=await read('views/form/form_compiler.js');
const renderer=await read('views/form/form_renderer.js');
const methods=['createLabelFromField','compileField'].map(name=>compiler.match(new RegExp('^    '+name+'\\([^]*?^    }','m'))[0]).join('\n');
const identity=renderer.match(/^    fieldId\([^]*?^    }/m)[0];
const attrs=initial=>({values:{...initial},getAttribute(name){return this.values[name]??null;},hasAttribute(name){return name in this.values;},setAttribute(name,value){this.values[name]=value;}});
const Compiler=new Function('Base','createElement','toStringExpression','return class extends Base {'+methods+'}')(
    class{compileField(el){return attrs({id:JSON.stringify(el.getAttribute('field_id')),fieldInfo:'original-metadata'});}},
    (tag,props)=>({...attrs({}),tag,props}),JSON.stringify);
const Renderer=new Function('return class {'+identity+'}')();

test('actual field and explicit-label compiler share per-renderer DOM identity without changing metadata',()=>{
    const c=new Compiler();c.getLabels=()=>[];c.encounteredFields={};
    const el=attrs({name:'name',field_id:'name_0'}),field=c.compileField(el,{});
    const label=c.createLabelFromField('name_0','name','Name',{...attrs({}),className:'',textContent:''},{});
    assert.equal(field.getAttribute('fieldInfo'),'original-metadata');
    assert.equal(label.props.fieldInfo,"__comp__.props.archInfo.fieldNodes['name_0']");
    const ids=[];
    for(const prefix of ['form_field_1','form_field_2']){
        const instance=new Renderer();instance.fieldIdPrefix=prefix;
        const evaluate=expression=>new Function('__comp__','return '+expression)(instance);
        const inputId=evaluate(field.getAttribute('id')),labelId=evaluate(label.props.id);
        assert.equal(inputId,labelId);assert.equal(instance.fieldId('name_0'),inputId);ids.push(inputId);
    }
    assert.notEqual(ids[0],ids[1]);assert.equal(el.getAttribute('field_id'),'name_0');
});

test('multiple appearances remain distinct and stable within one renderer',()=>{
    const r=new Renderer();r.fieldIdPrefix='form_field_3';
    assert.notEqual(r.fieldId('name_0'),r.fieldId('name_1'));
    assert.equal(r.fieldId('name_0'),r.fieldId('name_0'));
});


test('controller-owned button-box compilation has its own scoped identity provider',async()=>{
    const controller=await read('views/form/form_controller.js');
    const method=controller.match(/^    fieldId\([^]*?^    }/m)[0];
    const Controller=new Function('return class {'+method+'}')();
    const c=new Compiler();c.getLabels=()=>[];c.encounteredFields={};
    const field=c.compileField(attrs({name:'count',field_id:'count_0'}),{isSubView:true});
    const owner=new Controller();owner.fieldIdPrefix='form_field_4';
    assert.equal(new Function('__comp__','return '+field.getAttribute('id'))(owner),'form_field_4-count_0');
});


test('both actual form ID imports resolve the real helper from its declared shipped module',async()=>{
    const owners=[renderer,await read('views/form/form_controller.js')];
    const ids=[];
    for(const source of owners){
        const modulePath=source.match(/import \{ uniqueId \} from "(@web\/[^"\n]+)"/)[1];
        const actual=await import(new URL(modulePath.replace('@web/','')+'.js',root));
        assert.equal(typeof actual.uniqueId,'function',modulePath);
        ids.push(actual.uniqueId('form_field_'));
    }
    assert.notEqual(ids[0],ids[1]);
});
