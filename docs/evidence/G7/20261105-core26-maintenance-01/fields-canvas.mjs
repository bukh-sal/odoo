import path from 'node:path';
import { browserRuntime } from './browser_runtime.mjs';

const b = await browserRuntime(path.join(process.cwd(), '.local/g7-ui-core26-01/fields-canvas'));
const workspace = b.input.fixture.workspaces.A;
const board = b.before.mp_example_canvas_board[0];
const suffix = '?workspace=' + workspace.public_id;
const settingsURL = b.input.base + '/app/settings' + suffix;
const canvasURL = b.input.base + '/app/org.example.canvas/' + suffix;
const observations = {};
const active = () => b.evaluate(`({
    name: document.activeElement.getAttribute('aria-label') || document.activeElement.textContent.trim().slice(0, 90),
    tag: document.activeElement.tagName,
})`);
async function tabTo(name) {
    for (let i = 0; i < 90; i++) {
        if ((await active()).name === name) return;
        await b.key('Tab', 'Tab', 9);
    }
    throw Error('Keyboard cannot reach ' + name);
}
async function nav(url, selector) {
    await b.navigate(url);
    await b.until(() => b.evaluate(`!!document.querySelector(${JSON.stringify(selector)})`), selector);
}
async function check(name, observe) {
    observations[name] = await observe();
}

try {
    await nav(settingsURL, '#mp_workspace_name');
    const label = await b.ax('#mp_workspace_name');
    await b.evaluate('document.querySelector("#mp_workspace_name").focus()');
    await b.key('a', 'KeyA', 65, 2);
    await b.key('Backspace', 'Backspace', 8);
    const validation = await b.evaluate(`(() => {
        const field = document.querySelector('#mp_workspace_name');
        if (!field.validity.valueMissing) throw Error('Expected empty required field');
        let submitted = false;
        const guard = event => { submitted = true; event.preventDefault(); event.stopImmediatePropagation(); };
        field.form.addEventListener('submit', guard, true);
        try { field.form.requestSubmit(); } finally { field.form.removeEventListener('submit', guard, true); }
        return { valueMissing: field.validity.valueMissing, focused: field === document.activeElement,
            hasMessage: !!field.validationMessage, submitted };
    })()`);
    if (label[0]?.name !== 'Workspace name' || !validation.focused ||
        !validation.hasMessage || validation.submitted) throw Error('Required field association failed');
    observations.requiredField = { label, ...validation };
 await check('05-Canvas-keyboard-discard',async()=>{await nav(canvasURL,'.mp_canvas_card');await b.evaluate(`document.querySelector('.mp_canvas select[aria-label^="Move card"]').focus()`);const initial=await b.evaluate(`document.querySelector('.mp_canvas select[aria-label^="Move card"]').value`);await b.key('ArrowDown','ArrowDown',40);const moved=await b.evaluate(`document.querySelector('.mp_canvas select[aria-label^="Move card"]').value`),afterMove=await active();await tabTo('Reload saved board');await b.key('Enter','Enter',13);await b.until(()=>b.evaluate(`!!document.querySelector('.modal .modal-content')`),'Unsaved board discard confirmation');const title=await b.evaluate(`document.querySelector('.modal .modal-title').textContent.trim()`);if(title!=='Unsaved board')throw Error('Unexpected discard dialog');await tabTo('Continue');await b.key('Enter','Enter',13);await b.until(()=>b.evaluate(`!document.querySelector('.modal .modal-content')&&document.querySelector('.mp_canvas select[aria-label^="Move card"]').value===${JSON.stringify(initial)}`),'original lane restored');await b.evaluate(`document.querySelector('.mp_canvas input[aria-label="Board name"]').focus()`);await b.key('a','KeyA',65,2);await b.rpc('Input.insertText',{text:'Mixed long title عنوان طويل '.repeat(3)});const longInput=await b.evaluate(`({length:document.querySelector('.mp_canvas input[aria-label="Board name"]').value.length,width:document.querySelector('.mp_canvas input[aria-label="Board name"]').getBoundingClientRect().width,root_width:document.querySelector('.mp_canvas').clientWidth})`);await tabTo('Reload saved board');await b.key('Enter','Enter',13);await b.until(()=>b.evaluate(`!!document.querySelector('.modal .modal-title')`),'long input discard confirmation');if(await b.evaluate(`document.querySelector('.modal .modal-title').textContent.trim()`)!=='Unsaved board')throw Error('Unexpected long-input dialog');await tabTo('Continue');await b.key('Enter','Enter',13);await b.until(()=>b.evaluate(`document.querySelector('.mp_canvas input[aria-label="Board name"]').value===${JSON.stringify(board.name)}`),'saved board name restored');await b.screenshot('Canvas-keyboard.png');if(initial===moved)findings.push({check:'Canvas_keyboard_move',reason:'Keyboard move ineffective'});return {initial,moved,afterMove,longInput,discard_confirmed_twice:true,server_save_clicked:false,original_name_restored:true};});

    await tabTo('Settings');
    await b.key('Enter', 'Enter', 13);
    await b.until(() => b.evaluate('!!document.querySelector("#mp_workspace_name")'), 'keyboard exit to Settings');
    observations.keyboardExitToSettings = true;
    observations.foreignRequests = b.blocked.filter(entry => entry.path !== '/mp-ui09-network-probe');
    observations.runtimeExceptions = b.exceptions;
    if (observations.foreignRequests.length || observations.runtimeExceptions.length) throw Error('Unexpected browser activity');
    await b.save('fields-canvas.json', observations);
    console.log(JSON.stringify({result:'required_field_canvas_keyboard_and_exit_passed'}));
} finally {
    await b.close();
}
