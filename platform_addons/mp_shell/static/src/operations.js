/** Application nominations and observed progress; local OS approval is separate. */
import { Component, xml, useState, onMounted, onWillDestroy } from '@odoo/owl';

export class OperationsPanel extends Component {
    static props={api:Function,onSession:Function,onDenied:Function,initialWorkspace:{type:String,optional:true}};
    static template=xml`<section class="mp_operations" aria-label="Plugin operations">
        <p>Prepare a plan, request the operation, then use local operator approval and apply.</p>
        <p>New code requires a local operator to stage the release first. Installation from the current image and native uninstall still require exact local approval and coordinated maintenance. Uploading or selecting an artifact does not execute it.</p>
        <section t-if="state.context" class="mp_notice" aria-label="Upload validation">
            <h2>Validate a plugin archive</h2>
            <p>Validation uses a temporary private copy. It does not install code or add a package to the independent operator catalog.</p>
            <label for="mp_upload_file">Plugin archive (.mplug, maximum 100 MiB)</label>
            <input id="mp_upload_file" type="file" accept=".mplug" t-on-change="selectUpload" t-att-disabled="state.uploadBusy"/>
            <button t-on-click="upload" t-att-disabled="!state.uploadName || state.uploadBusy"><t t-esc="state.uploadBusy?'Validating…':'Validate archive'"/></button>
            <p t-if="state.uploadName" t-esc="state.uploadName"/>
            <div t-if="state.uploadResult" role="status">
                <p>Validation result: <strong t-esc="state.uploadResult.result"/></p><code t-esc="state.uploadResult.artifact_digest"/>
                <p t-if="state.uploadResult.result==='verified'">Archive, inventory and extracted bytes verified against the published curated policy. Independent local revalidation and approval are still required.</p>
                <p t-elif="state.uploadResult.result==='not_curated'">This digest is absent from the published curated catalog. Archive contents have not been validated. A local operator must review and configure trust separately.</p>
                <p t-else="">Validation rejected the archive or its byte identity. Nothing was installed or retained.</p>
                <p>Retain your original file for the local operator. Package builds and runtime selection happen separately, outside this web request.</p>
                <pre t-esc="uploadCommand"/>
            </div>
        </section>
        <section t-if="state.context" class="mp_notice" aria-label="Installed plugins">
            <h2>Installed plugins</h2><p>Health is reported separately from installation and workspace availability. Feature suspension does not unload native Python overrides.</p>
            <p t-if="state.inspectionStale">Published metadata is stale. Refresh it through the local operator before planning changes.</p>
            <table><thead><tr><th>Plugin</th><th>Version / trust</th><th>Database</th><th>Health</th><th>Dependencies</th><th>Workspace availability</th></tr></thead>
                <tbody><tr t-foreach="state.installed" t-as="item" t-key="item.installation_id">
                    <td><button t-if="item.artifact" t-on-click="()=>this.showDetails(item.artifact_digest)" t-esc="item.artifact.name"/><span t-else="" t-esc="item.plugin_id"/></td>
                    <td><t t-esc="item.version"/><p t-esc="item.artifact?.trust_model||'Not in the current curated catalog'"/></td>
                    <td t-esc="item.database_state"/><td><t t-esc="item.health.state"/><p t-esc="item.health.reason"/></td>
                    <td><t t-esc="item.dependencies.state"/><p t-foreach="item.dependencies.issues" t-as="issue" t-key="issue" t-esc="issue"/></td>
                    <td><p t-foreach="item.features" t-as="feature" t-key="feature.workspace_id"><t t-esc="workspaceName(feature.workspace_id)"/>: <t t-esc="feature.availability"/></p></td>
                </tr></tbody>
            </table>
            <p t-if="!state.installed.length &amp;&amp; !state.loading">No plugin installation metadata on this page.</p>
            <button t-if="state.installedOffset" t-on-click="()=>this.loadInstalled(Math.max(0,state.installedOffset-20))">Previous installations</button>
            <button t-if="state.installedNext!==null" t-on-click="()=>this.loadInstalled(state.installedNext)">Next installations</button>
            <button t-on-click="load">Refresh metadata</button>
        </section>
        <div t-if="state.error" class="mp_notice" role="alert"><strong t-esc="state.error"/><button t-on-click="load">Refresh</button></div>
        <p t-if="state.loading" role="status">Loading operator metadata…</p>
        <form t-if="state.context" t-on-submit.prevent="prepare" class="mp_operation_form">
            <label for="mp_operation_artifact">Plugin and version</label>
            <select id="mp_operation_artifact" t-model="state.digest" required="required" t-on-change="clearPlan">
                <option value="">Choose a plugin</option><option t-foreach="state.catalog" t-as="item" t-key="item.artifact_digest" t-att-value="item.artifact_digest"><t t-esc="item.name"/> · <t t-esc="item.version"/></option>
            </select>
            <button t-if="state.catalogNext!==null" type="button" t-on-click="loadMoreCatalog" t-att-disabled="state.catalogBusy">Load more catalog versions</button>
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
            <button t-on-click="()=>this.showDetails(selected.artifact_digest)">View package details</button>
        </section>
        <section t-if="state.details" class="mp_notice" aria-label="Plugin details">
            <h2><t t-esc="state.details.artifact.name"/> package details</h2>
            <p><t t-esc="state.details.artifact.plugin_id"/> · <t t-esc="state.details.artifact.version"/> · <t t-esc="state.details.artifact.publisher"/> · <t t-esc="state.details.artifact.license"/></p>
            <p t-esc="state.details.artifact.description"/><code t-esc="state.details.artifact.artifact_digest"/>
            <p t-if="state.details.native_trusted_code">Native Python and same-origin plugin JavaScript are fully trusted code. Declared permissions govern supported APIs; they do not sandbox arbitrary native code.</p>
            <p>Trust: <t t-esc="state.details.artifact.trust_model"/>. Signature and publisher identity verified: no.</p>
            <p t-if="state.details.stale">This published package observation is stale.</p>
            <h3>Declared permissions</h3><p t-foreach="permissionDefinitions" t-as="entry" t-key="entry[0]"><code t-esc="entry[0]"/>: <t t-esc="entry[1]"/></p>
            <p t-foreach="state.details.manifest.permissions.requests" t-as="entry" t-key="entry.capability+entry.scope"><code t-esc="entry.capability"/> (<t t-esc="entry.scope"/>): <t t-esc="entry.reason"/></p>
            <h3>Services and dependencies</h3><p t-foreach="state.details.manifest.services.provides" t-as="service" t-key="service.id+service.api_version">Provides <t t-esc="service.id"/> <t t-esc="service.api_version"/></p>
            <p t-foreach="state.details.manifest.services.requires" t-as="service" t-key="service.alias">Requires <t t-esc="service.alias"/>: <t t-esc="service.id"/> <t t-esc="service.version"/> (<t t-esc="service.optional?'optional':'required'"/>)</p>
            <p t-foreach="pluginDependencies" t-as="entry" t-key="entry[0]"><t t-esc="entry[0]"/> <t t-esc="entry[1]"/></p>
            <p>Python requirements: <t t-esc="(state.details.manifest.dependencies.python||[]).join(', ')||'None'"/></p>
            <h3>Native extension targets and data impact</h3><p>Models: <t t-esc="state.details.manifest.data.models.join(', ')||'None'"/></p><p>Extension targets: <t t-esc="state.details.manifest.data.extension_targets.join(', ')||'None'"/></p>
            <p t-foreach="state.details.manifest.data.contributions||[]" t-as="entry" t-key="entry.id"><t t-esc="entry.kind"/> <code t-esc="entry.id"/> → <t t-esc="entry.target"/>; deletion policy: <t t-esc="entry.delete_policy"/></p>
            <p>Data effects are package declarations. Arbitrary trusted hooks may have additional effects; review the exact operation plan and recovery requirements.</p>
            <h3>Provenance</h3><p>Builder claim: <t t-esc="state.details.provenance.builder"/>; source files: <t t-esc="state.details.provenance.source_files_count"/>; upstream claim: <t t-esc="state.details.provenance.upstream_commit||'Not declared'"/></p>
            <p>Provenance digest: <code t-esc="state.details.provenance.provenance_digest"/></p><p>Source inventory digest: <code t-esc="state.details.provenance.source_inventory_digest"/></p>
            <button t-on-click="closeDetails">Close details</button>
        </section>
        <section t-if="state.prepared" class="mp_notice" aria-label="Proposed operation">
            <h2>Review proposed changes</h2><p t-if="state.prepared.stale">Catalog observation is old. The local operator revalidates it before approval.</p>
            <p t-if="state.prepared.native_trusted_code">Native code shares the host application's trust.</p>
            <p t-if="state.prepared.plan.operation_type==='suspend'">Feature suspension retains native registration and data. Imported code and model overrides remain loaded.</p>
            <p t-if="state.prepared.plan.operation_type==='remove'">This removes the selected package from the new runtime. Native uninstall must already be complete. Retained installation history, catalog archives, old images, checkpoints and old assets are preserved; workers restart.</p>
            <p t-if="state.prepared.plan.destructive" role="alert">This operation can delete native data and schema.</p>
            <p t-if="state.prepared.plan.backup.required">A coordinated database and filestore checkpoint is required.</p>
            <p t-if="state.prepared.restart_required">Workers will restart on the selected release.</p>
            <table><thead><tr><th scope="col">Plugin</th><th scope="col">Workspace</th><th scope="col">Action</th></tr></thead><tbody><tr t-foreach="state.prepared.targets" t-as="target" t-key="target.installation_id+target.workspace_id"><td t-esc="target.plugin_id"/><td t-esc="workspaceName(target.workspace_id)"/><td t-esc="target.action"/></tr></tbody></table>
            <table><thead><tr><th scope="col">Artifact</th><th scope="col">Version</th><th scope="col">Action</th><th scope="col">Migration scripts</th></tr></thead><tbody><tr t-foreach="state.prepared.plan.artifacts" t-as="artifact" t-key="artifact.plugin_id+artifact.action"><td t-esc="artifact.plugin_id"/><td t-esc="artifact.version"/><td t-esc="artifact.action"/><td t-esc="artifact.migration_digests.length"/></tr></tbody></table>
            <section t-if="state.featureStates.length" aria-label="Post-install workspace states">
                <h3>Post-install workspace states</h3><p>Native schema is shared by the site. Retained suspended scopes are restored without enabling them or renewing their grants.</p>
                <table><thead><tr><th scope="col">Plugin</th><th scope="col">Workspace</th><th scope="col">Feature after installation</th></tr></thead><tbody>
                    <tr t-foreach="state.featureStates" t-as="scope" t-key="scope.installation_id+scope.workspace_id"><td t-esc="featurePlugin(scope)"/><td t-esc="workspaceName(scope.workspace_id)"/><td t-esc="scope.availability"/></tr>
                </tbody></table>
            </section>
            <section t-if="state.impact" aria-label="Native uninstall effects">
                <h3>Native uninstall effects</h3><p>Database uninstall may delete records and schema. The package remains in this runtime; workers will be replaced. These are known effects only; arbitrary trusted hooks may do more.</p>
                <p>Native dependent closure: <t t-esc="state.impact.impact.native_closure.join(', ')"/>.</p>
                <p t-foreach="state.impact.impact.plugins" t-as="plugin" t-key="plugin.installation_id"><t t-esc="plugin.plugin_id"/>: <t t-esc="workspaceList(plugin.workspace_ids)"/>.</p>
                <details open="open"><summary>Known models and fields</summary>
                    <table><thead><tr><th scope="col">Model</th><th scope="col">Relation</th><th scope="col">Records</th><th scope="col">Mapping</th></tr></thead><tbody><tr t-foreach="state.impact.impact.models" t-as="model" t-key="model.model"><td t-esc="model.model"/><td t-esc="model.relation||'Unknown'"/><td t-esc="model.records===null?'Unknown':model.records"/><td t-esc="model.unknown_reason||model.mapping"/></tr></tbody></table>
                    <table><thead><tr><th scope="col">Field</th><th scope="col">Relation / column</th><th scope="col">Non-null records</th><th scope="col">Mapping</th></tr></thead><tbody><tr t-foreach="state.impact.impact.fields" t-as="field" t-key="field.model+field.field"><td><t t-esc="field.model"/>.<t t-esc="field.field"/></td><td><t t-esc="field.relation||'Unknown'"/> / <t t-esc="field.column||'Unknown'"/></td><td t-esc="field.non_null_records===null?'Unknown':field.non_null_records"/><td t-esc="field.unknown_reason||field.mapping"/></tr></tbody></table>
                </details>
                <details><summary>Constraints and foreign references</summary><p>These describe affected relations; not every listed constraint will be deleted.</p>
                    <p t-foreach="state.impact.impact.constraints" t-as="constraint" t-key="constraint.relation+constraint.name"><code t-esc="constraint.relation"/> / <t t-esc="constraint.name"/>: <t t-esc="constraint.definition"/></p>
                    <p t-foreach="state.impact.impact.foreign_references" t-as="reference" t-key="reference.relation+reference.name"><code t-esc="reference.relation"/> → <code t-esc="reference.referenced_relation"/>: <t t-esc="reference.definition"/></p>
                </details>
                <details><summary>Metadata, assets and durable work</summary>
                    <p t-foreach="state.impact.impact.metadata_records" t-as="record" t-key="record.native_addon+record.model"><t t-esc="record.native_addon"/> / <t t-esc="record.model"/>: <t t-esc="record.records"/> metadata records.</p>
                    <p t-foreach="state.impact.impact.assets" t-as="asset" t-key="asset.native_addon+asset.path"><code t-esc="asset.path"/></p>
                    <p>Durable dispatch: <t t-esc="state.impact.impact.dispatch.state"/>.</p>
                </details>
                <p t-foreach="state.impact.impact.warnings" t-as="warning" t-key="warning" t-esc="warning"/>
                <p>Observation: <time t-att-datetime="state.impact.observed_at" t-esc="state.impact.observed_at"/>. The local operator independently reconstructs these effects before approval and mutation.</p>
            </section>
            <section t-if="state.prepared.plan.permission_changes.length" aria-label="Permission changes">
                <h3>Permission changes</h3><p>These grants govern supported APIs. Native code retains the host application's authority.</p>
                <ul><li t-foreach="state.prepared.plan.permission_changes" t-as="change" t-key="change.plugin_id+change.workspace_id+change.capability"><t t-esc="change.action"/> <code t-esc="change.capability"/> for <t t-esc="change.plugin_id"/> in <t t-esc="workspaceName(change.workspace_id)"/></li></ul>
            </section>
            <p t-foreach="state.prepared.declaration_changes" t-as="change" t-key="change.plugin_id"><t t-esc="change.plugin_id"/> added capabilities: <t t-esc="change.added_capabilities.join(', ')||'None'"/>; added scopes: <t t-esc="change.added_scopes.join(', ')||'None'"/>.</p>
            <p t-foreach="state.prepared.known_unknowns" t-as="item" t-key="item" t-esc="item"/>
            <label t-if="state.prepared.plan.destructive" class="mp_check"><input type="checkbox" t-model="state.destructiveConfirmed"/> I understand this may delete native data and schema. A local operator must approve this exact plan and create a coordinated backup before execution.</label>
            <button t-on-click="download" t-att-disabled="state.busy">Download full plan and bindings</button>
            <button t-on-click="submit" t-att-disabled="state.busy || state.submitted || !requestAllowed">Request operation</button>
        </section>
        <section t-if="state.status" class="mp_notice" aria-label="Operation progress">
            <h2>Operation progress</h2><p role="status"><strong t-esc="state.status.state"/> · <t t-esc="state.status.phase"/></p>
            <p t-if="state.status.stale">Progress observation is stale. Refresh or inspect the local operator journal.</p>
            <p>Operation ID: <code t-esc="state.status.operation_id"/></p><p>Exact plan hash: <code t-esc="state.status.plan_hash"/></p>
            <p t-if="state.status.approval_expires_at">Start approval expires: <time t-att-datetime="state.status.approval_expires_at" t-esc="state.status.approval_expires_at"/></p>
            <p t-if="state.status.state==='awaiting_operator_approval'">Next: local operator approval for this exact hash, followed by local apply.</p>
            <pre t-if="state.status.state==='awaiting_operator_approval'" t-esc="approvalCommand"/>
            <p t-if="state.status.state==='awaiting_operator_approval'">Replace the uppercase path placeholders with the independently configured local operator paths. Review the full plan and supply any required trust, permission or destructive acknowledgements locally.</p>
            <button t-if="!state.prepared &amp;&amp; !state.submitted &amp;&amp; requestId" t-on-click="submit" t-att-disabled="state.busy">Request this prepared operation</button>
            <ol><li t-foreach="state.status.history" t-as="event" t-key="event.sequence"><time t-att-datetime="event.utc" t-esc="event.utc"/> · <t t-esc="event.code"/></li></ol>
            <table t-if="state.status.dimensions.length"><thead><tr><th>Plugin</th><th>Artifact</th><th>Release</th><th>Database</th><th>Feature</th><th>Service runtime</th></tr></thead><tbody><tr t-foreach="state.status.dimensions" t-as="item" t-key="item.installation_id+item.workspace_id"><td t-esc="item.plugin_id"/><td t-esc="item.artifact_state"/><td t-esc="item.release_state"/><td t-esc="item.database_state"/><td t-esc="item.feature_state||'Not enabled'"/><td t-esc="item.service_state||'Not applicable'"/></tr></tbody></table>
        </section>
    </section>`;

