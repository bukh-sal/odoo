/** Mount-scoped transport; native bus wakes it, durable server receipts decide. */
import { validEventResult } from './event_contract';
const problem=code=>Object.assign(new Error(code),{code,retryable:false});
const freeze=value=>{if(value&&typeof value==='object'){Object.values(value).forEach(freeze);Object.freeze(value);}return value;};

export class DomainEventClient {
    constructor({context,generation,request,isCurrent,onError,onDeadLetter=()=>{},wake=()=>()=>{},clock=()=>Date.now(),monotonic=()=>performance.now(),setTimer=(callback,delay)=>globalThis.setTimeout(callback,delay),clearTimer=timer=>globalThis.clearTimeout(timer)}){
        Object.assign(this,{context,generation,request,isCurrent,onError,onDeadLetter,clock,monotonic,setTimer,clearTimer});
        this.active=true;this.paused=false;this.entries=new Map();this.unwake=wake(()=>this.resumeTimers());
    }
    current(entry){return this.active&&!this.paused&&entry.active&&this.isCurrent();}
    subscribe(topic,callback,binding){
        if(!this.active||!this.isCurrent())throw problem('CANCELLED');
        if(typeof callback!=='function'||!binding?.binding_id)throw problem('VALIDATION_FAILED');
        const key=binding.binding_id+'/'+topic;let entry=this.entries.get(key);
        if(!entry){entry={key,topic,binding,callbacks:new Set(),seen:new Map(),active:true,controller:new AbortController(),idempotencyKey:crypto.randomUUID(),subscription:null,failures:0,busy:false,timer:null};this.entries.set(key,entry);}
        entry.callbacks.add(callback);this.schedule(entry,0);let subscribed=true;
        return()=>{if(!subscribed)return;subscribed=false;entry.callbacks.delete(callback);if(!entry.callbacks.size)this.close(entry);};
    }
    schedule(entry,delay){
        if(!this.current(entry)||entry.busy)return;
        if(entry.timer!==null)this.clearTimer(entry.timer);
        entry.timer=this.setTimer(()=>{entry.timer=null;this.step(entry);},delay);
    }
    async call(entry,kind,extra={},signal=entry.controller.signal){
        const message={protocol:1,kind:kind+'_request',request_id:crypto.randomUUID(),...extra};
        if(kind!=='subscribe')message.subscription_id=entry.subscription.subscription_id;
        const started=this.monotonic();const value=await this.request(message,entry.binding,{signal});
        if(this.monotonic()-started>30000)throw problem('DEADLINE_EXCEEDED');
        if(!validEventResult(value)||value.kind!==kind+'_result'||kind!=='subscribe'&&value.subscription_id!==message.subscription_id)throw problem('INTERNAL_ERROR');
        return value;
    }
    async step(entry){
        if(!this.current(entry)||entry.busy)return;entry.busy=true;let delay=2000;
        const controller=entry.controller;const current=()=>this.current(entry)&&entry.controller===controller;
        try{
            if(!entry.subscription){
                const subscription=await this.call(entry,'subscribe',{topic:entry.topic,idempotency_key:entry.idempotencyKey});
                if(subscription.topic!==entry.topic)throw problem('INTERNAL_ERROR');
                entry.subscription=subscription;
                if(!current()){if(!this.active||!entry.active)this.cleanupSubscription(entry);return;}
            }
            const authorizedAt=this.monotonic();const batch=await this.call(entry,'poll',{limit:50});
            if(!current())return;
            delay=batch.has_more?1000:batch.next_poll_ms;
            if(batch.dead_letter_count&&batch.dead_letter_count!==entry.deadLetters){entry.deadLetters=batch.dead_letter_count;this.onDeadLetter({subscription_id:entry.subscription.subscription_id,count:batch.dead_letter_count,retry:()=>this.retryDeadLetters(entry)});}
            const receipts=[];
            for(const delivery of batch.deliveries){
                if(!current())return;
                const event=delivery.event;
                if(event.topic!==entry.topic||event.site_id!==this.context.site_id||event.workspace_id!==this.context.workspace_id)throw problem('FORBIDDEN');
                if(Date.parse(delivery.lease_expires_at)<=this.clock())continue;
                let completed=entry.seen.get(event.id);
                if(!completed){if(entry.seen.size>=10000)throw problem('RATE_LIMITED');completed={done:false,callbacks:new Set()};entry.seen.set(event.id,completed);}
                if(!completed.done){
                    const callbacks=[...entry.callbacks];let failed=false;
                    for(const callback of callbacks){
                        if(!current())return;
                        if(this.monotonic()-authorizedAt>30000){delay=1000;return;}
                        if(!entry.callbacks.has(callback)||completed.callbacks.has(callback))continue;
                        try{await callback(freeze({id:event.id,topic:event.topic,data:event.payload,generation:this.generation}));completed.callbacks.add(callback);}
                        catch{failed=true;if(current())this.onError(problem('INTERNAL_ERROR'));}
                    }
                    if(!current())return;
                    completed.done=!failed;
                }
                if(completed.done)receipts.push({delivery_id:delivery.id,receipt:delivery.receipt,generation:delivery.generation});
            }
            if(receipts.length&&current())await this.call(entry,'ack',{receipts});
            entry.failures=0;
        }catch(error){
            if(!current())return;
            if(error.code==='CONFLICT'&&entry.subscription){
                try{
                    const status=await this.call(entry,'status');
                    if(!current())return;
                    if(status.state==='expired'){entry.subscription=null;entry.idempotencyKey=crypto.randomUUID();entry.failures=0;return;}
                    // An expired ACK can safely redeliver; seen callbacks stay
                    // deduplicated. A live subscription must still be checked.
                    if(status.state==='active'){delay=2000;return;}
                }catch{/* A current-authority failure ends this stream below. */}
            }
            if(['DEADLINE_EXCEEDED','DEPENDENCY_UNAVAILABLE'].includes(error.code)&&++entry.failures<=5)delay=Math.min(10000,1000*2**(entry.failures-1));
            else{this.onError(problem(error.code||'INTERNAL_ERROR'));this.close(entry);}
        }finally{entry.busy=false;if(this.current(entry))this.schedule(entry,delay);}
    }
    async retryDeadLetters(entry){
        if(!this.current(entry))return;
        try{
            const status=await this.call(entry,'status');if(!this.current(entry))return;
            const event_ids=status.deliveries.filter(d=>d.state==='dead_letter').map(d=>d.event_id);
            if(event_ids.length){await this.call(entry,'replay',{event_ids});entry.deadLetters=0;this.schedule(entry,0);}
        }catch(error){if(this.current(entry))this.onError(problem(error.code||'INTERNAL_ERROR'));}
    }
    resumeTimers(){for(const entry of this.entries.values())this.schedule(entry,0);}
    pause(){
        this.paused=true;
        for(const entry of this.entries.values()){entry.controller.abort();if(entry.timer!==null)this.clearTimer(entry.timer);entry.timer=null;}
    }
    resume(){
        if(!this.active)return;
        for(const entry of this.entries.values())if(entry.controller.signal.aborted)entry.controller=new AbortController();
        this.paused=false;this.resumeTimers();
    }
    cleanupSubscription(entry){
        if(!entry.subscription)return;
        const controller=new AbortController();const timer=this.setTimer(()=>controller.abort(),2000);
        this.call(entry,'close',{},controller.signal).catch(()=>{}).finally(()=>this.clearTimer(timer));
    }
    close(entry){
        if(!entry.active)return;entry.active=false;entry.controller.abort();
        if(entry.timer!==null)this.clearTimer(entry.timer);entry.timer=null;
        entry.callbacks.clear();entry.seen.clear();this.entries.delete(entry.key);this.cleanupSubscription(entry);
    }
    dispose(){
        if(!this.active)return;this.active=false;this.unwake();
        for(const entry of [...this.entries.values()])this.close(entry);
        this.entries.clear();
    }
}
