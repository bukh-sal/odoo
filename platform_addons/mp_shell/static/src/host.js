/** Concentrated native adapter + major-1 framework-neutral host implementation. */
import { Component, xml, useState, useRef, useSubEnv, onMounted, onWillDestroy } from '@odoo/owl';
import { startWebClient } from '@web/start';
import { rpc } from '@web/core/network/rpc';
import { View } from '@web/views/view';
import { MainComponentsContainer } from '@web/core/main_components_container';
import { registry } from '@web/core/registry';

let workspace = null;
let generation = 0;
const pendingNative = new Set();
const nativeRPC = rpc._rpc;
function obsolete() { return new DOMException('Obsolete page context','AbortError'); }
rpc._rpc = function(url,params,settings={}) {
    const captured=generation;
    const pending=nativeRPC.call(this,url,params,{...settings,cache:false,headers:{...settings.headers,...(workspace?{'X-MP-Workspace':workspace}:{})}});
    let cancel;
    const cancellation=new Promise((resolve,reject)=>cancel=()=>reject(obsolete()));
    const guarded=Promise.race([pending,cancellation]).then(value=>{if(captured!==generation)throw obsolete();return value;}).finally(()=>pendingNative.delete(guarded));
    guarded.abort=(rejectError=true)=>{pending.abort(false);if(rejectError)cancel();};
    pendingNative.add(guarded);
    return guarded;
};

function error(code,request_id=crypto.randomUUID(),details={}) {
    const value=new Error(code.replaceAll('_',' ').toLowerCase());
    Object.assign(value,{code,request_id,retryable:false,details});return value;
}
function freeze(value) {
    if (value && typeof value==='object') {Object.values(value).forEach(freeze);Object.freeze(value);}
    return value;
}
const words={
    'en-US':{workspace:'Workspace',notes:'Notes',settings:'Settings',export:'Export notes',search:'Commands',theme:'Theme',language:'Language',back:'All notes',retry:'Try again',empty:'Select a workspace to begin',subtitle:'Your ideas, in one place.',saved:'Saved',light:'Light',dark:'Dark'},
    'ar':{workspace:'مساحة العمل',notes:'الملاحظات',settings:'الإعدادات',export:'تصدير الملاحظات',search:'الأوامر',theme:'المظهر',language:'اللغة',back:'كل الملاحظات',retry:'إعادة المحاولة',empty:'اختر مساحة عمل للبدء',subtitle:'أفكارك في مكان واحد.',saved:'تم الحفظ',light:'فاتح',dark:'داكن'},
};

