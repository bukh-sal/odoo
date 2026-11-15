import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';

const read = name => readFile(new URL('../framework_addons/web/static/src/' + name, import.meta.url), 'utf8');
const clean = source => source.replace(/^import .*;\r?\n/gm, '').replace(/^export /gm, '');
const preferenceSource = clean(await read('interface/context_preference.js'));
function fixture({uid = 6, key = 'org.example.partners', unavailable = false} = {}) {
    const values = new Map(), writes = [], listeners = [], effects = [], components = [];
    const storage = {
        getItem(name) { if (unavailable) throw Error('blocked'); return values.get(name) ?? null; },
        setItem(name, value) { if (unavailable) throw Error('blocked'); writes.push([name, value]); values.set(name, value); },
    };
    const bus = new EventTarget(); bus.trigger = (name, detail) => bus.dispatchEvent(new CustomEvent(name, {detail}));
    const window = new EventTarget(), user = {userId: uid}; let currentKey = key;
    const module = new Function('useComponent', 'useEffect', 'useExternalListener', 'useState', 'browser', 'user', 'window',
        preferenceSource + ';return {contextPreferenceKey,readContextCollapsed,writeContextCollapsed,useContextPreference};')(
        () => ({env: {bus}}), (fn, deps) => effects.push({fn, deps}),
        (target, name, fn) => { target.addEventListener(name, fn); listeners.push([target, name, fn]); },
        value => value, {localStorage: storage}, user, window);
    return {module, values, writes, user, bus, window, storage,
        key: value => {currentKey = value;},
        mount: () => { const owner = module.useContextPreference(() => currentKey); components.push(owner); return owner; },
        flush: () => effects.forEach(effect => effect.fn()),
        close: () => listeners.forEach(([target, name, fn]) => target.removeEventListener(name, fn)),
    };
}
test('sidebar preference stores only a boolean scoped to authenticated user and stable app', () => {
    const f = fixture(), owner = f.mount();
    assert.equal(owner.collapsed, false); assert.deepEqual(f.writes, []);
    owner.toggle(); assert.equal(owner.collapsed, true);
    assert.deepEqual(f.writes, [['mp.context.v1:6:org.example.partners', 'true']]);
    assert.equal(f.mount().collapsed, true, 'fresh owner reloads persisted preference');
    f.key('org.example.documents'); assert.equal(owner.collapsed, false);
    owner.toggle(); f.key('org.example.partners'); assert.equal(owner.collapsed, true);
    f.user.userId = 7; assert.equal(owner.collapsed, false); f.close();
});
test('malformed values and unsafe or missing identities never restore or write a preference', () => {
    const f = fixture();
    for (const uid of [0, -1, NaN, '6', 1.2]) assert.equal(f.module.contextPreferenceKey(uid, 'app'), null);
    for (const key of ['', 'app name', '../app', '<script>', 'x'.repeat(201), null]) assert.equal(f.module.contextPreferenceKey(6, key), null);
    for (const value of ['false', '1', 'TRUE', '{}', 'null', 'true ']) {
        f.values.set('mp.context.v1:6:org.example.partners', value);
        assert.equal(f.module.readContextCollapsed(f.storage, 'mp.context.v1:6:org.example.partners'), false);
    }
    assert.equal(f.module.writeContextCollapsed(f.storage, 'app', {collapsed: true}), false);
    assert.deepEqual(f.writes, []); f.key(null);
    const owner = f.mount(); owner.toggle(); assert.equal(owner.collapsed, true); assert.deepEqual(f.writes, []); f.close();
});
test('blocked storage keeps ephemeral native/custom preference in sync and never breaks navigation', () => {
    const f = fixture({unavailable: true}), native = f.mount(), custom = f.mount();
    native.toggle(); assert.equal(native.collapsed, true); assert.equal(custom.collapsed, true);
    custom.toggle(); assert.equal(native.collapsed, false); assert.deepEqual(f.writes, []); f.close();
});
test('same-window owners and storage changes synchronize only their current scope', () => {
    const f = fixture(), first = f.mount(), second = f.mount();
    first.toggle(); assert.equal(second.collapsed, true);
    f.bus.trigger('UI:CONTEXT-PREFERENCE-CHANGED', {key: 'mp.context.v1:7:org.example.partners', collapsed: false});
    assert.equal(first.collapsed, true);
    f.values.set('mp.context.v1:6:org.example.partners', 'false');
    const event = new Event('storage'); event.key = 'mp.context.v1:6:org.example.partners'; f.window.dispatchEvent(event);
    assert.equal(first.collapsed, false); assert.equal(second.collapsed, false); f.close();
});

