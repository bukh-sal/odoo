import path from 'node:path';
import { browserRuntime } from './fresh_browser_runtime.mjs';

const b = await browserRuntime(path.join(process.cwd(), '.local/g7-core26-fresh-browser/browser'));
const { input } = b;
const query = '?workspace=' + input.fixture.workspaces.A.public_id;
const notes = input.base + '/app/org.example.notes/' + query;
const canvas = input.base + '/app/org.example.canvas/' + query;

try {
    await b.navigate(notes);
    await b.until(() => b.evaluate('!!document.querySelector(".o_list_view")'), 'native Notes list');
    await b.navigate(notes + '&note=' + input.note_id);
    await b.until(() => b.evaluate('!!document.querySelector(".o_form_view .o_field_widget[name=title]")'), 'native Note form');
    await b.clickText('.mp_page_header button', 'Edit labels');
    await b.until(() => b.evaluate('!!document.querySelector(".mp_label_dialog[open]")'), 'native Labels extension action');
    const labels = await b.ax('.mp_label_dialog');
    await b.key('Escape', 'Escape', 27);
    await b.until(() => b.evaluate('!document.querySelector(".mp_label_dialog[open]")'), 'Labels dialog closed');
    await b.navigate(canvas);
    await b.until(() => b.evaluate('document.querySelectorAll(".mp_canvas_card").length === 1'), 'one-card custom page');
    const nav = await b.ax('.mp_root nav');
    const foreign = b.blocked.filter(entry => entry.path !== '/mp-ui09-network-probe');
    if (foreign.length || b.exceptions.length || labels[0]?.role !== 'dialog' || nav[0]?.role !== 'navigation') {
        throw new Error('Fresh reference browser check failed');
    }
    await b.save('fresh-browser.json', {
        result: 'fresh_kit_native_views_labels_and_custom_page_passed',
        image: input.image_id, generation: input.generation,
        nativeListAndForm: true, labels, canvasCards: 1, navigation: nav,
        foreignRequests: foreign, runtimeExceptions: b.exceptions, wroteBusinessData: false,
    });
    console.log('Fresh kit browser verified native Notes, Labels and one-card Canvas');
} finally {
    await b.close();
}
