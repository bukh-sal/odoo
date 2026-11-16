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
    const focused = [], effects = [], refs = {}, ui = {isSmall:true}, providers=new Map(),dialogs=[];
    const blank = class {};
    const module = await load('../framework_addons/web/static/src/webclient/shell/shell.js', {
        Icon: blank, useSubEnv: () => {}, useContextPreference: () => ({collapsed:false,toggle(){}}),
        useRailPreferences: apps => ({get apps(){return apps();},pins:null,save:()=>true}),
        railAppId: app => 'menu:'+app.id, contextTone: tone => ['amber','green','blue','violet','slate'].includes(tone)?tone:'neutral',
        RailCustomization: blank, WorkspaceHelp: blank,
        Component: blank, Dialog: class {static props = {};}, Dropdown: blank, DropdownItem: blank,
        xml: strings => strings.join(''), window: {}, document: {activeElement:null},
        ErrorHandler: blank, UserMenu: blank, PageHeader: blank, StatusMessage: blank, ContextNav: blank,
        useEffect: fn => effects.push(fn), useExternalListener: () => {}, useBus: () => {},
        useState: value => value, useRef: name => refs[name] = {el: {focus: () => focused.push(name), contains:()=>false}},
        useService: name => ({menu:{unavailable:false},action:{},command:{},dialog:{add:(...args)=>dialogs.push(args)},ui})[name],
        registry:{category:name=>name==='context_navigation'?{contains:key=>providers.has(key),get:key=>providers.get(key)}:{contains:()=>false}}, browser:{location:{search:'?workspace=scoped-workspace'}}, user:{}, _t:value=>value,
    });
    const shell = new module.Shell(); shell.env = {bus:{},isSmall:true}; shell.setup();
    return {shell, ui, focused, effects, refs,providers,dialogs,Component:blank};
}

test('optional context selects only current accessible app, supplies normal menu context and bounds its tone',async()=>{
    const f=await shellFixture();const app={id:1,pluginID:'example.owner',name:'Directory',actionID:10};
    class OwnerContext extends f.Component {}
    f.providers.set(app.pluginID,{Component:OwnerContext,tone:'amber'});
    let available=[app];f.shell.menu={getApps:()=>available,getCurrentApp:()=>app,getMenuAsTree:()=>({childrenTree:[]})};
    f.shell.action={};assert.equal(f.shell.contextProvider.Component,OwnerContext);assert.equal(f.shell.contextProvider.tone,'amber');
    const props=f.shell.contextProviderProps;assert.equal(props.contextTitle,'Directory');assert.equal(props.groups[0].items[0].menu,app);assert.equal(props.workspaceId,'scoped-workspace');
    f.providers.set(app.pluginID,{Component:()=>{},tone:'url(evil)'});assert.deepEqual(f.shell.contextProvider,{Component:null,tone:'neutral'});
    available=[];assert.equal(f.shell.current,undefined);assert.deepEqual(f.shell.contextProvider,{Component:null,tone:'neutral'});
});

test('sidebar customization uses fresh available IDs and cannot save after access becomes unavailable',async()=>{
    const f=await shellFixture();let available=[{id:1},{id:2}],saved=[];
    f.shell.menu={getApps:()=>available,unavailable:false};f.shell.railPreference={pins:null,save:pins=>{saved.push(pins);return true;}};
    assert.equal(f.shell.openRailSettings(),true);const props=f.dialogs[0][1];
    available=[{id:2}];assert.equal(props.onSave(['menu:1','menu:2']),true);assert.deepEqual(saved,[['menu:2']]);
    f.shell.menu.unavailable=true;assert.equal(props.onSave([]),false);assert.equal(f.shell.openRailSettings(),false);assert.equal(saved.length,1);assert.equal(f.dialogs.length,1);
});

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

test('shared native context keeps filtered menu groups and delegates normal action navigation',async()=>{
    const f=await shellFixture(),calls=[];
    const app={id:1,pluginID:'example.owner',name:'Directory',actionID:10,appIcon:'users'};
    const child={id:3,name:'People',actionID:12,contextIcon:'users',childrenTree:[]};
    const tree={childrenTree:[{id:2,name:'Directory',childrenTree:[child]},
        {id:4,name:'Empty filtered group',childrenTree:[]}]};
    f.shell.menu={getApps:()=>[app],getCurrentApp:()=>app,getMenuAsTree:()=>tree,selectMenu:async m=>calls.push(m)};
    f.shell.action={currentController:{action:{id:12}}};
    const groups=f.shell.contextGroups;
    assert.equal(groups.length,1);assert.equal(groups[0].items.length,2);
    const group=groups[0].items[1],row=group.children[0];
    assert.equal(group.label,'Directory');assert.equal(group.href,undefined);
    assert.equal(row.label,'People');assert.equal(row.icon,'users');assert.equal(row.current,true);
    assert.match(row.href,/action-12\?workspace=scoped-workspace$/);
    assert.equal(row.menu,child);
    let prevented=0;await f.shell.selectContext(row,{button:0,preventDefault(){prevented++;}});
    assert.equal(prevented,1);assert.deepEqual(calls,[child]);
    await f.shell.selectContext(row,{button:0,ctrlKey:true,preventDefault(){throw Error('Keep native modified link');}});
    assert.deepEqual(calls,[child]);
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
