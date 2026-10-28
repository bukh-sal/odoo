// Disposable source-function experiment, not a browser or complete WebClient test.
// Execute the pinned upstream function unchanged; stub only its enclosing services.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, relative } from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = resolve(process.argv[process.argv.indexOf('--output') + 1] || '');
assert(process.argv.includes('--output'));
assert(relative(resolve(root, 'docs/evidence/G5'), output).match(/^[^.][^:]*$/));
assert(!existsSync(output), 'Use fresh evidence; never overwrite an experiment');
const sourcePath = 'addons/web/static/src/webclient/actions/action_service.js';
const source = readFileSync(resolve(root, sourcePath), 'utf8');
const start = source.indexOf('    function _getViewInfo(');
const end = source.indexOf('\n    /**', start);
assert(start > 0 && end > start);
const functionSource = source.slice(start, end).trim();
assert(functionSource.endsWith('}'));
const calls = [];
const getViewInfo = new Function('_getView', 'switchView', 'doAction', 'shallowEqual', 'pushState',
    `${functionSource}\nreturn _getViewInfo;`)(
    type => type === 'form',
    (...args) => calls.push({ service: 'switchView', args }),
    (...args) => calls.push({ service: 'doAction', args }),
    (a, b) => Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(k => a[k] === b[k]),
    () => calls.push({ service: 'pushState' }),
);
const views = [
    { type: 'list', multiRecord: true, icon: 'oi-view-list', display_name: 'List' },
    { type: 'form', multiRecord: false, icon: 'fa-file', display_name: 'Form' },
];
const action = { id: 101, target: 'current', res_model: 'mp.note', context: {},
    views: [[false, 'list'], [false, 'form']], name: 'Notes' };
const platform = [];
const props = {
    selectRecord: id => platform.push({ route: '/app/notes?note=PUBLIC_UUID', id }),
    createRecord: () => platform.push({ route: '/app/notes?new=1' }),
    saveRecord: record => platform.push({ service: 'documents.update', record }),
    onDiscard: () => platform.push({ route: '/app/notes' }),
    updateActionState: () => platform.push({ route: 'platform-owned-state' }),
};
const info = getViewInfo(views[0], action, views, props);
assert.notEqual(info.props.selectRecord, props.selectRecord);
assert.notEqual(info.props.createRecord, props.createRecord);
info.props.selectRecord(42);
info.props.createRecord();
assert.equal(platform.length, 0, 'Public-ID/workspace route callbacks are bypassed');
assert.deepEqual(calls.slice(0, 2).map(c => [c.service, c.args[0], c.args[1].resId]),
    [['switchView', 'form', 42], ['switchView', 'form', false]]);
const form = getViewInfo(views[1], action, views, { ...props, resId: 42 });
assert.equal(form.props.saveRecord, props.saveRecord, 'CAS/idempotency callback can survive this seam');
assert.equal(form.props.onDiscard, props.onDiscard);
assert.notEqual(info.props.updateActionState, props.updateActionState);
info.props.updateActionState({ isMounted: true }, { resId: 42 });
assert.equal(calls.at(-1).service, 'pushState');
const report = {
    result: 'completed', utc: new Date().toISOString(),
    git_base: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    node: process.version,
    method: 'Unmodified pinned _getViewInfo executed in isolation with recorded closure-service stubs',
    findings: {
        public_route_select_callback_retained: false,
        public_route_create_callback_retained: false,
        platform_action_state_callback_retained: false,
        custom_save_callback_retained: true,
        custom_discard_callback_retained: true,
        observed_native_calls: calls,
    },
    decision: 'Retain existing native View adapter for R1; direct ActionContainer/options.props substitution does not preserve route ownership.',
    limits: [
        'No real browser, router, workspace authorization, save, dirty-navigation or session integration executed.',
        'Does not prove all possible WebClient integrations are incompatible; deeper wrapping or a client-action adapter remains possible.',
        'No live site, image, database, published package, upstream source or platform runtime changed.',
    ],
    source_sha256: Object.fromEntries([sourcePath,
        'addons/web/static/src/webclient/actions/action_container.js',
        'platform_addons/mp_shell/static/src/host.js',
        'tools/probe_native_action_seam.mjs'].map(path => [path,
        createHash('sha256').update(readFileSync(resolve(root, path))).digest('hex')])),
};
mkdirSync(output, { recursive: true });
writeFileSync(resolve(output, 'action-seam.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ result: report.result, decision: report.decision, evidence: output }));
