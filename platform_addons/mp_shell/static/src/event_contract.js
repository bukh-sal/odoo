/** Strict result DTO checks for the new event protocol; no UI framework. */
const MAX=Number.MAX_SAFE_INTEGER;
const plain=value=>value!==null&&typeof value==='object'&&!Array.isArray(value)&&[Object.prototype,null].includes(Object.getPrototypeOf(value));
const exact=(value,spec)=>plain(value)&&Object.keys(value).length===Object.keys(spec).length&&Object.entries(spec).every(([key,test])=>Object.hasOwn(value,key)&&test(value[key]));
const integer=(min=0,max=MAX)=>value=>Number.isSafeInteger(value)&&value>=min&&value<=max;
const uuid=value=>typeof value==='string'&&value.length===36&&/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);
const topic=value=>typeof value==='string'&&value.length<=200&&/^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*){2,15}(?![\s\S])/.test(value);
const plugin=value=>typeof value==='string'&&value.length<=180&&/^[a-z][a-z0-9]*(\.[a-z][a-z0-9_]*){2,}(?![\s\S])/.test(value);
const choice=(...values)=>value=>values.includes(value);
const array=(check,min=0,max=50)=>value=>Array.isArray(value)&&value.length>=min&&value.length<=max&&value.every(check);
const unique=value=>new Set(value).size===value.length;
const ids=value=>array(uuid)(value)&&unique(value);
const text=value=>typeof value==='string'&&[...value].every(ch=>ch.length!==1||ch.charCodeAt(0)<0xd800||ch.charCodeAt(0)>0xdfff);
const bytes=value=>new TextEncoder().encode(JSON.stringify(value)).length;
function utc(value){
    if(typeof value!=='string'||value.length>35)return false;
    const found=/^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]{1,6})?Z(?![\s\S])/.exec(value);
    if(!found||Number(found[1])<1)return false;
    const date=new Date(value);return Number.isFinite(+date)&&[date.getUTCFullYear(),date.getUTCMonth()+1,date.getUTCDate(),date.getUTCHours(),date.getUTCMinutes(),date.getUTCSeconds()].every((n,i)=>n===Number(found[i+1]));
}
function budget(value,depth=1){
    if(depth>16)return false;
    if(value===null||typeof value==='boolean')return true;
    if(typeof value==='number')return Number.isFinite(value)&&Math.abs(value)<=MAX;
    if(typeof value==='string')return text(value);
    if(Array.isArray(value))return value.length<=128&&value.every(child=>budget(child,depth+1));
    return plain(value)&&Object.keys(value).length<=128&&Object.entries(value).every(([key,child])=>text(key)&&budget(child,depth+1));
}
function jsonValue(value){
    if(typeof value==='string')return text(value)&&[...value].length<=2048;
    if(Array.isArray(value))return value.length<=32&&value.every(jsonValue);
    if(plain(value))return Object.keys(value).length<=32&&Object.values(value).every(jsonValue);
    return value===null||typeof value==='boolean'||typeof value==='number'&&Number.isFinite(value)&&Math.abs(value)<=MAX;
}
function event(value){
    const valid=exact(value,{id:uuid,topic,schema_version:integer(1,1000),owner_plugin_id:plugin,aggregate_id:uuid,aggregate_sequence:n=>n===null||integer(1)(n),site_id:uuid,workspace_id:uuid,occurred_at:utc,correlation_id:uuid,causation_id:n=>n===null||uuid(n),payload:n=>plain(n)&&jsonValue(n)});
    if(!valid||bytes(value)>16384)return false;
    if(value.topic!=='org.example.notes.changed')return true;
    return value.schema_version===1&&value.owner_plugin_id==='org.example.notes'&&exact(value.payload,{note_id:uuid,revision:integer(1),change:choice('created','updated','deleted')})&&value.aggregate_id===value.payload.note_id&&value.aggregate_sequence===value.payload.revision;
}
const delivery=value=>exact(value,{id:uuid,receipt:uuid,generation:integer(1),attempt:integer(1,5),lease_expires_at:utc,event});
const status=value=>exact(value,{id:uuid,event_id:uuid,state:choice('pending','leased','acknowledged','dead_letter'),attempts:integer(0,5),replays:integer(0,3),error_code:choice(null,'ACK_EXPIRED','CONSUMER_FAILED')});
const bool=value=>typeof value==='boolean';
const base=kind=>({protocol:choice(1),kind:choice(kind),subscription_id:uuid});
const specs={
    subscribe_result:{...base('subscribe_result'),topic,expires_at:utc,replay_window_seconds:choice(604800),ack_lease_seconds:choice(15),max_attempts:choice(5),max_replays:choice(3)},
    poll_result:{...base('poll_result'),deliveries:array(delivery),has_more:bool,dead_letter_count:integer(),next_poll_ms:integer(1000,10000)},
    ack_result:{...base('ack_result'),acknowledged:ids},
    status_result:{...base('status_result'),state:choice('active','closed','expired'),deliveries:array(status),truncated:bool},
    replay_result:{...base('replay_result'),replayed:ids},
    close_result:{...base('close_result'),closed:choice(true)},
};
export function validEventResult(value){
    try{
        if(!plain(value)||!Object.hasOwn(specs,value.kind)||!budget(value)||bytes(value)>65536||!exact(value,specs[value.kind]))return false;
        if(value.kind==='poll_result')return unique(value.deliveries.map(d=>d.id))&&unique(value.deliveries.map(d=>d.event.id));
        return true;
    }catch{return false;}
}
