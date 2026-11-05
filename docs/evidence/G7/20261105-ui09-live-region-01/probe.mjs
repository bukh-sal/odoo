import path from 'node:path';
import { browserRuntime } from '../20261105-core25-maintenance-01/browser_runtime.mjs';

const output = path.join(process.cwd(), '.local/g7-ui-core25-01/live-region');
const browser = await browserRuntime(output);
const workspace = browser.input.fixture.workspaces.A;
const foreignNote = browser.before.mp_example_note.find(note => note.workspace_id !== workspace.id);
const query = '?workspace=' + workspace.public_id;
const settings = browser.input.base + '/app/settings' + query;
const readRegions = () => browser.evaluate(`[...document.querySelectorAll('.mp_main [role=status], .mp_main [role=alert]')]
    .map(node => ({ role: node.getAttribute('role'), atomic: node.getAttribute('aria-atomic'),
        empty: !node.textContent.trim() }))`);

try {
    await browser.navigate(settings);
    await browser.until(() => browser.evaluate('!!document.querySelector("#mp_workspace_name")'), 'workspace settings');
    const before = await readRegions();
    await browser.rpc('Accessibility.enable');
    browser.holdNextNavigation();
    await browser.clickText('.mp_root nav a', 'Notes');
    await browser.until(() => browser.held(), 'held real navigation response');
    const loading = await readRegions();
    const loadingAX = await browser.ax('.mp_main [role=status]');
    await browser.releaseNavigation();
    await browser.until(() => browser.evaluate('!!document.querySelector(".o_list_view")'), 'native Notes list');
    await browser.navigate(browser.input.base + '/app/org.example.notes/' + query + '&note=' + foreignNote.public_id);
    await browser.until(() => browser.evaluate('!!document.querySelector(".mp_notice[role=alert]")'), 'foreign Note error');
    const error = await readRegions();
    const errorAX = await browser.ax('.mp_notice[role=alert]');
    const result = { image: browser.input.image_id, generation: browser.input.generation,
        before, loading, loadingAX, error, errorAX,
        foreignRequests: browser.blocked.filter(entry => entry.path !== '/mp-ui09-network-probe'),
        runtimeExceptions: browser.exceptions };
    await browser.save('observations.json', result);
    console.log(JSON.stringify(result));
} finally {
    await browser.releaseNavigation();
    await browser.close();
}
