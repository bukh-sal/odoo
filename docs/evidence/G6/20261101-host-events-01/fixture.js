/* Test-only registry page. No deployed bundle replacement or Canvas changes. */
odoo.define('g6_test.host_event_page',['@web/core/registry','@mp_example_canvas/adapter','@odoo/owl'],function(require){
    'use strict';
    const {registry}=require('@web/core/registry');const {Component}=require('@odoo/owl');
    const report={phase:'registered',checks:[],counts:{callbacks:0,polls:0,wakes:0},notes:[],subscription_ids:[],failures:[],disposals:0,actual_host_facade:true,bus_payload_minimized:true};
    const originalFetch=window.fetch.bind(window);let currentHost,currentContext,activeSubscription,unsub,observer,bus;
    const seen=new Map();let eventFor=new Map();const notes=new Set();let csrf,release,spaces;
    const panel=document.createElement('section');panel.id='g6-event-proof';panel.style.cssText='position:relative;z-index:20;background:white;color:black;border:2px solid #334;padding:12px;margin:12px';
    const output=document.createElement('pre');output.setAttribute('role','status');panel.append(output);
    const persist=async()=>{output.textContent=JSON.stringify(report,null,2);await originalFetch('/__g6_host__/report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(report)});};
    const check=(value,message)=>{if(!value)throw Error(message);};
    const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
    async function until(fn){for(let n=0;n<60;n++){if(await fn())return;await wait(250);}throw Error('Timed out waiting for required host observation');}
    window.fetch=async function(input,options){
        const eventRequest=typeof input==='string'&&input==='/api/v1/events';let message;
        if(eventRequest){message=JSON.parse(options.body);if(message.kind==='poll_request')report.counts.polls++;}
        const response=await originalFetch(input,options);
        if(eventRequest&&response.ok){const value=(await response.clone().json()).data;
            if(message.kind==='subscribe_request'){activeSubscription=value.subscription_id;report.subscription_ids.push(value.subscription_id);}
        }return response;
    };
    async function api(path,body,workspace=currentContext.workspace_id,extra={}){
        const response=await originalFetch(path,{method:body?'POST':'GET',credentials:'same-origin',headers:{'Content-Type':'application/json','X-MP-Workspace':workspace,...(csrf?{'X-CSRFToken':csrf}:{}),...(release?{'X-MP-Client-Release':release}:{}),...extra},...(body?{body:JSON.stringify(body)}:{})});
        const value=await response.json();if(!response.ok)throw Object.assign(Error(value.error?.code||'HTTP_ERROR'),value.error);return value.data;
    }
    async function produce(workspace=spaces.A){
        const context=await api('/api/v1/context?plugin_id=org.example.notes',null,workspace);const binding=context.bindings.find(b=>b.alias==='documents');
        return api('/api/v1/services/org.example.notes.documents/create',{api_version:'1.0',request_id:crypto.randomUUID(),idempotency_key:crypto.randomUUID(),input:{title:'Host event reference '+crypto.randomUUID(),body:'Minimal retained disposable fixture'}},workspace,{'X-MP-Binding':binding.binding_id,'X-MP-Consumer':context.context.installation_id});
    }
    function button(name,action){const control=document.createElement('button');control.textContent=name;control.onclick=async()=>{control.disabled=true;try{await action();report.checks.push(name);}catch(e){report.failures.push(name+': '+e.message);}await persist();};panel.append(control);}
    function callback(message){
        check(Object.isFrozen(message)&&Object.isFrozen(message.data),'Mutable host event');check(message.generation===currentContext.generation,'Wrong host mount generation');
        check(Object.keys(message.data).sort().join(',')==='change,note_id,revision','Event payload is not minimized');
        report.counts.callbacks++;seen.set(message.data.note_id,(seen.get(message.data.note_id)||0)+1);eventFor.set(message.data.note_id,message.id);
        if(notes.has(message.data.note_id))output.textContent=JSON.stringify(report,null,2);
    }
    button('Emit through committed Notes API',async()=>{
        await until(()=>activeSubscription);const value=await produce();notes.add(value.id);report.notes.push(value.id);await until(()=>seen.has(value.id));check(seen.get(value.id)===1,'Duplicate first callback');
        await until(()=>report.counts.wakes>0);check(report.bus_payload_minimized,'Bus exposed domain payload');report.phase='committed_host_delivery_and_native_bus';
    });
    button('Replay without duplicate callback',async()=>{
        check(report.notes.length>0,'Emit first');const note=report.notes[0],event_id=eventFor.get(note);check(event_id,'Missing retained event');
        const status=()=>api('/api/v1/events',{protocol:1,kind:'status_request',request_id:crypto.randomUUID(),subscription_id:activeSubscription});
        await until(async()=>(await status()).deliveries.some(d=>d.event_id===event_id&&d.state==='acknowledged'));
        await api('/api/v1/events',{protocol:1,kind:'replay_request',request_id:crypto.randomUUID(),subscription_id:activeSubscription,event_ids:[event_id]});
        await until(async()=>(await status()).deliveries.some(d=>d.event_id===event_id&&d.state==='acknowledged'&&d.replays===1));
        check(seen.get(note)===1,'Replay duplicated actual host callback');report.phase='actual_host_duplicate_deduplicated';
    });
    button('Dispose and show native Notes',async()=>{
        const subscription=activeSubscription;check(subscription,'Subscribe first');await currentHost.navigate({pluginId:'org.example.notes',pageId:'home'});
        await until(()=>report.disposals>0);await wait(2500);const before=report.counts.polls;
        const value=await produce();notes.add(value.id);report.notes.push(value.id);await wait(3000);
        check(!seen.has(value.id),'Disposed page received event');check(report.counts.polls===before,'Disposed client still polls');
        const status=await api('/api/v1/events',{protocol:1,kind:'status_request',request_id:crypto.randomUUID(),subscription_id:subscription});check(status.state==='closed','Disposed subscription not closed');
        report.native_Odoo_default=!!document.querySelector('.o_list_view');check(report.native_Odoo_default,'Expected native Odoo list');report.phase='actual_host_disposed_native_notes';
    });
    button('Check workspace B viewer limits',async()=>{
        check(spaces,'Context first');try{await produce(spaces.B);throw Error('Viewer created Note');}catch(e){check(e.code==='FORBIDDEN','Expected current viewer denial');}
        const value=await api('/api/v1/context?plugin_id=org.example.notes',null,spaces.B);check(value.context.workspace_id===spaces.B&&!value.context.capabilities.includes('org.example.notes:notes.write'),'Viewer context mismatch');report.phase='host_browser_checks_complete';
    });
    registry.category('mp.pages').add('org.example.canvas:board',{
        async mount({element,host,signal}){
            currentHost=host;currentContext=host.context();report.context={workspace_id:currentContext.workspace_id,plugin_id:currentContext.plugin_id,generation:currentContext.generation};
            check(currentContext.plugin_id==='org.example.canvas','Expected existing custom-page seam');
            spaces=await (await originalFetch('/__g6_host__/config')).json();const session=await api('/api/v1/session');csrf=session.csrf_token;release=(await api('/api/v1/client-release')).token;
            bus=Component.env.services.bus_service;check(bus,'Actual Odoo bus service unavailable');
            observer=payload=>{report.counts.wakes++;if(JSON.stringify(payload)!=='{"available":true}')report.bus_payload_minimized=false;};bus.subscribe('mp_domain_events',observer);
            document.body.append(panel);element.textContent='Minimal test-only page exercises the deployed host facade. Canvas installed code is unchanged.';
            unsub=host.events.subscribe('org.example.notes.changed',callback);report.phase='actual_host_subscribed';await persist();
            return{dispose(){unsub?.();bus.unsubscribe('mp_domain_events',observer);report.disposals++;persist();},updateRoute(){},isDirty(){return false;}};
        }
    },{force:true});
    return {testOnly:true};
});
