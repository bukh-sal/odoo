/** Actual pure browser validator/client code; HTTP/native effects are G6. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const root=process.cwd();
const contractPath=path.join(root,'platform_addons/mp_shell/static/src/event_contract.js');
const contractURL='data:text/javascript;base64,'+Buffer.from(fs.readFileSync(contractPath,'utf8')).toString('base64');
const {validEventResult}=await import(contractURL);
const source=fs.readFileSync(path.join(root,'platform_addons/mp_shell/static/src/event_client.js'),'utf8');
assert(source.includes("from './event_contract'"));
const {DomainEventClient}=await import('data:text/javascript;base64,'+Buffer.from(source.replace("from './event_contract'",'from '+JSON.stringify(contractURL))).toString('base64'));
const cases=JSON.parse(fs.readFileSync(path.join(root,'packages/contracts/fixtures/v1/event-transport-cases.json'),'utf8')).valid;
const clone=value=>structuredClone(value);let passed=0;
async function test(name,fn){await fn();passed++;process.stdout.write('PASS '+name+'\n');}
function harness(overrides={}){
    const calls=[],errors=[],timers=new Map();let next=0;
    const context={site_id:cases.poll_result.deliveries[0].event.site_id,workspace_id:cases.poll_result.deliveries[0].event.workspace_id};
    const request=async message=>{
        calls.push(clone(message));
        if(overrides.request)return overrides.request(message,calls);
        if(message.kind==='subscribe_request')return clone(cases.subscribe_result);
        if(message.kind==='poll_request')return clone(cases.poll_result);
        if(message.kind==='ack_request')return {...clone(cases.ack_result),acknowledged:message.receipts.map(r=>r.delivery_id)};
        if(message.kind==='status_request')return {...clone(cases.status_result),deliveries:[],state:'active'};
        if(message.kind==='close_request')return clone(cases.close_result);
        throw Error('Unexpected test request');
    };
    const client=new DomainEventClient({context,generation:7,request,isCurrent:overrides.isCurrent||(()=>true),onError:e=>errors.push(e.code),clock:()=>Date.parse('2026-10-29T15:00:00Z'),setTimer:fn=>{const id=++next;timers.set(id,fn);return id;},clearTimer:id=>timers.delete(id),...overrides.options});
    return {client,calls,errors,timers,subscribe:callback=>{client.subscribe('org.example.notes.changed',callback,{binding_id:context.site_id});return [...client.entries.values()][0];}};
}
await test('default timers keep the browser global receiver for scheduling and cleanup',()=>{
    const originalSet=globalThis.setTimeout,originalClear=globalThis.clearTimeout;let scheduled=0,cleared=0;
    globalThis.setTimeout=function(){assert.equal(this,globalThis,'browser setTimeout receiver');scheduled++;return 19;};
    globalThis.clearTimeout=function(id){assert.equal(this,globalThis,'browser clearTimeout receiver');assert.equal(id,19);cleared++;};
    try{
        const client=new DomainEventClient({context:{},generation:1,request:()=>assert.fail('timer must not execute synchronously'),isCurrent:()=>true,onError:()=>assert.fail('unexpected error')});
        const off=client.subscribe('org.example.notes.changed',()=>{},{binding_id:cases.subscribe_result.subscription_id});off();client.dispose();assert.equal(scheduled,1);assert.equal(cleared,1);
    }finally{globalThis.setTimeout=originalSet;globalThis.clearTimeout=originalClear;}
});
await test('six golden results accepted; requests and unknown shapes rejected',()=>{
    for(const [name,value]of Object.entries(cases))assert.equal(validEventResult(value),name.endsWith('_result'),name);
    for(const value of [{},{kind:'unknown'},{kind:'__proto__'},null,true])assert.equal(validEventResult(value),false);
});
await test('strict calendar, payload identity, duplicate receipts and Unicode',()=>{
    for(const date of ['2026-02-30T15:00:00Z','0000-01-01T00:00:00Z','2026-10-29T15:00:00Z\n']){const value=clone(cases.poll_result);value.deliveries[0].lease_expires_at=date;assert.equal(validEventResult(value),false);}
    for(const mutation of [v=>v.deliveries.push(clone(v.deliveries[0])),v=>v.deliveries[0].event.payload.note_id=v.subscription_id,v=>v.deliveries[0].event.payload.body='private',v=>v.protocol=true,v=>v.extra='authority',v=>v.deliveries[0].event.payload.revision=true]){const value=clone(cases.poll_result);mutation(value);assert.equal(validEventResult(value),false);}
    const value=clone(cases.poll_result);value.deliveries[0].event.topic='org.example.other.changed';value.deliveries[0].event.owner_plugin_id='org.example.other';value.deliveries[0].event.payload={text:'😀'.repeat(2048)};assert.equal(validEventResult(value),true);
    value.deliveries[0].event.payload.text='\ud800';assert.equal(validEventResult(value),false);
});
await test('byte and depth limits apply before callbacks',()=>{
    const value=clone(cases.poll_result);const event=value.deliveries[0].event;event.topic='org.example.other.changed';event.owner_plugin_id='org.example.other';event.payload=Object.fromEntries(Array.from({length:8},(_,i)=>[String(i),'x'.repeat(2048)]));assert.equal(validEventResult(value),false);
    event.payload={};let item=event.payload;for(let i=0;i<20;i++){item.nested={};item=item.nested;}assert.equal(validEventResult(value),false);
});
await test('redelivery has one callback and ACKs each current receipt',async()=>{
    const h=harness();let effects=0;const entry=h.subscribe(event=>{effects++;assert.equal(event.generation,7);assert(Object.isFrozen(event));assert(Object.isFrozen(event.data));});
    await h.client.step(entry);await h.client.step(entry);assert.equal(effects,1);assert.equal(h.calls.filter(c=>c.kind==='ack_request').length,2);h.client.dispose();await Promise.resolve();
});
await test('one failed callback does not repeat a successful sibling effect',async()=>{
    const h=harness();let first=0,second=0;const entry=h.subscribe(()=>first++);
    h.client.subscribe(entry.topic,()=>{if(++second===1)throw Error('synthetic callback failure');},entry.binding);
    await h.client.step(entry);assert.equal(h.calls.filter(c=>c.kind==='ack_request').length,0);
    await h.client.step(entry);assert.equal(first,1);assert.equal(second,2);assert.equal(h.calls.filter(c=>c.kind==='ack_request').length,1);h.client.dispose();
});
await test('foreign workspace payload closes before any callback or ACK',async()=>{
    const h=harness({request:async message=>{if(message.kind==='subscribe_request')return clone(cases.subscribe_result);if(message.kind==='close_request')return clone(cases.close_result);const value=clone(cases.poll_result);value.deliveries[0].event.workspace_id=value.subscription_id;return value;}});let effects=0;const entry=h.subscribe(()=>effects++);await h.client.step(entry);assert.equal(effects,0);assert(h.errors.includes('FORBIDDEN'));assert.equal(h.client.entries.size,0);h.client.dispose();
});
await test('retired generation ignores an already-completed transport reply',async()=>{
    let release;let effects=0;const h=harness({request:async message=>{if(message.kind==='subscribe_request')return clone(cases.subscribe_result);if(message.kind==='close_request')return clone(cases.close_result);return new Promise(resolve=>release=resolve);}});
    const entry=h.subscribe(()=>effects++);const pending=h.client.step(entry);while(!release)await Promise.resolve();h.client.dispose();release(clone(cases.poll_result));await pending;assert.equal(effects,0);assert(!h.calls.some(c=>c.kind==='ack_request'));assert.equal(h.client.entries.size,0);
});
await test('pause drops its old reply and resume fetches under a new controller',async()=>{
    let release,polls=0,effects=0;const h=harness({request:async message=>{if(message.kind==='subscribe_request')return clone(cases.subscribe_result);if(message.kind==='close_request')return clone(cases.close_result);if(message.kind==='ack_request')return clone(cases.ack_result);if(++polls===1)return new Promise(resolve=>release=resolve);return clone(cases.poll_result);}});
    const entry=h.subscribe(()=>effects++);const pending=h.client.step(entry);while(!release)await Promise.resolve();h.client.pause();h.client.resume();release(clone(cases.poll_result));await pending;assert.equal(effects,0);await h.client.step(entry);assert.equal(effects,1);h.client.dispose();
});
await test('late creation after disposal is closed without payload polling',async()=>{
    let release;const h=harness({request:async message=>{if(message.kind==='subscribe_request')return new Promise(resolve=>release=resolve);assert.equal(message.kind,'close_request');return clone(cases.close_result);}});
    const entry=h.subscribe(()=>assert.fail('disposed callback'));const pending=h.client.step(entry);while(!release)await Promise.resolve();h.client.dispose();release(clone(cases.subscribe_result));await pending;await Promise.resolve();assert(h.calls.some(c=>c.kind==='close_request'));assert(!h.calls.some(c=>c.kind==='poll_request'));
});
await test('a reply older than30seconds cannot reach callbacks despite wall-clock drift',async()=>{
    let mono=0,effects=0;const h=harness({options:{monotonic:()=>mono},request:async message=>{if(message.kind==='subscribe_request')return clone(cases.subscribe_result);if(message.kind==='close_request')return clone(cases.close_result);mono+=31000;return clone(cases.poll_result);}});
    const entry=h.subscribe(()=>effects++);await h.client.step(entry);assert.equal(effects,0);assert(!h.calls.some(c=>c.kind==='ack_request'));h.client.dispose();
});
await test('a slow callback cannot pass stale event authority to a later callback',async()=>{
    let mono=0,first=0,second=0;const h=harness({options:{monotonic:()=>mono}});
    const entry=h.subscribe(()=>{first++;mono+=31000;});h.client.subscribe(entry.topic,()=>second++,entry.binding);
    await h.client.step(entry);assert.equal(first,1);assert.equal(second,0);assert(!h.calls.some(c=>c.kind==='ack_request'));
    await h.client.step(entry);assert.equal(first,1);assert.equal(second,1);assert.equal(h.calls.filter(c=>c.kind==='ack_request').length,1);h.client.dispose();
});
await test('unsubscribe and native wake subscription are disposed once',async()=>{
    let unwake=0;const h=harness({options:{wake:()=>()=>unwake++}});const off=h.client.subscribe('org.example.notes.changed',()=>{}, {binding_id:cases.poll_result.subscription_id});off();off();h.client.dispose();h.client.dispose();assert.equal(unwake,1);assert.equal(h.client.entries.size,0);assert.equal(h.timers.size,0);
});
process.stdout.write(JSON.stringify({result:'passed',checks:passed,limits:'Actual frontend validator/client semantics; native PostgreSQL/HTTP/browser integration remains required.'})+'\n');
