/** Execute the real framework-neutral page with instrumented standard EventTargets. */
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {getEventListeners} from 'node:events';
import {readFile} from 'node:fs/promises';

const source=await readFile(new URL('../platform_addons/mp_example_canvas/static/src/page.js',import.meta.url),'utf8');
const {CanvasPage}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));

class Element extends EventTarget {
    constructor(tag){super();this.tagName=tag;this.children=[];this.attributes={};this.dataset={};this.value='';this.className='';}
    setAttribute(key,value){this.attributes[key]=value;}
    append(...children){for(const child of children){child.parent=this;this.children.push(child);}}
    replaceChildren(...children){for(const child of this.children)child.parent=null;this.children=[];this.append(...children);}
    remove(){if(this.parent)this.parent.children=this.parent.children.filter(child=>child!==this);this.parent=null;}
    querySelector(selector){return this.walk().find(child=>selector.startsWith('.')?child.className.split(' ').includes(selector.slice(1)):child.tagName===selector)||null;}
    walk(){return this.children.flatMap(child=>[child,...child.walk()]);}
    focus(){}
}

function fixture(){
    const document=new EventTarget();document.createElement=tag=>new Element(tag);globalThis.document=document;
    const element=new Element('div'),themes=new Set(),calls=[];
    const board={id:'00000000-0000-4000-8000-000000000001',name:'Lifecycle board',revision:1,cards:[]};
    const host={context:()=>({capabilities:['org.example.canvas:canvas.write']}),theme:{current:()=>({mode:'light'}),subscribe:callback=>{themes.add(callback);return()=>themes.delete(callback);}},
        locale:{current:()=>({direction:'ltr'})},dialogs:{confirm:async()=>false},navigate:async()=>{},
        services:{call:async(alias,method,input)=>{
            calls.push({alias,method,input});
            if(alias==='documents')return {documents:[]};
            if(method==='get')return structuredClone(board);
            return {...structuredClone(board),...input,id:input.board_id,revision:input.expected_revision+1};
        }}};
    return {document,element,themes,calls,host,board,route:{query:{}}};
}

test('repeated mounts dispose document handlers, theme subscriptions and owned DOM',async()=>{
    const f=fixture();
    for(let i=0;i<12;i++){
        const controller=new AbortController();const page=await CanvasPage.mount({...f,signal:controller.signal});
        assert.equal(getEventListeners(f.document,'keydown').length,1);assert.equal(f.themes.size,1);assert.equal(f.element.children.length,1);
        controller.abort();await page.dispose();
        assert.equal(getEventListeners(f.document,'keydown').length,0);assert.equal(f.themes.size,0);assert.equal(f.element.children.length,0);
    }
});
test('only the current mount handles one keyboard save after prior disposal',async()=>{
    const f=fixture();
    for(let i=0;i<4;i++){
        const controller=new AbortController();const page=await CanvasPage.mount({...f,signal:controller.signal});controller.abort();await page.dispose();
    }
    const controller=new AbortController();const page=await CanvasPage.mount({...f,signal:controller.signal});
    const event=new Event('keydown',{cancelable:true});Object.assign(event,{ctrlKey:true,key:'s'});f.document.dispatchEvent(event);
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(f.calls.filter(call=>call.alias==='boards'&&call.method==='save').length,1);
    controller.abort();await page.dispose();
    f.document.dispatchEvent(event);await new Promise(resolve=>setImmediate(resolve));
    assert.equal(f.calls.filter(call=>call.method==='save').length,1);
});
test('late initial response after abort cannot retain a page or subscriptions',async()=>{
    const f=fixture();let complete;f.host.services.call=()=>new Promise(resolve=>complete=resolve);
    const controller=new AbortController();const mounted=CanvasPage.mount({...f,signal:controller.signal});controller.abort();complete({documents:[]});
    await assert.rejects(mounted,{name:'AbortError'});
    assert.equal(f.element.children.length,0);assert.equal(f.themes.size,0);assert.equal(getEventListeners(f.document,'keydown').length,0);
});
test('late save completion cannot update a replacement mount',async()=>{
    const f=fixture();const original=f.host.services.call;let finishSave;
    f.host.services.call=(alias,method,input)=>method==='save'?new Promise(resolve=>finishSave=resolve):original(alias,method,input);
    const first=new AbortController();const oldPage=await CanvasPage.mount({...f,signal:first.signal});
    const event=new Event('keydown',{cancelable:true});Object.assign(event,{ctrlKey:true,key:'s'});f.document.dispatchEvent(event);
    first.abort();await oldPage.dispose();
    const second=new AbortController();const current=await CanvasPage.mount({...f,signal:second.signal});
    finishSave({...f.board,revision:2});await new Promise(resolve=>setImmediate(resolve));
    assert.match(f.element.querySelector('.mp_canvas_status').textContent,/^Revision 1/);
    assert.equal(f.element.children.length,1);assert.equal(f.themes.size,1);assert.equal(getEventListeners(f.document,'keydown').length,1);
    second.abort();await current.dispose();
});
test('dirty page exposes a safe JSON snapshot and dispose retains no draft DOM',async()=>{
    const f=fixture();const controller=new AbortController();const page=await CanvasPage.mount({...f,signal:controller.signal});
    const title=f.element.walk().find(node=>node.attributes['aria-label']==='Board name');title.value='Unsaved lifecycle draft';title.dispatchEvent(new Event('input'));
    assert.equal(page.canLeave(),'confirm');
    const snapshot=JSON.parse(JSON.stringify(page.snapshotDraft()));
    assert.equal(snapshot.filename,'canvas-draft.json');assert.equal(snapshot.data.name,title.value);assert.equal(snapshot.data.board_id,f.board.id);assert.equal(snapshot.data.expected_revision,1);
    controller.abort();await page.dispose();assert.equal(f.element.children.length,0);
});
