/** Mount-scoped adapters to the existing Odoo interaction services.
 * Public host contracts stay framework-neutral; Odoo owns rendering, focus,
 * Escape handling, notification timers and command keyboard/search behavior.
 */
export class NativeInteractions {
    constructor({dialog, notification, command, ConfirmationDialog, provider, error}) {
        Object.assign(this,{dialog,notification,command,ConfirmationDialog,provider,error});
        this.notices=new Set();this.commands=[];this.pending=null;
    }
    confirm(input) {
        if(this.pending)throw this.error('CONFLICT');
        if(typeof input.title!=='string'||typeof input.message!=='string')throw this.error('VALIDATION_FAILED');
        return new Promise(resolve=>{
            const pending={resolve};this.pending=pending;
            const settle=value=>{
                if(this.pending!==pending)return;
                this.pending=null;resolve(value);
            };
            try {
                pending.close=this.dialog.add(this.ConfirmationDialog,{
                    title:input.title,body:input.message,
                    confirmLabel:input.destructive?'Delete':'Continue',
                    confirmClass:input.destructive?'btn-danger':'btn-primary',
                    confirm:()=>{settle(true);},cancel:()=>{settle(false);},dismiss:()=>{settle(false);},
                },{onClose:()=>settle(false)});
            }catch(error){this.pending=null;throw error;}
        });
    }
    notify(message,severity='info') {
        if(typeof message!=='string'||!['info','success','warning','error'].includes(severity))throw this.error('VALIDATION_FAILED');
        let close;
        close=this.notification.add(message,{type:severity==='error'?'danger':severity,autocloseDelay:5000,
            onClose:()=>this.notices.delete(close)});
        this.notices.add(close);
    }
    setCommands(entries) {
        for(const remove of this.commands)remove();
        this.commands=entries.map(entry=>this.command.add(entry.name,async()=>{
            // A palette may have cached an old entry before its scope retired.
            // Recheck the mount and authority before invoking its callback.
            if(!entry.isAvailable())return;
            await entry.action();
        },{category:'mp_platform',global:true,isAvailable:entry.isAvailable}));
    }
    openCommands(placeholder) {
        this.command.openPalette({
            providers:[{provide:(env,options)=>this.provider.provide(env,options).filter(command=>command.category==='mp_platform')}],
            configByNamespace:{default:{categories:['mp_platform'],categoryNames:{mp_platform:'Platform'},placeholder,debounceDelay:0}},
        });
    }
    clear() {
        // Every native view/plugin mounted by this root shares its current
        // identity/workspace. None of its dialogs may survive that boundary.
        const pending=this.pending;this.pending=null;pending?.resolve(false);
        pending?.close?.();
        this.dialog.closeAll();
        for(const close of [...this.notices])close();this.notices.clear();
        for(const remove of this.commands)remove();this.commands=[];
    }
}
