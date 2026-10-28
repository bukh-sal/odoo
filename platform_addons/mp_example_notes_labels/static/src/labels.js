/** Trusted compiled contribution. Catalog strings never become templates/code. */
import { registry } from '@web/core/registry';

registry.category('mp.commands').add('org.example.notes_labels:command:set_labels',({host,input})=>host.services.call('labels','set_labels',input,{idempotencyKey:'labels-'+crypto.randomUUID()}));

registry.category('mp.slot_actions').add('org.example.notes_labels:action:set_labels',async({element,host,context,signal})=>{
    const note=await host.services.call('documents','get',{note_id:context.note_id},{signal});
    if(signal.aborted)return null;
    const dialog=document.createElement('dialog');dialog.className='mp_label_dialog';
    const title=document.createElement('h2');title.id='mp_labels_title';title.textContent='Edit note labels';dialog.setAttribute('aria-labelledby',title.id);
    const form=document.createElement('form');const label=document.createElement('label');label.textContent='Labels, one per line';
    const input=document.createElement('textarea');input.id='mp_labels_input';input.rows=7;input.value=note.labels.join('\n');label.htmlFor=input.id;
    const help=document.createElement('p');help.textContent='Up to 30 unique labels. Changes also require the current note revision.';
    const alert=document.createElement('p');alert.setAttribute('role','alert');
    const save=document.createElement('button');save.type='submit';save.textContent='Save labels';
    const cancel=document.createElement('button');cancel.type='button';cancel.textContent='Cancel';
    form.append(label,input,help,alert,save,cancel);dialog.append(title,form);element.append(dialog);
    return new Promise(resolve=>{
        let finished=false;const controller=new AbortController();
        const finish=value=>{if(finished)return;finished=true;controller.abort();signal.removeEventListener('abort',aborted);dialog.close();dialog.remove();resolve(value);};
        const aborted=()=>finish(null);signal.addEventListener('abort',aborted,{once:true});
        cancel.addEventListener('click',()=>finish(null),{signal:controller.signal});
        dialog.addEventListener('cancel',event=>{event.preventDefault();finish(null);},{signal:controller.signal});
        form.addEventListener('submit',async event=>{
            event.preventDefault();save.disabled=true;
            try{
                const labels=input.value.split('\n').map(v=>v.trim()).filter(Boolean);
                const saved=await host.commands.execute('org.example.notes_labels:command:set_labels',{note_id:context.note_id,expected_revision:context.expected_revision,labels});
                finish(saved);
            }catch(error){if(!finished){alert.textContent=error.code==='CONFLICT'?'This note changed. Cancel and reload before trying again.':error.message||'Labels could not be saved';save.disabled=false;}}
        },{signal:controller.signal});
        dialog.showModal();input.focus();
    });
});
