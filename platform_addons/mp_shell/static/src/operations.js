/** Application nominations and observed progress; local OS approval is separate. */
import { Component, xml, useState, onMounted, onWillDestroy } from '@odoo/owl';

export class OperationsPanel extends Component {
    static props={api:Function,onSession:Function,onDenied:Function,initialWorkspace:{type:String,optional:true}};
    static template=xml`<section class="mp_operations" aria-label="Plugin operations">
        <p>Prepare a plan, request the operation, then use local operator approval and apply.</p>
        <div t-if="state.error" class="mp_notice" role="alert"><strong t-esc="state.error"/><button t-on-click="load">Refresh</button></div>
        <p t-if="state.loading" role="status">Loading operator metadata…</p>
        <form t-if="state.context" t-on-submit.prevent="prepare" class="mp_operation_form">
            <label for="mp_operation_artifact">Plugin and version</label>
            <select id="mp_operation_artifact" t-model="state.digest" required="required" t-on-change="clearPlan">
                <option value="">Choose a plugin</option><option t-foreach="state.catalog" t-as="item" t-key="item.artifact_digest" t-att-value="item.artifact_digest"><t t-esc="item.name"/> · <t t-esc="item.version"/></option>
            </select>
            <label for="mp_operation_type">Operation</label><select id="mp_operation_type" t-model="state.action" t-on-change="clearPlan">
                <option value="install">Install</option><option value="upgrade">Upgrade</option><option value="suspend">Feature suspension</option><option value="enable">Enable feature</option><option value="uninstall">Native uninstall</option><option value="unregister">Unregister service</option><option value="remove">Remove unused artifact</option>
            </select>
            <label t-if="needsWorkspace" for="mp_operation_workspace">Workspace</label>
            <select t-if="needsWorkspace" id="mp_operation_workspace" t-model="state.workspace" required="required" t-on-change="clearPlan"><option value="">Choose a workspace</option><option t-foreach="state.context.workspaces" t-as="space" t-key="space.workspace_id" t-att-value="space.workspace_id" t-esc="space.name"/></select>
            <p t-else="">This operation affects the site. The plan lists every affected workspace.</p>
            <label class="mp_check"><input type="checkbox" t-model="state.cascade" t-on-change="clearPlan"/> Include dependent changes in the proposed plan</label>
            <button type="submit" t-att-disabled="state.busy || !selected || (needsWorkspace &amp;&amp; !state.workspace)">Prepare plan</button>
        </form>
        <section t-if="selected" class="mp_notice" aria-label="Package trust">
            <h2 t-esc="selected.name"/><p t-esc="selected.description"/><p>Publisher: <t t-esc="selected.publisher"/> · License: <t t-esc="selected.license"/></p>
            <p>Trust: <t t-esc="selected.trust_model"/> · Signature verified: no</p><code t-esc="selected.artifact_digest"/>
            <p t-foreach="selected.warnings" t-as="warning" t-key="warning" class="mp_notice" role="status" t-esc="warning"/>
        </section>
        <section t-if="state.prepared" class="mp_notice" aria-label="Proposed operation">
            <h2>Review proposed changes</h2><p t-if="state.prepared.stale">Catalog observation is old. The local operator revalidates it before approval.</p>
            <p t-if="state.prepared.native_trusted_code">Native code shares the host application's trust.</p>
            <p t-if="state.prepared.plan.operation_type==='suspend'">Feature suspension retains native registration and data. Imported code and model overrides remain loaded.</p>
            <p t-if="state.prepared.plan.destructive" role="alert">This operation can delete native data and schema.</p>
            <p t-if="state.prepared.plan.backup.required">A coordinated database and filestore checkpoint is required.</p>
            <p t-if="state.prepared.restart_required">Workers will restart on the selected release.</p>
            <table><thead><tr><th scope="col">Plugin</th><th scope="col">Workspace</th><th scope="col">Action</th></tr></thead><tbody><tr t-foreach="state.prepared.targets" t-as="target" t-key="target.installation_id+target.workspace_id"><td t-esc="target.plugin_id"/><td t-esc="workspaceName(target.workspace_id)"/><td t-esc="target.action"/></tr></tbody></table>
            <p t-foreach="state.prepared.known_unknowns" t-as="item" t-key="item" t-esc="item"/>
            <button t-on-click="download" t-att-disabled="state.busy">Download full plan and bindings</button>
            <button t-on-click="submit" t-att-disabled="state.busy || state.submitted">Request operation</button>
        </section>
        <section t-if="state.status" class="mp_notice" aria-label="Operation progress">
            <h2>Operation progress</h2><p role="status"><strong t-esc="state.status.state"/> · <t t-esc="state.status.phase"/></p>
            <p t-if="state.status.stale">Progress observation is stale. Refresh or inspect the local operator journal.</p>
            <p>Operation ID: <code t-esc="state.status.operation_id"/></p><p>Exact plan hash: <code t-esc="state.status.plan_hash"/></p>
            <p t-if="state.status.approval_expires_at">Start approval expires: <time t-att-datetime="state.status.approval_expires_at" t-esc="state.status.approval_expires_at"/></p>
            <p t-if="state.status.state==='awaiting_operator_approval'">Next: local operator approval for this exact hash, followed by local apply.</p>
            <pre t-if="state.status.state==='awaiting_operator_approval'" t-esc="approvalCommand"/>
            <ol><li t-foreach="state.status.history" t-as="event" t-key="event.sequence"><time t-att-datetime="event.utc" t-esc="event.utc"/> · <t t-esc="event.code"/></li></ol>
            <table t-if="state.status.dimensions.length"><thead><tr><th>Plugin</th><th>Artifact</th><th>Release</th><th>Database</th><th>Feature</th><th>Service runtime</th></tr></thead><tbody><tr t-foreach="state.status.dimensions" t-as="item" t-key="item.installation_id+item.workspace_id"><td t-esc="item.plugin_id"/><td t-esc="item.artifact_state"/><td t-esc="item.release_state"/><td t-esc="item.database_state"/><td t-esc="item.feature_state||'Not enabled'"/><td t-esc="item.service_state||'Not applicable'"/></tr></tbody></table>
        </section>
    </section>`;

