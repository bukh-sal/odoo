import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const source=await readFile(new URL('../platform_addons/mp_shell/static/src/native_interactions.js',import.meta.url),'utf8');
const {NativeInteractions}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));

function fixture() {
    const dialogs=[],notices=[],commands=[];
    const dialog={add:(Component,props,options)=>{
        const entry={Component,props,options,closed:false};dialogs.push(entry);
        entry.close=()=>{entry.closed=true;options.onClose();};return entry.close;
    },closeAll:()=>{for(const entry of dialogs)entry.close();}};
    const notification={add:(message,options)=>{
        const entry={message,options,closed:false};notices.push(entry);
        return ()=>{entry.closed=true;options.onClose();};
    }};
    const command={add:(name,action,options)=>{
        const entry={name,action,options,removed:false};commands.push(entry);return ()=>entry.removed=true;
    },openPalette:config=>command.config=config};
    const provider={provide:()=>[{category:'mp_platform',name:'Settings'},{category:'unrelated',name:'System action'}]};
    const ConfirmationDialog=class {};
    const error=code=>Object.assign(new Error(code),{code});
    const adapter=new NativeInteractions({dialog,notification,command,provider,ConfirmationDialog,error});
    return {adapter,dialogs,notices,commands,command,ConfirmationDialog};
}

test('native confirmation maps destructive labels and resolves once on confirm',async()=>{
    const {adapter,dialogs,ConfirmationDialog}=fixture();
    const result=adapter.confirm({title:'<unsafe>',message:'<img src=x>',destructive:true});
    assert.equal(dialogs[0].Component,ConfirmationDialog);
    assert.equal(dialogs[0].props.body,'<img src=x>'); // strings, never markup wrappers
    assert.equal(dialogs[0].props.confirmLabel,'Delete');assert.equal(dialogs[0].props.confirmClass,'btn-danger');
    assert.throws(()=>adapter.confirm({title:'Other',message:'Other'}),{code:'CONFLICT'});
    dialogs[0].props.confirm();dialogs[0].close();assert.equal(await result,true);
});
test('native cancel, Escape/dismiss and external close all settle false',async()=>{
    for(const method of ['cancel','dismiss','close']) {
        const {adapter,dialogs}=fixture();const result=adapter.confirm({title:'Leave',message:'Discard?'});
        if(method==='close')dialogs[0].close();else dialogs[0].props[method]();
        assert.equal(await result,false);
    }
});
test('retiring cancels pending confirmation and stale callbacks cannot authorize',async()=>{
    const {adapter,dialogs}=fixture();const first=adapter.confirm({title:'Old',message:'Old scope'});
    adapter.clear();assert.equal(await first,false);assert.equal(dialogs[0].closed,true);
    const second=adapter.confirm({title:'New',message:'New scope'});
    dialogs[0].props.confirm();dialogs[1].props.cancel();assert.equal(await second,false);
});
test('native notifications retain severity and plain text, clean up on scope retirement',()=>{
    const {adapter,notices}=fixture();
    for(const severity of ['info','success','warning','error'])adapter.notify('<script>plain text</script>',severity);
    assert.deepEqual(notices.map(n=>n.options.type),['info','success','warning','danger']);
    assert.equal(notices[0].message,'<script>plain text</script>');
    adapter.clear();assert.ok(notices.every(n=>n.closed));assert.equal(adapter.notices.size,0);
    assert.throws(()=>adapter.notify({},'info'),{code:'VALIDATION_FAILED'});
});
test('native command registrations retire and cached commands recheck current authority',async()=>{
    const {adapter,commands,command}=fixture();let active=true,calls=0;
    adapter.setCommands([{name:'Export',isAvailable:()=>active,action:()=>calls++}]);
    await commands[0].action();assert.equal(calls,1);active=false;
    await commands[0].action();assert.equal(calls,1);
    adapter.setCommands([{name:'Settings',isAvailable:()=>true,action:()=>{}}]);assert.equal(commands[0].removed,true);
    adapter.openCommands('Commands');
    assert.deepEqual(command.config.providers[0].provide().map(c=>c.name),['Settings']);
    assert.equal(command.config.FooterComponent,undefined); // no unrelated namespace shortcuts
    adapter.clear();assert.ok(commands.every(c=>c.removed));
});
test('ordinary confirm does not use destructive appearance and failed add rejects',async()=>{
    const {adapter,dialogs}=fixture();const result=adapter.confirm({title:'Continue',message:'Continue?'});
    assert.equal(dialogs[0].props.confirmClass,'btn-primary');adapter.clear();assert.equal(await result,false);
    adapter.dialog.add=()=>{throw new Error('native failure');};
    await assert.rejects(adapter.confirm({title:'Continue',message:'Continue?'}),/native failure/);
    assert.equal(adapter.pending,null);
});
