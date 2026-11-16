import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

let serial = 0;
async function load(relative, fixture) {
    const source = (await readFile(new URL(relative, import.meta.url), 'utf8')).replace(/^import .*;\r?\n/gm, '');
    globalThis.renderedShellFixture = fixture;
    const names = Object.keys(fixture).join(',');
    return import('data:text/javascript;base64,' + Buffer.from(`const {${names}}=globalThis.renderedShellFixture;\n` + source).toString('base64') + '#' + serial++);
}

async function shellFixture() {
    const focused = [], effects = [], refs = {}, ui = {isSmall:true};
    const blank = class {};
    const module = await load('../framework_addons/web/static/src/webclient/shell/shell.js', {
        Icon: blank, useSubEnv: () => {}, useContextPreference: () => ({collapsed:false,toggle(){}}),
        Component: blank, Dialog: class {static props = {};}, Dropdown: blank, DropdownItem: blank,
        xml: strings => strings.join(''), window: {}, document: {activeElement:null},
        ErrorHandler: blank, UserMenu: blank, PageHeader: blank, StatusMessage: blank,
        useEffect: fn => effects.push(fn), useExternalListener: () => {}, useBus: () => {},
        useState: value => value, useRef: name => refs[name] = {el: {focus: () => focused.push(name), contains:()=>false}},
        useService: name => ({menu:{unavailable:false},action:{},command:{},dialog:{add:()=>{}},ui})[name],
        registry:{category:()=>({contains:()=>false})}, browser:{}, user:{}, _t:value=>value,
    });
    const shell = new module.Shell(); shell.env = {bus:{},isSmall:true}; shell.setup();
    return {shell, ui, focused, effects, refs};
}

test('native context opening moves focus into its mounted navigation', async () => {
    const f = await shellFixture();
    f.shell.toggleContext();
    f.effects.forEach(effect => effect());
    assert.equal(f.shell.state.contextOpen, true);
    assert.deepEqual(f.focused, ['context']);
});

test('workspace presentation region partitions currently displayed utilities without caching them', async () => {
    const f = await shellFixture();
    const workspace = {key: 'workspace', region: 'workspace'};
    const ordinary = {key: 'available-tool'};
    let entries = [ordinary, workspace];
    Object.defineProperty(f.shell, 'utilities', {get: () => entries});
    assert.deepEqual(f.shell.workspaceUtilities, [workspace]);
    assert.deepEqual(f.shell.trailingUtilities, [ordinary]);
    entries = [];
    assert.deepEqual(f.shell.workspaceUtilities, []);
    assert.deepEqual(f.shell.trailingUtilities, []);
});

test('desktop context toggle restores focus to the newly mounted reopen or header control', async () => {
    const f = await shellFixture();
    f.ui.isSmall = false;
    const preference = f.shell.contextPreference;
    preference.toggle = () => { preference.collapsed = !preference.collapsed; };
    for (const expected of [true, false]) {
        f.shell.toggleContext();
        f.refs.contextTrigger.el = {focus: () => f.focused.push('new-trigger-' + expected)};
        f.effects.forEach(effect => effect());
        assert.equal(f.shell.contextCollapsed, expected);
    }
    assert.deepEqual(f.focused, ['new-trigger-true', 'new-trigger-false']);
});

test('Escape closes an open native context and returns focus to the opener', async () => {
    const f = await shellFixture(); f.shell.state.contextOpen = true;
    const calls = [];
    f.shell.closeContext({key:'Escape',defaultPrevented:false,preventDefault:()=>calls.push('prevent'),stopPropagation:()=>calls.push('stop')});
    assert.equal(f.shell.state.contextOpen, false);
    assert.deepEqual(calls, ['prevent','stop']);
    assert.deepEqual(f.focused, ['contextTrigger']);
});

test('nested handled Escape and closed context do not steal focus or keys', async () => {
    const f = await shellFixture(); const calls=[];
    const event={key:'Escape',defaultPrevented:true,preventDefault:()=>calls.push('prevent'),stopPropagation:()=>calls.push('stop')};
    f.shell.state.contextOpen=true; f.shell.closeContext(event);
    assert.equal(f.shell.state.contextOpen,true);
    f.shell.state.contextOpen=false; f.shell.closeContext({...event,defaultPrevented:false});
    assert.deepEqual(f.focused,[]); assert.deepEqual(calls,[]);
});

test('native sidebar follows service breakpoint changes and retains desktop preference', async () => {
    const f=await shellFixture();
    f.ui.isSmall=false;
    assert.equal(f.shell.env.isSmall,true);
    assert.equal(f.shell.contextExpanded,true);
    f.shell.contextPreference.collapsed=true;
    assert.equal(f.shell.contextCollapsed,true);
    f.ui.isSmall=true;
    assert.equal(f.shell.contextExpanded,false);
    f.shell.toggleContext();assert.equal(f.shell.contextExpanded,true);
    f.ui.isSmall=false;f.effects.forEach(effect=>effect());
    assert.equal(f.shell.state.contextOpen,false);
    assert.equal(f.shell.contextPreference.collapsed,true);
});

async function appearanceFixture({dark=false,canLeave=true}={}) {
    const entries = new Map(), calls=[];
    await load('../framework_addons/web/static/src/webclient/user_menu/user_menu_items.js', {
        Component:class{}, markup:strings=>strings.join(''), isMacOS:()=>false, _t:value=>value,
        rpc:()=>{}, user:{}, session:{},
        registry:{category:()=>({add(key,value){entries.set(key,value);return this;}})},
        cookie:{get:()=>dark?'dark':undefined,set:(...args)=>calls.push(['cookie',...args])},
        clearUncommittedChanges:async()=>{calls.push(['leave']);return canLeave;},
        browser:{location:{reload:()=>calls.push(['reload'])}},
    });
    return {entries,calls};
}

test('appearance change respects the existing leave guard before cookie or reload',async()=>{
    const f=await appearanceFixture({canLeave:false});
    const item=f.entries.get('appearance')({});
    await item.callback();
    assert.deepEqual(f.calls,[['leave']]);
});

test('appearance selects normal light/dark assets through the existing cookie',async()=>{
    for(const dark of [false,true]) {
        const f=await appearanceFixture({dark});
        const item=f.entries.get('appearance')({});
        assert.equal(item.description,dark?'Use light appearance':'Use dark appearance');
        await item.callback();
        assert.deepEqual(f.calls,[['leave'],['cookie','color_scheme',dark?'light':'dark'],['reload']]);
    }
});

test('owned account menu does not register unsupported vendor account/support actions',async()=>{
    const f=await appearanceFixture();
    assert.equal(f.entries.has('odoo_account'),false);
    assert.equal(f.entries.has('support'),false);
    assert.equal(f.entries.has('preferences'),true);
    assert.equal(f.entries.has('log_out'),true);
});
