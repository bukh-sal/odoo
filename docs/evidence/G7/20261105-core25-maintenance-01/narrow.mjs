import path from 'node:path';
import { browserRuntime } from './browser_runtime.mjs';

const output = path.join(process.cwd(), '.local/g7-ui-core25-01/narrow');
const browser = await browserRuntime(output);
const workspace = browser.input.fixture.workspaces.A;
const note = browser.before.mp_example_note.find(row => row.workspace_id === workspace.id);
const route = (name, extra = '') => `${browser.input.base}/app/${name}?workspace=${workspace.public_id}${extra}`;
const readySettings = '!!document.querySelector("#mp_workspace_name") && !document.querySelector(".mp_notice[role=status]")';
const samples = [];

async function sample(name, url, ready) {
    await browser.navigate(url);
    await browser.until(() => browser.evaluate(ready), name);
    const dimensions = await browser.evaluate(`({
        viewport: innerWidth,
        document: document.documentElement.scrollWidth,
        root: document.querySelector('.mp_root').scrollWidth,
        header: document.querySelector('.mp_root header').scrollWidth,
        headerClient: document.querySelector('.mp_root header').clientWidth,
        lang: document.documentElement.lang,
        direction: document.documentElement.dir
    })`);
    samples.push({ name, ...dimensions });
    await browser.screenshot(name + '.png');
}

try {
    await browser.rpc('Emulation.setDeviceMetricsOverride', {
        width: 320, height: 800, deviceScaleFactor: 1, mobile: false
    });
    await sample('english-settings', route('settings'), readySettings);
    await sample('native-note', route('org.example.notes/', '&note=' + note.public_id),
        '!!document.querySelector(".o_form_view .o_field_widget[name=title]")');
    await browser.navigate(route('settings'));
    await browser.until(() => browser.evaluate(readySettings), 'settings loaded');
    await browser.select('#mp_shell_language', 'ar');
    await sample('arabic-settings', route('settings'),
        readySettings + ' && document.documentElement.lang === "ar"');
    await browser.select('#mp_shell_language', 'en-US');
    await browser.until(() => browser.evaluate('document.documentElement.lang === "en-US"'), 'English restored');
    const foreign = browser.blocked.filter(entry => entry.path !== '/mp-ui09-network-probe');
    const overflow = samples.filter(row => row.viewport !== 320 || row.document > 320 ||
        row.root > 320 || row.header > row.headerClient);
    await browser.save('observations.json', { samples, overflow, foreign, exceptions: browser.exceptions });
    console.log(JSON.stringify({ samples, overflow, foreign: foreign.length, exceptions: browser.exceptions.length }));
    if (overflow.length || foreign.length || browser.exceptions.length) process.exitCode = 1;
} finally {
    await browser.close();
}