const geometry = new Function(clean(await read('interface/icons/lucide.js')) + ';return ICON_NODES;')();
const {Icon, iconName} = new Function('Component', 'ICON_NODES', clean(await read('interface/icon.js')) + ';return {Icon,iconName};')(
    class {constructor(props) {this.props = props;}}, geometry);
test('local icons accept semantic/explicit legacy aliases and fall back for unknown or hostile names', () => {
    for (const name of ['constructor', '__proto__', 'https://icons.invalid/pic', '<svg onload=x>', null]) assert.equal(iconName(name), 'box');
    assert.equal(iconName('fa fa-fw fa-pencil'), 'pencil');
    assert.equal(iconName('oi oi-view-list'), 'list');
    assert.equal(iconName('fa fa-sliders'), 'sliders-horizontal');
    const icon = new Icon({name: 'constructor', size: NaN});
    assert.equal(icon.nodes, geometry.box); assert.equal(icon.size, 18);
});
test('pinned geometry contains only declarative SVG shapes and attributes, never an execution or asset seam', () => {
    const tags = new Set(['path', 'line', 'polyline', 'polygon', 'rect', 'circle', 'ellipse']);
    for (const nodes of Object.values(geometry)) for (const node of nodes) {
        assert.ok(tags.has(node.tag)); assert.equal(typeof node.key, 'string');
        for (const key of Object.keys(node.attrs)) assert.ok(!/^on|href|style|src/i.test(key));
    }
});
const translation = (text, ...args) => text.replace(/%s/g, () => args.shift());
const {BreadcrumbTrail} = new Function('Component', 'Icon', '_t', clean(await read('interface/breadcrumb_trail.js')) + ';return {BreadcrumbTrail};')(class{}, Icon, translation);
const {Breadcrumbs} = new Function('Component', 'Dropdown', 'DropdownItem', 'Icon', '_t', clean(await read('search/breadcrumbs/breadcrumbs.js')) + ';return {Breadcrumbs};')(class{}, class{}, class{}, Icon, translation);
test('shared breadcrumb exposes real links and refuses active/protocol-relative destinations', () => {
    const trail = new BreadcrumbTrail();
    for (const href of ['javascript:alert(1)', '//foreign.invalid', '/\\foreign.invalid', '/\n/foreign.invalid', null, 'data:text/html,x']) assert.equal(trail.href({href}), undefined);
    assert.equal(trail.href({href: '/odoo/action-84?workspace=abc'}), '/odoo/action-84?workspace=abc');
});
test('native and shared breadcrumb delegates preserve dirty refusal and ordinary modified/new-tab links', async () => {
    for (const component of [new BreadcrumbTrail(), new Breadcrumbs()]) {
        const calls = [], item = {onSelected: async () => {calls.push('leave-refused'); return false;}};
        assert.equal(await component.select({preventDefault: () => calls.push('prevent')}, item), false);
        assert.deepEqual(calls, ['prevent', 'leave-refused']);
        for (const modifier of ['ctrlKey', 'metaKey', 'shiftKey', 'altKey', 'button']) {
            component.select({[modifier]: true, preventDefault: () => assert.fail()}, {onSelected: () => assert.fail()});
        }
    }
});