    setup(){
        this.state=useState({context:null,catalog:[],digest:'',action:'suspend',workspace:this.props.initialWorkspace||'',cascade:false,prepared:null,status:null,error:'',loading:true,busy:false,submitted:false});
        this.controller=new AbortController();this.active=true;this.sequence=0;this.checking=false;
        onMounted(()=>{this.timer=setInterval(()=>this.poll(),5000);this.load();});
        onWillDestroy(()=>{this.active=false;this.sequence++;clearInterval(this.timer);this.controller.abort();});
    }
    get selected(){return this.state.catalog.find(item=>item.artifact_digest===this.state.digest);}
    get needsWorkspace(){return ['install','upgrade','suspend','enable'].includes(this.state.action);}
    get approvalCommand(){const s=this.state.status;return s?'modular operations approve '+s.operation_id+' --plan-hash '+s.plan_hash:'';}
    workspaceName(id){return this.state.context?.workspaces.find(item=>item.workspace_id===id)?.name||id;}
    clearPlan(){this.sequence++;this.state.prepared=null;this.state.status=null;this.state.submitted=false;this.requestId=null;}
    async api(path,body=null){
        const controller=new AbortController();const abort=()=>controller.abort();this.controller.signal.addEventListener('abort',abort,{once:true});
        const timer=setTimeout(abort,10000);
        try{return await this.props.api(path,body,{signal:controller.signal});}
        finally{clearTimeout(timer);this.controller.signal.removeEventListener('abort',abort);}
    }
    denied(){this.clearPlan();this.state.context=null;this.state.catalog=[];this.props.onDenied();}
    failure(error){
        if(!this.active)return;
        if(this.state.status)this.state.status.stale=true;
        if(['UNAUTHENTICATED','FORBIDDEN','NOT_FOUND'].includes(error.code))this.denied();
        this.state.error=error.name==='AbortError'?'Request timed out. Check progress before retrying a submitted request.':error.message||'Operation information is unavailable';
    }
    async authority(){
        const session=await this.api('/api/v1/session');if(!this.active)return false;
        if(this.principal&&session.principal_id!==this.principal)this.clearPlan();
        this.principal=session.principal_id;this.props.onSession(session);
        const context=await this.api('/api/v1/operations/context');
        if(!this.active)return false;
        if(!context.can_request){this.denied();this.state.error='Application operator access is required';return false;}
        this.state.context=context;return true;
    }
    async load(){
        this.state.loading=true;this.state.error='';
        try{if(!await this.authority())return;const catalog=await this.api('/api/v1/operations/catalog');if(this.active)this.state.catalog=catalog.items;}
        catch(error){this.failure(error);}finally{if(this.active)this.state.loading=false;}
    }
    async prepare(){
        const item=this.selected;if(!item||this.state.busy)return;
        this.clearPlan();const sequence=this.sequence;this.state.busy=true;this.state.error='';
        const body={schema_version:1,operation:'prepare',operation_type:this.state.action,plugin_id:item.plugin_id,site_id:this.state.context.site_id,
            workspace_ids:this.needsWorkspace?[this.state.workspace]:[],cascade:this.state.cascade};
        if(['install','upgrade'].includes(this.state.action)){body.artifact_version=item.version;body.artifact_digest=item.artifact_digest;}
        if(this.state.action==='remove')body.artifact_digest=item.artifact_digest;
        try{const value=await this.api('/api/v1/operations/prepare',body);if(this.active&&sequence===this.sequence){this.state.prepared=value;this.requestId=crypto.randomUUID();}}
        catch(error){if(sequence===this.sequence)this.failure(error);}finally{if(this.active)this.state.busy=false;}
    }
    async submit(){
        if(this.state.busy||!this.state.prepared)return;this.state.busy=true;this.state.error='';const prepared=this.state.prepared,sequence=this.sequence;
        try{const status=await this.api('/api/v1/operations/request',{schema_version:1,operation:'request',operation_id:prepared.operation_id,plan_hash:prepared.plan_hash,request_id:this.requestId});
            if(this.active&&sequence===this.sequence){this.state.status=status;this.state.submitted=true;}}
        catch(error){if(sequence===this.sequence)this.failure(error);}finally{if(this.active)this.state.busy=false;}
    }
    async poll(){
        if(!this.active||document.hidden||this.checking)return;this.checking=true;
        try{if(!await this.authority())return;const prepared=this.state.prepared,sequence=this.sequence;if(!prepared)return;
            const status=await this.api('/api/v1/operations/status/'+prepared.operation_id);
            if(this.active&&sequence===this.sequence){this.state.status=status;if(status.source==='operator_journal_mirror'||status.history.some(item=>item.code==='requested'))this.state.submitted=true;}}
        catch(error){this.failure(error);}finally{this.checking=false;}
    }
    async download(){
        if(!this.state.prepared)return;const prepared=this.state.prepared,sequence=this.sequence;
        try{const bundle=await this.api('/api/v1/operations/bundle/'+prepared.operation_id);if(!this.active||sequence!==this.sequence)return;
            const url=URL.createObjectURL(new Blob([JSON.stringify(bundle,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download='operation-'+prepared.operation_id+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),0);
        }catch(error){this.failure(error);}
    }
}
