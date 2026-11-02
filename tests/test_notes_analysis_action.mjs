import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const registrations=[];
globalThis.__analysisRegistry={category:name=>({add:(id,handler)=>registrations.push({name,id,handler})})};
const source=(await readFile(new URL('../platform_addons/mp_example_notes_stats/static/src/analysis.js',import.meta.url),'utf8'))
    .replace("import { registry } from '@web/core/registry';","const registry=globalThis.__analysisRegistry;");
const {createAnalysisAction}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));

function fixture({jobs=[null],revision=2,wait,now,language='en'}={}){
    const controller=new AbortController(),calls=[],notices=[];let index=0;
    const host={locale:{current:()=>({language})},notifications:{show:value=>notices.push(value)},services:{call:async(alias,method,input,options)=>{
        calls.push({alias,method,input,options});
        if(alias==='documents')return {revision};
        if(method==='analyze')return {job:{id:'job1',state:'pending'}};
        return {job:jobs[Math.min(index++,jobs.length-1)]};
    }}};
    const args={element:{},host,context:{note_id:'note1',expected_revision:2},signal:controller.signal};
    const action=createAnalysisAction({wait:wait||(()=>Promise.resolve()),now:now||(()=>0),timeout:100});
    return {args,action,controller,calls,notices};
}
const completed=(revision=2)=>({id:'job1',state:'completed',result:{note_id:'note1',revision,statistics:{characters:50,words:7,lines:1}}});

test('registers one existing Notes slot handler, without a new page',()=>{
    assert.equal(registrations.length,1);assert.equal(registrations[0].name,'mp.slot_actions');
    assert.equal(registrations[0].id,'org.example.notes_stats:action:analyze');
});
test('new analysis uses saved revision/idempotency and returns null, not a saved Note',async()=>{
    const f=fixture({jobs:[null,completed()]});assert.equal(await f.action(f.args),null);
    const post=f.calls.filter(c=>c.method==='analyze');assert.equal(post.length,1);
    assert.deepEqual(post[0].input,{note_id:'note1',expected_revision:2});assert.match(post[0].options.idempotencyKey,/^analysis-/);
    assert.ok(f.calls.every(c=>c.options.signal===f.args.signal));
    assert.deepEqual(f.notices.map(n=>n.severity),['info','success']);assert.match(f.notices[1].message,/revision 2: characters 50, words 7, lines 1/);
});
test('cached current result and pending job do not enqueue duplicate work',async()=>{
    for(const jobs of [[completed()],[{id:'job1',state:'running'},completed()]]){
        const f=fixture({jobs});await f.action(f.args);assert.equal(f.calls.filter(c=>c.method==='analyze').length,0);
        assert.equal(f.notices.at(-1).severity,'success');
    }
});
test('changed saved revision blocks enqueue and later changes block result display',async()=>{
    const f=fixture({revision:3});await f.action(f.args);assert.equal(f.calls.length,1);assert.match(f.notices[0].message,/saved note changed/);
    const g=fixture({jobs:[null,completed()]});let reads=0;const original=g.args.host.services.call;
    g.args.host.services.call=(a,m,i,o)=>a==='documents'&&++reads===2?Promise.resolve({revision:3}):original(a,m,i,o);
    await g.action(g.args);assert.equal(g.notices.some(n=>n.severity==='success'),false);assert.match(g.notices.at(-1).message,/saved note changed/);
});
test('timeout/crash errors visibly degrade analysis without a second write',async()=>{
    for(const code of ['DEADLINE_EXCEEDED','DEPENDENCY_UNAVAILABLE','PLUGIN_SUSPENDED']){
        const f=fixture({jobs:[null,{id:'job1',state:'dead_letter',error_code:code}]});await f.action(f.args);
        assert.equal(f.calls.filter(c=>c.method==='analyze').length,1);assert.match(f.notices.at(-1).message,/Analysis is unavailable. Notes are still available/);
    }
});
test('unknown and held outcomes never create another analysis request',async()=>{
    for(const state of ['outcome_unknown','held']){
        const f=fixture({jobs:[{id:'job1',state}]});await f.action(f.args);
        assert.equal(f.calls.filter(c=>c.method==='analyze').length,0);assert.equal(f.notices.at(-1).severity,'warning');
    }
});
test('retirement cancels polling and suppresses late cross-workspace results',async()=>{
    const f=fixture({jobs:[null,completed()]});f.action=createAnalysisAction({wait:async()=>f.controller.abort(),now:()=>0});
    await f.action(f.args);assert.equal(f.calls.filter(c=>c.method==='status').length,1);
    assert.equal(f.notices.some(n=>n.severity==='success'),false);
    const g=fixture({jobs:[completed()]});const original=g.args.host.services.call;
    g.args.host.services.call=async(...args)=>{const value=await original(...args);if(args[1]==='status')g.controller.abort();return value;};
    await g.action(g.args);assert.deepEqual(g.notices,[]);
});
test('newer actor request is not mistaken for this analysis result',async()=>{
    const f=fixture({jobs:[null,{...completed(),id:'job2'}]});await f.action(f.args);
    assert.equal(f.notices.some(n=>n.severity==='success'),false);assert.match(f.notices.at(-1).message,/newer analysis request/);
});
test('polling is bounded and re-opening reuses the outstanding job',async()=>{
    let clock=0;const f=fixture({jobs:[{id:'job1',state:'pending'}],wait:async()=>{clock+=60;},now:()=>clock});
    await f.action(f.args);assert.match(f.notices.at(-1).message,/still pending/);assert.equal(f.calls.filter(c=>c.method==='analyze').length,0);
});
test('duplicate clicks share the active scope and cleanup allows a later action',async()=>{
    let release;const barrier=new Promise(resolve=>release=resolve);const f=fixture({jobs:[completed()]});const original=f.args.host.services.call;
    f.args.host.services.call=async(...args)=>{await barrier;return original(...args);};
    const pending=f.action(f.args);await f.action(f.args);assert.match(f.notices[0].message,/already being checked/);
    release();await pending;assert.equal(f.notices.at(-1).severity,'success');await f.action(f.args);assert.equal(f.notices.filter(n=>n.severity==='success').length,2);
});
test('RPC failure is local degradation; Arabic uses the existing locale facade',async()=>{
    const f=fixture();f.args.host.services.call=async()=>{throw Object.assign(new Error('outage'),{code:'DEPENDENCY_UNAVAILABLE'});};
    await f.action(f.args);assert.match(f.notices[0].message,/Notes are still available/);
    const g=fixture({jobs:[completed()],language:'ar'});await g.action(g.args);assert.match(g.notices[0].message,/النسخة المحفوظة/);
});
