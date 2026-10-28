import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../platform_addons/mp_shell/static/src/client_release.js',import.meta.url),'utf8');
const {ClientReleaseFence,validRelease,isReleaseError}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const document=JSON.parse(await readFile(new URL('../packages/contracts/examples/v1/client-release.json',import.meta.url),'utf8'));

test('bootstrap pin cannot be mutated or silently adopted from a newer poll',async()=>{
    const input={...document};const fence=new ClientReleaseFence(input);input.generation++;
    assert.equal(fence.document.generation,document.generation);assert.equal(fence.observe(document),true);
    assert.equal(fence.headers()['X-MP-Client-Release'],document.token);
    assert.equal(fence.observe({...document,generation:document.generation+1}),false);
    assert.equal(fence.document.generation,document.generation);
    assert.throws(()=>fence.assert('/api/v1/services/notes/update'),isReleaseError);
    assert.equal(fence.observe(document),false);
});
test('mismatch fences synchronously before asynchronous retirement and only once',async()=>{
    const fence=new ClientReleaseFence(document);let calls=0,finish;
    fence.onChange=async()=>{calls++;await new Promise(resolve=>finish=resolve);};
    fence.block();fence.block();
    assert.throws(()=>fence.assert('/web/dataset/call_kw'),isReleaseError);
    await Promise.resolve();assert.equal(calls,1);finish();await fence.retirement;
    fence.block();assert.equal(calls,1);
});
test('safe auth/draft discovery remains usable but retries and native calls stay fenced',()=>{
    const fence=new ClientReleaseFence(document);fence.block();
    for(const path of ['/api/v1/session','/api/v1/client-release','/api/v1/workspaces','/web/session/check'])assert.doesNotThrow(()=>fence.assert(path));
    for(const path of ['/api/v1/context','/api/v1/operations/request','/web/action/load'])assert.throws(()=>fence.assert(path),isReleaseError);
});
test('malformed or missing bootstrap fails closed without automatic reload',()=>{
    for(const value of [null,{}, {...document,token:document.token+'\n'}, {...document,generation:0}, {...document,protocol:2}]){
        assert.ok(!validRelease(value));const fence=new ClientReleaseFence(value);
        assert.throws(()=>fence.assert('/api/v1/context'),isReleaseError);
    }
});
test('private native release exception maps distinctly from record CAS conflicts',()=>{
    assert.ok(isReleaseError({exceptionName:'odoo.addons.mp_identity.release.ClientReleaseMismatch'}));
    assert.ok(!isReleaseError({code:'CONFLICT',details:{field:'revision'}}));
});
test('failed page disposal cannot unblock or reload the document',async()=>{
    const fence=new ClientReleaseFence(document);fence.onChange=()=>{throw new Error('dispose failure');};
    fence.block();await assert.rejects(fence.retirement);
    assert.throws(()=>fence.assert('/api/v1/context'),isReleaseError);
});
test('late response cannot falsely claim that a possibly committed write never started',()=>{
    const fence=new ClientReleaseFence(document);fence.block();
    assert.throws(()=>fence.assert('/api/v1/services/notes/update','unknown'),error=>isReleaseError(error)&&error.details.outcome==='unknown');
    assert.throws(()=>fence.assert('/api/v1/services/notes/update'),error=>isReleaseError(error)&&error.details.outcome==='not_started');
});
