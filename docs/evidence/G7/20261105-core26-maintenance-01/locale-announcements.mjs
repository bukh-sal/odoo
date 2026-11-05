import path from 'node:path';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { readFile } from 'node:fs/promises';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import { browserRuntime } from './browser_runtime.mjs';

const nativeEvents = process.argv.includes('--native-events');
const output = path.join(process.cwd(), '.local/g7-ui-core26-01', nativeEvents ? 'native-events-03' : 'baseline');
const browser = await browserRuntime(output, { forceAccessibility: nativeEvents });
const workspace = browser.input.fixture.workspaces.A;
const query = '?workspace=' + workspace.public_id;
const settings = browser.input.base + '/app/settings' + query;
const foreignNote = browser.before.mp_example_note.find(note => note.workspace_id !== workspace.id);
const alert = '.mp_main > [role=alert]';
const status = '.mp_main > p[role=status]';
let observer, observerExit;
const events = [];

async function startObserver() {
    const { pid } = JSON.parse(await readFile(path.join(output, 'process-running.json'), 'utf8'));
    observer = spawn(path.resolve('.local/toolchain/operator-python16/Scripts/python.exe'),
        ['-X', 'utf8', fileURLToPath(new URL('./watch-live-events.py', import.meta.url)), String(pid)], {
            windowsHide: true, stdio: ['pipe', 'pipe', 'inherit'],
        });
    observerExit = once(observer, 'exit');
    const lines = createInterface({ input: observer.stdout });
    lines.on('line', line => events.push(JSON.parse(line)));
    await browser.until(() => events.some(event => event.type === 'ready'), 'Win32 observer ready', 5000);
}

async function inspectRegion(selector) {
    const { result } = await browser.rpc('Runtime.evaluate', {
        expression: `document.querySelector(${JSON.stringify(selector)})`,
    });
    try {
        const { node } = await browser.rpc('DOM.describeNode', { objectId: result.objectId });
        const { nodes } = await browser.rpc('Accessibility.getPartialAXTree', {
            objectId: result.objectId, fetchRelatives: false,
        });
        const ax = nodes[0];
        const live = Object.fromEntries((ax.properties || [])
            .filter(property => ['live', 'atomic', 'relevant'].includes(property.name))
            .map(property => [property.name, property.value.value]));
        const text = await browser.evaluate(`document.querySelector(${JSON.stringify(selector)}).textContent.trim()`);
        return { id: node.backendNodeId, role: ax.role?.value, ignored: ax.ignored, live, hasText: !!text };
    } finally {
        await browser.rpc('Runtime.releaseObject', { objectId: result.objectId });
    }
}

const settingsReady = () => browser.evaluate(`!!document.querySelector("#mp_workspace_name") &&
    !document.querySelector(${JSON.stringify(status)})?.textContent.trim()`);
const memberCount = () => browser.evaluate(`({
    language: document.documentElement.lang,
    direction: document.documentElement.dir,
    count: document.querySelectorAll('.mp_members tbody tr').length,
    text: document.querySelector('.mp_members').parentElement.querySelector('h3 + p').textContent.trim(),
})`);

try {
    await browser.navigate(settings);
    await browser.until(settingsReady, 'English settings');
    await browser.rpc('Accessibility.enable');
    const english = await memberCount();
    await browser.select('#mp_shell_language', 'ar');
    await browser.until(async () => await settingsReady() &&
        /عضو|أعضاء/u.test((await memberCount()).text), 'rendered Arabic member count');
    const arabic = await memberCount();
    await browser.select('#mp_shell_language', 'en-US');
    await browser.until(async () => await settingsReady() &&
        /members?$/u.test((await memberCount()).text), 'rendered English member count');
    const readyStatus = await inspectRegion(status);
    const readyAlert = await inspectRegion(alert);
    if (nativeEvents) await startObserver();

    const loadingStarted = Date.now();
    browser.holdNextNavigation();
    await browser.clickText('.mp_root nav a', 'Notes');
    await browser.until(() => browser.held(), 'held real navigation response');
    const loading = await inspectRegion(status);
    if (nativeEvents) await browser.delay(500);
    const loadingEnded = Date.now();
    await browser.releaseNavigation();
    await browser.until(() => browser.evaluate('!!document.querySelector(".o_list_view")'), 'native Notes list');
    if (nativeEvents) await browser.delay(500);

    const errorStarted = Date.now();
    const denied = '/app/org.example.notes/' + query + '&note=' + foreignNote.public_id;
    await browser.evaluate(`(() => {
        history.pushState(null, '', ${JSON.stringify(denied)});
        dispatchEvent(new PopStateEvent('popstate'));
    })()`);
    await browser.until(() => browser.evaluate('!!document.querySelector(".mp_notice[role=alert]")'), 'real foreign Note denied');
    const error = await inspectRegion(alert);
    if (nativeEvents) await browser.delay(500);
    const errorEnded = Date.now();

    const timestamps = await browser.evaluate(`(() => {
        const { OperationsPanel } = odoo.loader.modules.get('@mp_shell/operations');
        const panel = Object.create(OperationsPanel.prototype);
        const utc = '2026-11-05T18:03:07Z';
        panel.props = { language: 'en-US' };
        const english = panel.formatTimestamp(utc);
        panel.props.language = 'ar';
        return { utc, english, arabic: panel.formatTimestamp(utc) };
    })()`);
    const foreignRequests = browser.blocked.filter(entry => entry.path !== '/mp-ui09-network-probe');
    const result = { image: browser.input.image_id, generation: browser.input.generation, english, arabic,
        readyStatus, loading, readyAlert, error, timestamps, foreignRequests, runtimeExceptions: browser.exceptions };
    if (nativeEvents) {
        const changed = events.filter(event => event.type === 'live_region_changed');
        result.windowsLiveEvents = {
            loading: changed.filter(event => event.epoch_ms >= loadingStarted && event.epoch_ms <= loadingEnded),
            error: changed.filter(event => event.epoch_ms >= errorStarted && event.epoch_ms <= errorEnded),
        };
    }
    await browser.save('locale-announcements.json', result);
    const windowsPassed = !nativeEvents || (
        result.windowsLiveEvents.loading.length &&
        result.windowsLiveEvents.error.some(event =>
            !result.windowsLiveEvents.loading.some(previous => previous.child_id === event.child_id))
    );
    if (!windowsPassed || readyStatus.hasText || readyAlert.hasText || !loading.hasText || !error.hasText ||
        readyStatus.id !== loading.id || readyAlert.id !== error.id ||
        loading.live.live !== 'polite' || error.live.live !== 'assertive' ||
        loading.live.atomic !== true || error.live.atomic !== true ||
        loading.ignored || error.ignored ||
        english.count !== arabic.count || !/members?$/u.test(english.text) ||
        arabic.direction !== 'rtl' || !/عضو|أعضاء/u.test(arabic.text) ||
        !timestamps.english.includes('Nov') || !timestamps.arabic.includes('نوفمبر') ||
        foreignRequests.length || browser.exceptions.length) {
        throw new Error('Installed locale or live-region check failed. Inspect retained observations.');
    }
    console.log(JSON.stringify({ result: 'installed_browser_locale_and_live_region_checks_passed' }));
} finally {
    if (observer) {
        observer.stdin.end('\n');
        await observerExit;
    }
    await browser.releaseNavigation();
    await browser.close();
}
