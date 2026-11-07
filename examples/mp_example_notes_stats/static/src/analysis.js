/** Minimal trusted contribution; Odoo owns presentation and mount cleanup. */
import { registry } from '@web/core/registry';

const messages={
    en:{queued:'Analysis is queued for the saved note.',busy:'Analysis is already being checked.',
        stale:'The saved note changed. Reload before analyzing it.',unavailable:'Analysis is unavailable. Notes are still available.',
        unknown:'The analysis outcome is uncertain and needs operator reconciliation. It will not be retried automatically.',
        held:'Analysis is on hold. Check again after it is resumed.',pending:'Analysis is still pending. Open analysis again to check.',
        replaced:'A newer analysis request exists. Open analysis again to check.',cancelled:'Analysis was cancelled.',
        denied:'Analysis access changed. Refresh this note.',result:(revision,s)=>`Saved revision ${revision}: characters ${s.characters}, words ${s.words}, lines ${s.lines}.`},
    ar:{queued:'أُضيف تحليل الملاحظة المحفوظة إلى قائمة الانتظار.',busy:'يجري التحقق من التحليل بالفعل.',
        stale:'تغيّرت الملاحظة المحفوظة. أعد تحميلها قبل تحليلها.',unavailable:'التحليل غير متاح. ما زال بإمكانك استخدام الملاحظات.',
        unknown:'نتيجة التحليل غير مؤكدة وتحتاج إلى مراجعة المشغّل. لن يُعاد تلقائياً.',
        held:'التحليل معلّق. تحقّق مجدداً بعد استئنافه.',pending:'ما زال التحليل قيد الانتظار. افتح التحليل مجدداً للتحقق.',
        replaced:'يوجد طلب تحليل أحدث. افتح التحليل مجدداً للتحقق.',cancelled:'أُلغي التحليل.',
        denied:'تغيّر إذن التحليل. أعد تحميل الملاحظة.',result:(revision,s)=>`النسخة المحفوظة ${revision}: ${s.characters} حرفاً، ${s.words} كلمة، ${s.lines} سطراً.`},
};

function pause(signal){
    return new Promise(resolve=>{
        const done=()=>{clearTimeout(timer);signal.removeEventListener('abort',done);resolve();};
        const timer=setTimeout(done,1000);signal.addEventListener('abort',done,{once:true});
        if(signal.aborted)done();
    });
}

// Timing is injected only for source tests; catalog input never configures it.
export function createAnalysisAction({wait=pause,now=()=>performance.now(),timeout=200000}={}){
    const active=new WeakMap();
    return async function analyze({element,host,context,signal}){
        if(signal.aborted)return null;
        const text=messages[host.locale.current().language==='ar'?'ar':'en'];
        const notify=(key,severity='warning')=>{if(!signal.aborted)host.notifications.show({message:text[key],severity});};
        if(active.get(element)&&!active.get(element).aborted){notify('busy','info');return null;}
        active.set(element,signal);
        const call=(alias,method,input,options={})=>host.services.call(alias,method,input,{...options,signal});
        const currentNote=async()=>{
            const note=await call('documents','get',{note_id:context.note_id});
            if(signal.aborted)return false;
            if(note.revision!==context.expected_revision){notify('stale');return false;}
            return true;
        };
        try{
            if(!await currentNote())return null;
            let {job}=await call('jobs','status',{note_id:context.note_id});
            if(signal.aborted)return null;
            if(job?.state==='outcome_unknown'){notify('unknown');return null;}
            if(job?.state==='held'){notify('held');return null;}
            if(!job||['dead_letter','cancelled'].includes(job.state)||(job.state==='completed'&&job.result?.revision!==context.expected_revision)){
                ({job}=await call('jobs','analyze',{note_id:context.note_id,expected_revision:context.expected_revision},{idempotencyKey:'analysis-'+crypto.randomUUID()}));
            }
            if(signal.aborted)return null;
            const jobID=job?.id;const deadline=now()+timeout;
            if(job?.state!=='completed')notify('queued','info');
            while(!signal.aborted){
                if(job?.id&&job.id!==jobID){notify('replaced');break;}
                if(job?.state==='completed'){
                    if(!await currentNote())break;
                    if(signal.aborted)break;
                    if(job.result?.note_id!==context.note_id||job.result?.revision!==context.expected_revision){notify('stale');break;}
                    host.notifications.show({message:text.result(context.expected_revision,job.result.statistics),severity:'success'});break;
                }
                if(job?.state==='outcome_unknown'){notify('unknown');break;}
                if(job?.state==='held'){notify('held');break;}
                if(job?.state==='cancelled'){notify('cancelled');break;}
                if(job?.state==='dead_letter'){
                    notify(job.error_code==='CONFLICT'?'stale':['FORBIDDEN','UNAUTHENTICATED'].includes(job.error_code)?'denied':'unavailable');break;
                }
                if(now()>=deadline){notify('pending');break;}
                await wait(signal);if(signal.aborted)break;
                ({job}=await call('jobs','status',{note_id:context.note_id}));
            }
        }catch(error){
            if(!signal.aborted&&error.name!=='AbortError')notify(error.code==='CONFLICT'?'stale':['FORBIDDEN','UNAUTHENTICATED'].includes(error.code)?'denied':'unavailable');
        }finally{if(active.get(element)===signal)active.delete(element);}
        // Analysis never saves a Note. A truthy result would clear its draft.
        return null;
    };
}

registry.category('mp.slot_actions').add('org.example.notes_stats:action:analyze',createAnalysisAction());
