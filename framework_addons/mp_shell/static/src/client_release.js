/** A document's bootstrap pin is immutable. Native UI services own refresh UI. */
const keys=['generation','inventory_digest','protocol','release_digest','site_id','token'];
const digest=value=>typeof value==='string'&&/^sha256:[0-9a-f]{64}$/.test(value)&&value.length===71;
export function validRelease(value){
    return value&&Object.keys(value).sort().join(',')===keys.join(',')&&value.protocol===1&&
        Number.isSafeInteger(value.generation)&&value.generation>0&&
        typeof value.site_id==='string'&&/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value.site_id)&&value.site_id.length===36&&
        digest(value.release_digest)&&digest(value.inventory_digest)&&digest(value.token);
}
export function releaseError(outcome='not_started'){
    return Object.assign(new Error('The platform has changed. Refresh to continue.'),{
        code:'CONFLICT',details:{field:'client_release',outcome},retryable:false});
}
export function isReleaseError(error){
    return error?.code==='CONFLICT'&&error?.details?.field==='client_release'||
        error?.exceptionName?.endsWith('.ClientReleaseMismatch');
}
export function recoveryPath(path){return ['/api/v1/session','/api/v1/workspaces','/api/v1/client-release'].includes(path.split('?')[0])||path.startsWith('/web/session/');}
export class ClientReleaseFence{
    constructor(document){this.document=Object.freeze({...document});this.blocked=false;this.onChange=null;}
    headers(){return validRelease(this.document)?{'X-MP-Client-Release':this.document.token}:{};}
    assert(path,outcome='not_started'){
        if(recoveryPath(path))return;
        if(!validRelease(this.document))this.block();
        if(this.blocked)throw releaseError(outcome);
    }
    observe(document){
        if(!validRelease(this.document)||!validRelease(document)||keys.some(key=>document[key]!==this.document[key]))this.block();
        return !this.blocked;
    }
    block(){
        if(this.blocked)return;
        this.blocked=true;
        this.retirement=Promise.resolve().then(()=>this.onChange?.());
        // A disposal error cannot clear the fence or create an unhandled loop.
        this.retirement.catch(()=>{});
    }
}