    setup(){
        this.state=useState({context:null,catalog:[],catalogNext:null,catalogBusy:false,installed:[],installedOffset:0,installedNext:null,inspectionStale:false,details:null,uploadName:'',uploadBusy:false,uploadResult:null,digest:'',action:'suspend',workspace:this.props.initialWorkspace||'',cascade:false,prepared:null,status:null,impact:null,featureStates:[],destructiveConfirmed:false,error:'',loading:true,busy:false,submitted:false});
        this.controller=new AbortController();this.active=true;this.sequence=0;this.checking=false;this.resumeOperation=null;
        this.inspectionSequence=0;this.uploadSequence=0;this.detailSequence=0;this.loadSequence=0;
        onMounted(()=>{this.timer=setInterval(()=>this.poll(),5000);this.load();});
        onWillDestroy(()=>{this.active=false;this.sequence++;this.clearInspection();clearInterval(this.timer);this.controller.abort();});
    }
    get selected(){return this.state.catalog.find(item=>item.artifact_digest===this.state.digest);}
    get needsWorkspace(){return ['install','upgrade','suspend','enable'].includes(this.state.action);}
    get requestAllowed(){const plan=this.state.prepared?.plan;if(!plan)return Boolean(!this.state.prepared&&this.resumeOperation&&this.resumeOperation===this.state.status?.operation_id&&this.requestId);return Boolean((!plan.destructive||this.state.destructiveConfirmed)&&(plan.operation_type!=='uninstall'||this.state.impact));}
    featurePlugin(scope){return this.state.prepared?.targets.find(t=>t.installation_id===scope.installation_id&&t.workspace_id===scope.workspace_id)?.plugin_id||scope.installation_id;}
    workspaceList(ids){return ids.map(id=>this.workspaceName(id)).join(', ');}
    get approvalCommand(){
        const s=this.state.status;if(!s)return '';
        const prefix='modular --config OPERATOR_TRUST_CONFIG ';
        const paths=' --store OPERATOR_STORE --deployment-config DEPLOYMENT_CONFIG --catalog OPERATOR_CATALOG';
        return prefix+'operations import-request '+s.operation_id+paths+'\n'+
            prefix+'operations approve '+s.operation_id+' --plan-hash '+s.plan_hash+paths+'\n'+
            prefix+'plugin apply '+s.operation_id+paths+'\n'+
            prefix+'operations mirror-status '+s.operation_id+paths;
    }
    workspaceName(id){return this.state.context?.workspaces.find(item=>item.workspace_id===id)?.name||id;}
    get permissionDefinitions(){return Object.entries(this.state.details?.manifest.permissions.defines||{});}
    get pluginDependencies(){return Object.entries(this.state.details?.manifest.dependencies.plugins||{});}
    get uploadCommand(){const digest=this.state.uploadResult?.artifact_digest;if(!digest)return '';return 'modular --config OPERATOR_TRUST_CONFIG plugin validate ARTIFACT_FILE --digest '+digest+'\nmodular --config OPERATOR_TRUST_CONFIG catalog --store OPERATOR_CATALOG add ARTIFACT_FILE --digest '+digest;}
    clearInspection(){this.inspectionSequence++;this.uploadSequence++;this.detailSequence++;this.uploadFile=null;Object.assign(this.state,{installed:[],installedOffset:0,installedNext:null,details:null,uploadName:'',uploadBusy:false,uploadResult:null});}
    closeDetails(){this.detailSequence++;this.state.details=null;}
    async showDetails(digest){const sequence=++this.detailSequence;this.state.details=null;try{const value=await this.api('/api/v1/operations/details?digest='+encodeURIComponent(digest));if(this.active&&sequence===this.detailSequence)this.state.details=value;}catch(error){if(sequence===this.detailSequence)this.failure(error);}}
    async loadInstalled(offset=0){const sequence=this.inspectionSequence;try{const value=await this.api('/api/v1/operations/installed?offset='+offset);if(this.active&&sequence===this.inspectionSequence){this.state.installed=value.items;this.state.installedOffset=offset;this.state.installedNext=value.next_offset;this.state.inspectionStale=value.stale;}}catch(error){if(sequence===this.inspectionSequence)this.failure(error);}}
    async loadMoreCatalog(){
        if(this.state.catalogNext===null||this.state.catalogBusy)return;const sequence=this.inspectionSequence;this.state.catalogBusy=true;
        try{const page=await this.api('/api/v1/operations/catalog?offset='+this.state.catalogNext);if(!this.active||sequence!==this.inspectionSequence)return;
            if(page.snapshot_digest!==this.catalogSnapshot)throw Object.assign(new Error('Catalog changed. Refresh metadata before selecting a version.'),{code:'CONFLICT'});
            this.state.catalog.push(...page.items);this.state.catalogNext=page.next_offset;
        }catch(error){if(sequence===this.inspectionSequence)this.failure(error);}finally{if(this.active)this.state.catalogBusy=false;}
    }
    selectUpload(event){this.uploadSequence++;this.uploadFile=event.target.files?.[0]||null;this.state.uploadName=this.uploadFile?.name||'';this.state.uploadResult=null;}
    async upload(){
        const file=this.uploadFile;if(!file||this.state.uploadBusy)return;const sequence=++this.uploadSequence;this.state.uploadBusy=true;this.state.error='';this.state.uploadResult=null;
        try{
            if(file.size<1||file.size>100*1024*1024)throw new Error('Choose a nonempty archive of at most 100 MiB.');
            const bytes=await file.arrayBuffer();if(!this.active||sequence!==this.uploadSequence)return;
            const hash=await crypto.subtle.digest('SHA-256',bytes);if(!this.active||sequence!==this.uploadSequence)return;
            const digest='sha256:'+Array.from(new Uint8Array(hash),byte=>byte.toString(16).padStart(2,'0')).join('');
            const value=await this.api('/api/v1/operations/validate-upload',file,{binary:true,timeoutMs:90000,headers:{'X-MP-Artifact-Digest':digest}});
            if(this.active&&sequence===this.uploadSequence)this.state.uploadResult=value;
        }catch(error){if(sequence===this.uploadSequence)this.failure(error);}finally{if(this.active&&sequence===this.uploadSequence)this.state.uploadBusy=false;}
    }
    get resumeKey(){return this.principal&&this.state.context?'mp.operation.'+this.state.context.site_id+'.'+this.principal:null;}
    forgetPending(){try{if(this.resumeKey)sessionStorage.removeItem(this.resumeKey);}catch{/* Storage is optional; the local journal remains authoritative. */}}
    rememberPending(operation){try{if(this.resumeKey)sessionStorage.setItem(this.resumeKey,JSON.stringify({operation_id:operation.operation_id,request_id:this.requestId}));}catch{/* Keep the current in-memory observation. */}}
    clearPlan(){this.forgetPending();this.sequence++;this.state.prepared=null;this.state.status=null;this.state.impact=null;this.state.featureStates=[];this.state.destructiveConfirmed=false;this.state.submitted=false;this.requestId=null;this.resumeOperation=null;}
    async restorePending(){
        const key=this.resumeKey,sequence=this.sequence;let pending;
        try{pending=JSON.parse(key?sessionStorage.getItem(key):null);}catch{return;}
        const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
        if(!pending||Object.keys(pending).sort().join(',')!=='operation_id,request_id'||!uuid.test(pending.operation_id)||!uuid.test(pending.request_id))return;
        // An opaque resume hint never grants access: load status through the
        // current session, operator role, own-request and release-pin checks.
        const status=await this.api('/api/v1/operations/status/'+pending.operation_id);
        if(this.active&&sequence===this.sequence&&key===this.resumeKey){
            this.state.status=status;this.requestId=pending.request_id;this.resumeOperation=status.operation_id;
            this.state.submitted=status.source==='operator_journal_mirror'||status.history.some(item=>item.code==='requested');
        }
    }
    async api(path,body=null,options={}){
        const controller=new AbortController();const abort=()=>controller.abort();this.controller.signal.addEventListener('abort',abort,{once:true});
        const timer=setTimeout(abort,options.timeoutMs||10000);
        try{return await this.props.api(path,body,{...options,signal:controller.signal});}
        finally{clearTimeout(timer);this.controller.signal.removeEventListener('abort',abort);}
    }
    denied(){this.clearPlan();this.clearInspection();this.state.context=null;this.state.catalog=[];this.state.catalogNext=null;this.props.onDenied();}
    failure(error){
        if(!this.active)return;
        if(this.state.status)this.state.status.stale=true;
        if(['UNAUTHENTICATED','FORBIDDEN','NOT_FOUND'].includes(error.code))this.denied();
        this.state.error=error.name==='AbortError'?'Request timed out. Check progress before retrying a submitted request.':error.message||'Operation information is unavailable';
    }
    async authority(){
        const session=await this.api('/api/v1/session');if(!this.active)return false;
        if(this.principal&&session.principal_id!==this.principal){this.clearPlan();this.clearInspection();this.state.catalog=[];this.state.catalogNext=null;}
        this.principal=session.principal_id;this.props.onSession(session);
        const context=await this.api('/api/v1/operations/context');
        if(!this.active)return false;
        this.state.context=context;
        if(!context.can_request){this.denied();this.state.error='Application operator access is required';return false;}
        return true;
    }
    async load(){
        this.state.loading=true;this.state.error='';const load=++this.loadSequence;this.inspectionSequence++;
        try{if(!await this.authority()||load!==this.loadSequence)return;const sequence=this.inspectionSequence;const catalog=await this.api('/api/v1/operations/catalog');if(this.active&&sequence===this.inspectionSequence){this.state.catalog=catalog.items;this.state.catalogNext=catalog.next_offset??null;this.catalogSnapshot=catalog.snapshot_digest;await this.loadInstalled();if(!this.state.prepared&&!this.state.status)await this.restorePending();}}
        catch(error){this.failure(error);}finally{if(this.active)this.state.loading=false;}
    }
    async prepare(){
        const item=this.selected;if(!item||this.state.busy)return;
        this.clearPlan();const sequence=this.sequence;this.state.busy=true;this.state.error='';
        const body={schema_version:1,operation:'prepare',operation_type:this.state.action,plugin_id:item.plugin_id,site_id:this.state.context.site_id,
            workspace_ids:this.needsWorkspace?[this.state.workspace]:[],cascade:this.state.cascade};
        if(['install','upgrade'].includes(this.state.action)){body.artifact_version=item.version;body.artifact_digest=item.artifact_digest;}
        if(this.state.action==='remove')body.artifact_digest=item.artifact_digest;
        try{const value=await this.api('/api/v1/operations/prepare',body);
            const bundle=await this.api('/api/v1/operations/bundle/'+value.operation_id);
            if(bundle.plan_hash!==value.plan_hash||bundle.plan.operation_id!==value.operation_id)throw Object.assign(new Error('Prepared operation changed.'),{code:'CONFLICT'});
            const featureStates=bundle.operation_lock.feature_states||[];
            if(!Array.isArray(featureStates)||featureStates.length&&(
                featureStates.length!==value.targets.length||new Set(featureStates.map(r=>r.installation_id+'|'+r.workspace_id)).size!==featureStates.length||
                featureStates.some(r=>!['enabled','suspended'].includes(r.availability)||!value.targets.some(t=>t.installation_id===r.installation_id&&t.workspace_id===r.workspace_id&&t.site_id===r.site_id))))throw Object.assign(new Error('Invalid workspace state preview.'),{code:'VALIDATION_FAILED'});
            let impact=null;
            if(value.plan.operation_type==='uninstall'){
                impact=await this.api('/api/v1/operations/impact/'+value.operation_id);
                if(impact.schema_version!==1||impact.kind!=='native_uninstall_impact'||impact.operation_id!==value.operation_id||impact.plan_hash!==value.plan_hash||
                    !impact.destructive||!impact.requires_backup||impact.artifact_action!=='retain_in_runtime'||
                    ['plugins','models','fields','constraints','foreign_references','metadata_records','assets','warnings','native_closure','requested_addons'].some(k=>!Array.isArray(impact.impact?.[k])))throw Object.assign(new Error('Invalid native uninstall preview.'),{code:'VALIDATION_FAILED'});
            }
            if(this.active&&sequence===this.sequence){this.state.prepared=value;this.state.featureStates=featureStates;this.state.impact=impact;this.requestId=crypto.randomUUID();}}
        catch(error){if(sequence===this.sequence)this.failure(error);}finally{if(this.active)this.state.busy=false;}
    }
    async submit(){
        const prepared=this.state.prepared||this.state.status;
        if(this.state.busy||!prepared||!this.requestId||!this.requestAllowed)return;this.state.busy=true;this.state.error='';const sequence=this.sequence;
        this.rememberPending(prepared);
        try{const status=await this.api('/api/v1/operations/request',{schema_version:1,operation:'request',operation_id:prepared.operation_id,plan_hash:prepared.plan_hash,request_id:this.requestId});
            if(this.active&&sequence===this.sequence){this.state.status=status;this.state.submitted=true;}}
        catch(error){if(sequence===this.sequence)this.failure(error);}finally{if(this.active)this.state.busy=false;}
    }
    async poll(){
        if(!this.active||document.hidden||this.checking)return;this.checking=true;
        try{if(!await this.authority())return;const operation=this.state.prepared?.operation_id||this.state.status?.operation_id,sequence=this.sequence;if(!operation)return;
            const status=await this.api('/api/v1/operations/status/'+operation);
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