class Shell extends Component {
    static components={View,MainComponentsContainer};
    static props={};
    static template=xml`
    <div class="mp_root" t-att-dir="state.language==='ar'?'rtl':'ltr'">
        <header><div class="mp_brand"><span class="mp_mark">M</span><strong>Modular Platform</strong></div>
            <div class="mp_tools"><label><span class="visually-hidden" t-esc="t('workspace')"/>
                <select t-on-change="switchWorkspace" t-att-aria-label="t('workspace')">
                    <option value="" t-att-selected="!state.workspace" t-esc="t('workspace')"/>
                    <option t-foreach="state.workspaces" t-as="space" t-key="space.id" t-att-value="space.id" t-att-selected="space.id===state.workspace" t-esc="space.name"/>
                </select></label>
                <button t-on-click="openCommands" t-esc="t('search')"/>
                <span t-esc="state.displayName"/>
            </div>
        </header>
        <aside><nav aria-label="Applications">
            <t t-foreach="state.navigation" t-as="app" t-key="app.plugin_id">
                <a t-foreach="app.navigation" t-as="item" t-key="item.id" href="#" t-att-aria-current="state.plugin===app.plugin_id and !state.settings ? 'page' : undefined" t-on-click.prevent="()=>this.openPage(app.plugin_id,item.page)"><t t-esc="app.plugin_id==='org.example.notes'?t('notes'):app.name"/></a>
            </t>
            <a href="#" t-on-click.prevent="openSettings" t-att-aria-current="state.settings?'page':undefined" t-esc="t('settings')"/>
        </nav></aside>
        <div class="mp_main" t-att-role="state.nativeProps?undefined:'main'" t-ref="main" t-att-style="state.paused?'visibility:hidden':''" t-on-input="trackDraft">
            <div class="mp_page_header"><div><h1 t-esc="state.settings?t('settings'):state.title"/><p class="mp_subtitle" t-esc="t('subtitle')"/></div>
                <button t-if="!state.settings and state.nativeProps and state.nativeProps.type==='form'" t-on-click="backToList" t-esc="t('back')"/>
                <button t-if="!state.settings and state.context and state.plugin==='org.example.notes'" t-on-click="exportNotes" t-esc="t('export')"/>
                <button t-if="state.nativeProps and state.nativeProps.type==='form' and selectedNote and state.context.capabilities.includes('org.example.notes:notes.delete')" t-on-click="deleteNote">Delete note</button>
            </div>
            <div t-if="state.notification" class="mp_notice" role="status" t-esc="state.notification"/>
            <div t-if="state.recoveryDraft and state.context" class="mp_notice" role="status">Your unsaved draft is available locally. <button t-on-click="downloadDraft">Download unsaved draft</button></div>
            <div t-if="state.error" class="mp_notice" role="alert"><strong t-esc="state.error.message"/><p t-esc="state.error.request_id"/>
                <p t-if="state.error.field">Field: <t t-esc="state.error.field"/></p>
                <button t-on-click="retry" t-esc="t('retry')"/>
                <a t-if="state.error.code==='UNAUTHENTICATED'" t-att-href="loginURL">Sign in</a>
                <button t-if="canRecoverDraft" t-on-click="downloadDraft">Download unsaved draft</button>
            </div>
            <p t-if="state.loading" role="status">Loading…</p>
            <section t-if="state.settings" class="mp_notice" aria-label="Preferences">
                <h2>Preferences</h2><label><t t-esc="t('theme')"/> <select t-on-change="setTheme" aria-label="Theme"><option value="light" t-att-selected="state.theme==='light'" t-esc="t('light')"/><option value="dark" t-att-selected="state.theme==='dark'" t-esc="t('dark')"/></select></label>
                <label><t t-esc="t('language')"/> <select t-on-change="setLanguage" aria-label="Language"><option value="en-US" t-att-selected="state.language==='en-US'">English</option><option value="ar" t-att-selected="state.language==='ar'">العربية</option></select></label>
                <p>Workspace access is checked for every operation. Installation and deployment require a separate local operator.</p>
            </section>
            <section t-if="state.settings and isWorkspaceAdministrator and state.workspaceSettings" class="mp_notice" aria-label="Workspace administration">
                <h2>Workspace administration</h2>
                <form t-on-submit.prevent="saveWorkspaceConfiguration" t-on-input="markSettingsDirty" class="mp_settings_form">
                    <label for="mp_workspace_name">Workspace name</label><input id="mp_workspace_name" t-model="state.workspaceSettings.name" maxlength="100" required="required"/>
                    <label for="mp_workspace_locale">Default language</label><select id="mp_workspace_locale" t-model="state.workspaceSettings.default_locale"><option value="en-US">English</option><option value="ar">العربية</option></select>
                    <label for="mp_workspace_timezone">Time zone</label><input id="mp_workspace_timezone" t-model="state.workspaceSettings.timezone" maxlength="64" required="required"/>
                    <button type="submit" t-att-disabled="state.adminBusy">Save workspace settings</button>
                </form>
                <h3>Members</h3><p>Use the public principal ID supplied by your operator. Account provisioning remains an operator action.</p>
                <table class="mp_members"><thead><tr><th scope="col">Member</th><th scope="col">Role</th><th scope="col">Access</th></tr></thead><tbody>
                    <tr t-foreach="state.members" t-as="member" t-key="member.principal_id">
                        <td t-esc="member.display_name"/><td><select t-att-aria-label="'Role for '+member.display_name" t-on-change="event=>this.changeWorkspaceMember(member.principal_id,event.target.value,event.target)" t-att-disabled="state.adminBusy">
                            <option value="viewer" t-att-selected="member.role==='viewer'">Viewer</option><option value="editor" t-att-selected="member.role==='editor'">Editor</option><option value="administrator" t-att-selected="member.role==='administrator'" t-att-disabled="member.kind==='service'">Administrator</option>
                        </select></td><td><button t-on-click="()=>this.removeWorkspaceMember(member)" t-att-aria-label="'Revoke access for '+member.display_name" t-att-disabled="state.adminBusy">Revoke access</button></td>
                    </tr>
                </tbody></table>
                <form t-on-submit.prevent="addWorkspaceMember" class="mp_settings_form">
                    <label for="mp_member_principal">Principal ID</label><input id="mp_member_principal" t-model="state.memberPrincipal" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" required="required"/>
                    <label for="mp_member_role">Member role</label><select id="mp_member_role" t-model="state.memberRole"><option value="viewer">Viewer</option><option value="editor">Editor</option><option value="administrator">Administrator</option></select>
                    <button type="submit" t-att-disabled="state.adminBusy">Add member</button>
                </form>
            </section>
            <div class="mp_content" t-if="!state.settings">
                <div t-ref="custom"/>
                <View t-if="state.nativeProps" t-key="state.generation" t-props="state.nativeProps"/>
                <p t-if="!state.context and !state.loading and !state.error" t-esc="t('empty')"/>
            </div>
        </div>
        <dialog t-ref="commands"><h2 t-esc="t('search')"/><button class="mp_command_row" t-on-click="paletteExport" t-esc="t('export')"/><button class="mp_command_row" t-on-click="paletteSettings" t-esc="t('settings')"/><button class="mp_command_row" t-on-click="closeCommands">Close · Esc</button></dialog>
        <dialog t-ref="confirmation" aria-labelledby="mp_confirmation_title" t-on-cancel="cancelConfirmation">
            <h2 id="mp_confirmation_title" t-esc="state.confirmation.title"/><p t-esc="state.confirmation.message"/>
            <button t-on-click="cancelConfirmation">Cancel</button><button t-on-click="acceptConfirmation" t-esc="state.confirmation.destructive?'Delete':'Continue'"/>
        </dialog>
        <MainComponentsContainer/>
    </div>`;

