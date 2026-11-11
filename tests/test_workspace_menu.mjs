import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../framework_addons/mp_core/static/src/workspace_menu.js', import.meta.url), 'utf8');
const a = '218464f2-b2e0-466a-8310-0a78fc0bcb73';
const b = 'f89466f6-19cd-46d2-9685-60f8fa89790e';
let serial = 0;
async function fixture({ rows = [{ id: a, name: 'A' }, { id: b, name: '<script>B</script>' }], ok = true,
    error = false, stock = true, custom = false, search = `?workspace=${a}`, timeout = false } = {}) {
    const callbacks = [], registrations = [], calls = [], opened = [], timers = [], cleared = [];
    const browser = {
        location: { search },
        setTimeout: (callback, ms) => { timers.push({ callback, ms }); return 12; },
        clearTimeout: (id) => cleared.push(id),
        open: (...args) => opened.push(args),
        fetch: async (...args) => {
            calls.push(args);
            if (timeout) timers[0].callback();
            if (error || args[1].signal.aborted) throw new Error('Unavailable');
            return { ok, json: async () => ({ data: rows }) };
        },
    };
    globalThis.workspaceTest = {
        Component: class {}, onWillStart: (callback) => callbacks.push(callback),
        xml: (strings) => strings.join(''), browser, Dropdown: class {}, DropdownItem: class {}, _t: (s) => s,
        registry: { category: (category) => ({ add: (...args) => registrations.push({ category, args }) }) },
        session: { mp_stock_profile: stock }, odoo: { __mp_client_release__: custom },
    };
    const imports = 'const { Component, onWillStart, xml, browser, Dropdown, DropdownItem, _t, registry, session, odoo } = globalThis.workspaceTest;';
    const transformed = source.replace(/^import .*;\r?\n/gm, '');
    const { WorkspaceMenu } = await import('data:text/javascript;base64,' + Buffer.from(imports + transformed + `\n//case${serial++}`).toString('base64'));
    const menu = new WorkspaceMenu(); menu.setup(); await callbacks[0]();
    return { menu, calls, opened, registrations, browser, timers, cleared };
}

test('clean stock navigation registers without an optional app or shell', async () => {
    const f = await fixture();
    assert.equal(f.registrations.length, 1);
    assert.equal(f.registrations[0].category, 'systray');
    assert.equal(f.registrations[0].args[0], 'mp_stock_workspace');
    assert.equal(f.menu.label, 'A');
    assert.doesNotMatch(source, /mp_shell|mp_example|dev\.local\.partners|org\.example/);
    assert.match(f.menu.constructor.template, /t-esc="space.name"/);
    assert.equal((await fixture({ stock: false })).registrations.length, 0);
    assert.equal((await fixture({ custom: true })).registrations.length, 0);
});

test('workspace list is current, uncached and bounded on network failure', async () => {
    const f = await fixture();
    assert.equal(f.calls.length, 1);
    assert.equal(f.calls[0][0], '/api/v1/workspaces');
    assert.equal(f.calls[0][1].cache, 'no-store');
    assert.equal(f.timers[0].ms, 10000);
    assert.deepEqual(f.cleared, [12]);
    for (const options of [{ ok: false }, { error: true }, { timeout: true }, { rows: null },
        { rows: [{ id: a, name: 'A' }, { id: a, name: 'duplicate' }] },
        { rows: [{ id: '../arbitrary', name: 'bad' }] }, { rows: [{ id: a }] }]) {
        const failed = await fixture(options);
        assert.deepEqual(failed.menu.workspaces, []);
        assert.equal(failed.menu.emptyMessage, 'Could not load workspaces');
        assert.deepEqual(failed.cleared, [12]);
        failed.menu.open(a); assert.deepEqual(failed.opened, []);
    }
});

test('new-tab selection preserves the old form URL and drops old action/record context', async () => {
    const search = `?workspace=${a}&action=123&id=42`;
    const f = await fixture({ search });
    f.menu.open(b);
    assert.deepEqual(f.opened, [[`/odoo?workspace=${b}`, '_blank', 'noopener']]);
    assert.equal(f.browser.location.search, search);
    assert.equal(f.menu.selected.id, a);
    f.menu.open('https://foreign.invalid/');
    assert.equal(f.opened.length, 1);
    f.menu.open(a, true);
    assert.equal(f.opened[1][0], `/odoo/action-mp_core.action_job_history?workspace=${a}`);
});

test('missing, revoked or unknown selection is never silently replaced with another workspace', async () => {
    for (const search of ['', '?workspace=unavailable']) {
        const f = await fixture({ search });
        assert.equal(f.menu.selected, undefined);
        assert.equal(f.menu.label, 'Choose workspace');
        assert.deepEqual(f.opened, []);
    }
    const f = await fixture({ rows: [] });
    assert.equal(f.menu.emptyMessage, 'No workspaces available');
    assert.deepEqual(f.opened, []);
});

test('optional reference tools use their own registry entry without another workspace selector', async () => {
    const optional = await readFile(new URL('../framework_addons/mp_shell/static/src/stock_workspace_menu.js', import.meta.url), 'utf8');
    assert.match(optional, /add\("mp_reference_tools"/);
    assert.doesNotMatch(optional, /add\("mp_stock_workspace"|t-foreach="workspaces"/);
    assert.match(optional, /mp_example_notes/);
});
