import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
const root=new URL('../',import.meta.url);
const source=await readFile(new URL('framework_addons/web/static/src/core/dialog/dialog.xml',root),'utf8');
const expression=name=>new Function('props','id','return ('+source.match(new RegExp('t-att-'+name+'="([^"]+)"'))[1].replace(/\band\b/g,'&&').replace(/\bor\b/g,'||')+');');
const labelledBy=expression('aria-labelledby'),label=expression('aria-label');
test('optional native action slots retain the visible heading as the dialog name',()=>{
    const props={header:true,title:'Preferences'};
    assert.equal(labelledBy(props,'dialog-1'),'dialog-1_title');assert.equal(label(props,'dialog-1'),undefined);
});
test('ordinary, custom-header and headerless dialogs retain one meaningful name',()=>{
    const ordinary={header:true,title:'Warning',slots:{default:{}}};
    assert.equal(labelledBy(ordinary,'dialog-2'),'dialog-2_title');assert.equal(label(ordinary,'dialog-2'),undefined);
    for(const props of [{...ordinary,slots:{default:{},header:{}}},{header:false,title:'Preview'}]){
        assert.equal(labelledBy(props,'dialog-3'),undefined);assert.equal(label(props,'dialog-3'),props.title);
    }
});