    setup() {
        this.state=useState({workspaces:[],workspace:'',navigation:[],plugin:'org.example.notes',title:'Notes',displayName:'',context:null,nativeProps:null,generation:0,error:null,notification:'',loading:true,settings:false,paused:false,confirmation:{title:'',message:'',destructive:false},theme:localStorage.getItem('mp.theme')||'light',language:localStorage.getItem('mp.language')||'en-US'});
        if(!words[this.state.language])this.state.language='en-US';
        this.main=useRef('main');this.custom=useRef('custom');this.commands=useRef('commands');
        this.confirmation=useRef('confirmation');
        Object.assign(this.state,{members:[],workspaceSettings:null,memberPrincipal:'',memberRole:'viewer',adminBusy:false,settingsDirty:false,recoveryDraft:false});
        const shell=this;
        useSubEnv({config:{...this.env.config,breadcrumbs:[{get name(){return shell.state.nativeTitle||shell.state.title;}}],getDisplayName:()=>this.state.nativeTitle||this.state.title,setDisplayName:name=>this.state.nativeTitle=name,historyBack:()=>this.backToList()}});
        this.themeListeners=new Set();this.localeListeners=new Set();this.eventListeners=new Map();
        this.transition=0;
        this.onPop=async()=>{
            if(!await this.canLeave()){history.pushState({},'',this.currentURL);return;}
            this.nativeDirty=false;this.draft=null;this.state.settingsDirty=false;this.settingsRecovery=null;await this.activate();
        };
        this.onVisibility=async()=>{
            if(document.hidden){this.state.paused=true;return;}
            await this.refreshAuthority();this.state.paused=false;
        };
        this.onKey=event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();this.openCommands();}};
        onMounted(async()=>{
            document.body.dataset.theme=this.state.theme;
            window.addEventListener('popstate',this.onPop);window.addEventListener('keydown',this.onKey);document.addEventListener('visibilitychange',this.onVisibility);
            // Authority refresh must not depend on initial native-view loading;
            // rapid navigation can cancel that activation before it completes.
            this.timer=setInterval(()=>this.refreshAuthority(),5000);
            try {const session=await this.json('/api/v1/session');this.csrf=session.csrf_token;this.state.displayName=session.display_name;this.state.workspaces=await this.json('/api/v1/workspaces');await this.activate();}
            catch(e){this.fail(e);this.state.loading=false;}
        });
        onWillDestroy(()=>{clearInterval(this.timer);clearTimeout(this.noticeTimer);window.removeEventListener('popstate',this.onPop);window.removeEventListener('keydown',this.onKey);document.removeEventListener('visibilitychange',this.onVisibility);this.retire();});
    }
    t(key){return words[this.state.language][key]||key;}
    get loginURL(){return '/web/login?redirect='+encodeURIComponent(location.pathname+location.search);}
    async json(path,body,options={}){
        let response;
        try{response=await fetch(path,{cache:'no-store',credentials:'same-origin',method:body?'POST':'GET',signal:options.signal,
            headers:{...(workspace?{'X-MP-Workspace':workspace}:{}),...(body?{'Content-Type':'application/json','X-CSRFToken':this.csrf}:{}),...options.headers},...(body?{body:JSON.stringify(body)}:{})});}
        catch(e){if(e.name==='AbortError')throw e;throw Object.assign(error('DEPENDENCY_UNAVAILABLE',undefined,{outcome:'unknown'}),{retryable:true});}
        let result;try{result=await response.json();}catch{throw error(response.status===401?'UNAUTHENTICATED':'INTERNAL_ERROR');}
        if(!response.ok||result.error){const e=result.error||{};throw Object.assign(error(e.code||'INTERNAL_ERROR',e.request_id,e.details),{message:e.message||'Operation unavailable',retryable:!!e.retryable});}
        if(result.api_version!=='1.0'||typeof result.request_id!=='string'||!('data'in result))throw error('INTERNAL_ERROR');
        return result.data;
    }
    trackDraft(){
        if(this.state.nativeProps?.type!=='form')return;
        this.nativeDirty=true;
        this.draftPrincipal=this.state.context?.principal_id;
        const root=this.main.el;
        this.draft={title:root.querySelector('[name="title"] input')?.value||'',body:root.querySelector('[name="body"] textarea')?.value||''};
    }
    async canLeave(){
        const dirty=this.nativeDirty||this.state.settingsDirty||(this.mounted?.canLeave&&await this.mounted.canLeave()==='confirm');
        return !dirty||await this.confirm({title:'Unsaved changes',message:'Discard unsaved changes?',destructive:false});
    }
    confirm(input){
        if(this.confirmResolve)throw error('CONFLICT');
        this.state.confirmation={title:input.title,message:input.message,destructive:!!input.destructive};
        this.confirmation.el.showModal();
        return new Promise(resolve=>this.confirmResolve=resolve);
    }
    finishConfirmation(value){this.confirmation.el.close();const resolve=this.confirmResolve;this.confirmResolve=null;resolve?.(value);}
    cancelConfirmation(event){event?.preventDefault();this.finishConfirmation(false);}
    acceptConfirmation(){this.finishConfirmation(true);}
    async retire(){
        const mounted=this.mounted;this.mounted=null;
        this.controller?.abort();for(const p of pendingNative)p.abort();pendingNative.clear();
        this.state.nativeProps=null;this.bindings=[];
        this.custom.el?.replaceChildren();
        this.themeListeners.clear();this.localeListeners.clear();this.eventListeners.clear();
        if(mounted)await mounted.dispose();
    }
    fail(e){if(e.name==='AbortError')return;if(e.code==='CONFLICT'&&this.nativeDirty&&this.draft)this.state.recoveryDraft=true;this.state.error={code:e.code||'INTERNAL_ERROR',message:e.message||'Page unavailable',request_id:e.request_id||crypto.randomUUID(),field:e.details?.field};}
    async go(url){if(!await this.canLeave())return;this.nativeDirty=false;this.state.settingsDirty=false;this.settingsRecovery=null;this.draft=null;this.state.recoveryDraft=false;history.pushState({},'',url);await this.activate();}
    async openPage(plugin,pageId,query={}){
        const app=this.state.navigation.find(app=>app.plugin_id===plugin);const page=app?.pages.find(p=>p.id===pageId);
        if(!page)throw error('NOT_FOUND');
        const url=new URL('/app/'+plugin+page.path,location.origin);url.searchParams.set('workspace',this.state.workspace);
        for(const [key,value]of Object.entries(query)){if(['workspace','plugin','site_id','principal_id'].includes(key))throw error('VALIDATION_FAILED');url.searchParams.set(key,value);}
        await this.go(url);
    }
    async switchWorkspace(event){const url=new URL(location.href);url.searchParams.set('workspace',event.target.value);url.searchParams.delete('note');url.searchParams.delete('new');await this.go(url);}
    async openSettings(){const url=new URL('/app/settings',location.origin);if(this.state.workspace)url.searchParams.set('workspace',this.state.workspace);await this.go(url);}
    async backToList(){return this.openPage(this.state.plugin,this.page.id);}
    async deleteNote(){
        if(!await this.confirm({title:'Delete note',message:'Permanently delete this note?',destructive:true}))return;
        try{await this.callService('documents','delete',{note_id:this.selectedNote.public_id,expected_revision:this.selectedNote.revision},{idempotencyKey:crypto.randomUUID()});this.nativeDirty=false;this.draft=null;this.selectedNote=null;await this.backToList();this.notify('Note deleted');}catch(e){this.fail(e);}
    }
    async retry(){if(!await this.canLeave())return;this.nativeDirty=false;this.state.settingsDirty=false;this.settingsRecovery=null;this.draft=null;this.state.recoveryDraft=false;await this.activate(true);}
    openCommands(){this.commands.el.showModal();}
    closeCommands(){this.commands.el.close();}
    async paletteExport(){this.closeCommands();await this.exportNotes();}
    async paletteSettings(){this.closeCommands();await this.openSettings();}
    setTheme(event){this.state.theme=event.target.value;localStorage.setItem('mp.theme',this.state.theme);document.body.dataset.theme=this.state.theme;for(const callback of this.themeListeners)callback(this.theme());}
    async setLanguage(event){if(!await this.canLeave()){event.target.value=this.state.language;return;}this.state.settingsDirty=false;this.settingsRecovery=null;this.state.language=event.target.value;localStorage.setItem('mp.language',this.state.language);for(const callback of this.localeListeners)callback(this.locale());await this.activate(true);}
    get isWorkspaceAdministrator(){return !!this.state.context?.capabilities.includes('org.modularplatform.identity:workspace.members.manage');}
    markSettingsDirty(){this.state.settingsDirty=true;}
    async loadWorkspaceAdministration(controller,captured){
        const headers={'X-MP-Workspace':workspace};
        const [settings,members]=await Promise.all([this.json('/api/v1/workspace/settings',null,{signal:controller.signal,headers}),this.json('/api/v1/workspace/members',null,{signal:controller.signal,headers})]);
        if(captured!==generation)throw obsolete();
        this.state.workspaceSettings={name:settings.name,default_locale:settings.default_locale,timezone:settings.timezone};this.state.members=members;this.state.settingsDirty=false;
        if(this.settingsRecovery?.principal===this.state.context.principal_id&&this.settingsRecovery.workspace===workspace){this.state.workspaceSettings={...this.settingsRecovery.value};this.state.settingsDirty=true;this.notify('Workspace configuration changed. Review your unsaved values before saving.');}
    }
    async mutateWorkspace(path,input,message,savingSettings=false){
        if(this.state.adminBusy)return;
        if(this.state.settingsDirty&&!savingSettings&&!await this.canLeave())return;
        const captured=generation;const selectedWorkspace=workspace;const controller=this.controller;this.state.adminBusy=true;
        try{
            await this.json('/api/v1/workspace/'+path,input,{signal:controller.signal,headers:{'X-MP-Workspace':selectedWorkspace}});
            if(captured!==generation)throw obsolete();
            this.state.settingsDirty=false;this.settingsRecovery=null;this.state.workspaces=await this.json('/api/v1/workspaces',null,{signal:controller.signal});
            if(captured!==generation)throw obsolete();await this.activate(true);this.notify(message);return true;
        }catch(e){this.fail(e);return false;}finally{if(captured===generation)this.state.adminBusy=false;}
    }
    async saveWorkspaceConfiguration(){return this.mutateWorkspace('settings',{...this.state.workspaceSettings},'Workspace settings saved',true);}
    async addWorkspaceMember(){return this.mutateWorkspace('members',{operation:'add',principal_id:this.state.memberPrincipal.trim(),role:this.state.memberRole},'Member access added');}
    async changeWorkspaceMember(principal,role,select){const previous=this.state.members.find(member=>member.principal_id===principal)?.role;const saved=await this.mutateWorkspace('members',{operation:'update',principal_id:principal,role},'Member role updated');if(!saved&&select)select.value=previous;}
    async removeWorkspaceMember(member){if(await this.confirm({title:'Revoke workspace access',message:'Revoke '+member.display_name+' access to this workspace? Data and the account will be retained.'}))return this.mutateWorkspace('members',{operation:'remove',principal_id:member.principal_id},'Member access revoked');}
    theme(){return freeze({mode:this.state.theme,density:'comfortable'});}
    locale(){return freeze({language:this.state.language,direction:this.state.language==='ar'?'rtl':'ltr',timezone:this.state.context?.timezone||'UTC'});}
    notify(message){this.state.notification=message;clearTimeout(this.noticeTimer);this.noticeTimer=setTimeout(()=>this.state.notification='',5000);}
    download(name,value){const blob=new Blob([JSON.stringify(value,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download=name;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
    async downloadDraft(){
        if(!this.draft)return;
        try{const session=await this.json('/api/v1/session');if(session.principal_id!==this.draftPrincipal){this.draft=null;this.state.recoveryDraft=false;throw error('FORBIDDEN');}}
        catch(e){if(!['UNAUTHENTICATED','INTERNAL_ERROR','DEPENDENCY_UNAVAILABLE','DEADLINE_EXCEEDED'].includes(e.code)){this.fail(e);return;}}
        this.download('unsaved-note.json',this.draft);
    }
    get canRecoverDraft(){return !!this.draft&&['UNAUTHENTICATED','INTERNAL_ERROR','DEPENDENCY_UNAVAILABLE','DEADLINE_EXCEEDED'].includes(this.state.error?.code);}
    async exportNotes(){
        try{const notes=[];let cursor=null;do{const data=await this.callService('documents','list',{limit:100,...(cursor?{cursor}:{})});notes.push(...data.items.map(({id,title,body,revision,labels})=>({id,title,body,revision,labels})));cursor=data.next_cursor;if(notes.length>=10000&&cursor)throw error('VALIDATION_FAILED');}while(cursor);this.download('notes.json',{schema_version:1,workspace_id:workspace,notes});this.notify('Notes exported');}
        catch(e){this.fail(e);}
    }
    async callService(alias,method,input,options={}){
        if(Object.keys(options).some(k=>!['signal','idempotencyKey'].includes(k)))throw error('VALIDATION_FAILED');
        const binding=this.bindings?.find(binding=>binding.alias===alias);if(!binding)throw error('DEPENDENCY_UNAVAILABLE');
        const captured=generation;const controller=new AbortController();const signals=[this.controller.signal,options.signal].filter(Boolean);const abort=()=>controller.abort();
        if(options.signal?.aborted)throw error('CANCELLED',undefined,{outcome:'not_started'});
        for(const signal of signals){if(signal.aborted)abort();else signal.addEventListener('abort',abort,{once:true});}
        try{
            const value=await this.json('/api/v1/services/'+binding.service_id+'/'+method,{api_version:binding.api_version,request_id:crypto.randomUUID(),...(options.idempotencyKey?{idempotency_key:options.idempotencyKey}:{}),input},{signal:controller.signal,headers:{'X-MP-Binding':binding.binding_id,'X-MP-Consumer':this.state.context.installation_id}});
            if(captured!==generation||controller.signal.aborted)throw obsolete();return value;
        }catch(e){if(captured!==generation)throw obsolete();if(e.name==='AbortError')throw error('CANCELLED',undefined,{outcome:'unknown'});if(e.code==='UNAUTHENTICATED'){await this.retire();generation++;this.state.context=null;this.fail(e);}throw e;}
        finally{for(const signal of signals)signal.removeEventListener('abort',abort);}
    }
    facade(context){
        const captured=generation;
        const ensure=()=>{if(captured!==generation||this.controller.signal.aborted)throw obsolete();};
        const subscribe=(set,callback)=>{if(captured!==generation)throw obsolete();set.add(callback);return()=>set.delete(callback);};
        return freeze({context:()=>context,navigate:target=>{ensure();if(target.params&&Object.keys(target.params).length)throw error('VALIDATION_FAILED');return this.openPage(target.pluginId,target.pageId,target.query);},services:{call:(...args)=>{ensure();return this.callService(...args);}},
            commands:{execute:async id=>{ensure();if(id==='org.modularplatform.shell:command:export')return this.exportNotes();throw error('NOT_FOUND');}},
            events:{subscribe:(topic,callback)=>{if(!['org.example.notes.changed'].includes(topic))throw error('FORBIDDEN');if(!this.eventListeners.has(topic))this.eventListeners.set(topic,new Set());return subscribe(this.eventListeners.get(topic),callback);}},
            notifications:{show:input=>{if(captured===generation)this.notify(input.message);}},dialogs:{confirm:async input=>{ensure();return this.confirm(input);}},
            theme:{current:()=>this.theme(),subscribe:callback=>subscribe(this.themeListeners,callback)},locale:{current:()=>this.locale(),translate:key=>key==='notes.title'?this.t('notes'):this.t(key)},
        });
    }
    async refreshAuthority(){
        if(!workspace||!this.state.context||this.checking)return;this.checking=true;const captured=generation;
        try{const value=await this.json('/api/v1/context?plugin_id='+this.state.plugin,null,{signal:this.controller.signal});if(captured===generation&&this.state.context&&(value.context.policy_generation!==this.state.context.policy_generation||value.context.principal_id!==this.state.context.principal_id||value.context.site_id!==this.state.context.site_id||value.context.installation_id!==this.state.context.installation_id)){
            if(this.state.settingsDirty&&value.context.principal_id===this.state.context.principal_id&&value.context.capabilities.includes('org.modularplatform.identity:workspace.members.manage'))this.settingsRecovery={principal:value.context.principal_id,workspace,value:{...this.state.workspaceSettings}};
            this.state.recoveryDraft=!!(this.nativeDirty&&this.draft);await this.activate(true);
        }}
        catch(e){if(captured===generation&&e.name!=='AbortError'){await this.retire();generation++;this.state.context=null;if(['FORBIDDEN','PLUGIN_SUSPENDED','NOT_FOUND'].includes(e.code)){this.draft=null;this.nativeDirty=false;this.state.recoveryDraft=false;this.settingsRecovery=null;}this.fail(e);}}
        finally{this.checking=false;}
    }
    async activate(force=false){
        const transition=++this.transition;
        const url=new URL(location.href);const nextWorkspace=url.searchParams.get('workspace');const settings=url.pathname==='/app/settings';const plugin=settings?this.state.plugin:url.pathname.split('/')[2];const path='/'+url.pathname.split('/').slice(3).join('/');
        this.currentURL=url.href;
        if(!force&&!settings&&this.mounted&&workspace===nextWorkspace&&plugin===this.state.plugin&&path===this.page?.path){await this.mounted.updateRoute?.(freeze({plugin_id:plugin,page_id:this.page.id,path,params:{},query:Object.fromEntries(url.searchParams)}));return;}
        await this.retire();if(transition!==this.transition)return;
        generation++;const captured=generation;workspace=nextWorkspace;
        this.state.workspace=workspace||'';this.state.plugin=plugin;this.state.generation=generation;this.state.context=null;this.state.settings=settings;this.state.error=null;this.state.nativeTitle='';this.state.loading=true;this.state.workspaceSettings=null;this.state.members=[];this.state.adminBusy=false;
        const controller=new AbortController();this.controller=controller;
        try{
            if(!workspace){this.state.navigation=[];return;}
            const navigation=await this.json('/api/v1/navigation',null,{signal:controller.signal});
            if(captured!==generation)throw obsolete();this.state.navigation=navigation;
            const value=await this.json('/api/v1/context?plugin_id='+plugin,null,{signal:controller.signal});
            if(captured!==generation)throw obsolete();
            const c=value.context;
            if(c.ui_api_major!==1||c.workspace_id!==workspace||c.plugin_id!==plugin||!Array.isArray(c.capabilities))throw error('INTERNAL_ERROR');
            if(this.boundPrincipal&&(c.principal_id!==this.boundPrincipal||c.site_id!==this.boundSite)){this.draft=null;this.nativeDirty=false;this.state.recoveryDraft=false;this.settingsRecovery=null;this.state.workspaces=await this.json('/api/v1/workspaces',null,{signal:controller.signal});if(captured!==generation)throw obsolete();}
            this.boundPrincipal=c.principal_id;this.boundSite=c.site_id;this.state.displayName=c.display_name;
            this.csrf=value.csrf_token;this.bindings=freeze(value.bindings);this.state.context=freeze({...c,generation,locale:this.state.language,direction:this.state.language==='ar'?'rtl':'ltr',capabilities:[...c.capabilities]});
            if(settings){if(this.isWorkspaceAdministrator)await this.loadWorkspaceAdministration(controller,captured);return;}
            this.page=value.pages.find(page=>page.path===path);if(!this.page)throw error('NOT_FOUND');
            this.state.title=plugin==='org.example.notes'?this.t('notes'):(this.state.navigation.find(app=>app.plugin_id===plugin)?.name||plugin);
            const route=freeze({plugin_id:plugin,page_id:this.page.id,path,params:{},query:Object.fromEntries(url.searchParams)});
            if(this.page.kind==='native_view')await this.nativeView(url);
            else{
                const module=registry.category('mp.pages').get(plugin+':'+this.page.id,null);if(!module)throw error('DEPENDENCY_UNAVAILABLE');
                const element=document.createElement('div');this.custom.el.replaceChildren(element);
                const mounted=await module.mount({element,host:this.facade(this.state.context),route,signal:this.controller.signal});
                if(captured!==generation){await mounted.dispose();element.remove();throw obsolete();}
                this.mounted=mounted;
            }
        }catch(e){this.fail(e);}
        finally{if(captured===generation)this.state.loading=false;}
    }
    async nativeView(url){
        const captured=generation;
        const action=await rpc('/web/action/load',{action_id:this.page.action_ref});
        if(captured!==generation)throw obsolete();
        const creating=url.searchParams.get('new')==='1';const publicID=url.searchParams.get('note');let selected=null;
        if(publicID){const rows=await rpc('/web/dataset/call_kw',{model:action.res_model,method:'search_read',args:[[['public_id','=',publicID]]],kwargs:{fields:['public_id','revision'],limit:1}});selected=rows[0];if(!selected)throw error('NOT_FOUND');}
        if(captured!==generation)throw obsolete();
        const type=creating||selected?'form':'list';const view=action.views.find(view=>view[1]===type);
        this.selectedNote=selected;
        const editable=this.state.context.capabilities.includes('org.example.notes:notes.write');
        if(creating&&!editable)throw error('FORBIDDEN');
        const props={resModel:action.res_model,type,viewId:view?.[0]||false,domain:[],context:{...(selected?{expected_revision:selected.revision}:{}),create:editable,edit:editable,delete:editable},display:{controlPanel:true},readonly:!editable,
            createRecord:()=>this.openPage(this.state.plugin,this.page.id,{new:'1'}),selectRecord:async ident=>{const rows=await rpc('/web/dataset/call_kw',{model:action.res_model,method:'read',args:[[ident],['public_id']],kwargs:{}});await this.openPage(this.state.plugin,this.page.id,{note:rows[0].public_id});},
        };
        if(type==='form')Object.assign(props,{resId:selected?.id||false,preventCreate:true,saveRecord:async record=>{
            try{
            const input={title:record.data.title,body:record.data.body||''};
            const payload=selected?{...input,note_id:publicID,expected_revision:selected.revision}:input;
            const fingerprint=JSON.stringify([workspace,publicID,payload]);
            if(this.saveAttempt?.fingerprint!==fingerprint)this.saveAttempt={fingerprint,key:crypto.randomUUID()};
            const saved=await this.callService('documents',selected?'update':'create',payload,{idempotencyKey:this.saveAttempt.key});
            this.saveAttempt=null;
            this.nativeDirty=false;this.draft=null;this.notify(this.t('saved'));await this.openPage(this.state.plugin,this.page.id,{note:saved.id});return true;
            }catch(e){this.fail(e);return false;}
        },onDiscard:async()=>{this.nativeDirty=false;this.draft=null;await this.backToList();}});
        this.state.nativeProps=props;
    }
}

startWebClient(Shell);
