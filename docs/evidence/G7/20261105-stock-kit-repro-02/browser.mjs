// Isolated browser measurements using the established blocked-origin harness.
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

const privateRoot = path.resolve(process.argv[2] || ".local/stock-webclient-release/browser");
const helper = path.resolve("docs/evidence/G7/20261104-ui-qualification-01/browser_runtime02.mjs");
let original = await readFile(helper, "utf8");
if (process.env.MP_QUALIFICATION_CHROMIUM) {
    const launcher = "path.join(process.env['ProgramFiles(x86)'],'Microsoft/Edge/Application/msedge.exe')";
    assert.equal(original.split(launcher).length, 2);
    original = original.replace(launcher, JSON.stringify(process.env.MP_QUALIFICATION_CHROMIUM));
}
const prior = "path.join(process.cwd(),'.local/g7-ui-qualification-01')";
assert.equal(original.split(prior).length, 2);
const modulePath = path.join(privateRoot, "browser_runtime.mjs");
await writeFile(modulePath, original.replace(prior, JSON.stringify(privateRoot)), { flag: "wx" });
const { browserRuntime } = await import(pathToFileURL(modulePath));
const b = await browserRuntime(privateRoot);
const { input } = b;
const workspace = input.fixture.workspaces.A.public_id;

async function page(route, selector) {
    await b.rpc("Page.navigate", { url: input.base + route });
    await b.until(() => b.evaluate(`!!document.querySelector(${JSON.stringify(selector)})`), selector);
}

async function exitAttempt(method) {
    // A pending page transition can wait on the dialog. Dismiss it before
    // waiting on the command result. No page or request override is used.
    const attempt = b.rpc(method).catch((error) => ({ error: error.message }));
    let dismissed = false;
    for (let count = 0; count < 30 && !dismissed; count++) {
        try {
            await b.rpc("Page.handleJavaScriptDialog", { accept: false });
            dismissed = true;
        } catch {
            await b.delay(100);
        }
    }
    assert.ok(dismissed, `Browser did not prompt on ${method}`);
    await attempt;
    assert.equal(await b.evaluate("document.querySelector('.o_field_widget[name=title] input').value"), "Unsaved stock form proof");
}

async function checkRtlAndPluginPages() {
    await page(input.notes_route, ".o_list_view");
    await b.until(() => b.evaluate("document.body.innerText.includes('Release reference A')"), "native RTL Notes row");
    await b.clickText("td", "Release reference A");
    await b.until(() => b.evaluate("!!document.querySelector('.o_form_view .o_field_widget[name=title]')"), "native RTL form");
    const rtl = await b.evaluate(`(() => {
        const button = document.querySelector('.o_menu_systray button[aria-haspopup=menu]');
        let background = 'rgba(0, 0, 0, 0)';
        for (let element = button; element && background === 'rgba(0, 0, 0, 0)'; element = element.parentElement) {
            background = getComputedStyle(element).backgroundColor;
        }
        return { direction: getComputedStyle(document.body).direction,
            titleDirection: getComputedStyle(document.querySelector('.o_field_widget[name=title] input')).direction,
            foreground: getComputedStyle(button).color, background };
    })()`);
    assert.equal(rtl.direction, "rtl");
    assert.equal(rtl.titleDirection, "rtl");
    const trigger = ".o_menu_systray .mp_stock_workspace";
    await b.evaluate(`document.querySelector('${trigger}').focus()`);
    await b.key("Enter", "Enter", 13);
    await b.until(() => b.evaluate("document.body.innerText.includes('أدوات الملاحظات')"), "Arabic workspace menu labels");
    await b.key("Escape", "Escape", 27);
    await b.until(() => b.evaluate(`document.querySelector('${trigger}').getAttribute('aria-expanded') === 'false'`), "RTL keyboard close");
    rtl.trigger_focus_restored = await b.evaluate(`document.activeElement === document.querySelector('${trigger}')`);
    rtl.focus_outline = await b.evaluate(`getComputedStyle(document.activeElement).outlineWidth`);
    assert.equal(rtl.trigger_focus_restored, true);
    assert.equal(rtl.focus_outline, "2px");
    function luminance(channels) {
        const linear = channels.map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
        return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
    }
    const text = rtl.foreground.match(/[\d.]+/g).map(Number);
    const backdrop = rtl.background.match(/[\d.]+/g).map(Number);
    assert.ok(text.length >= 3 && backdrop.length >= 3 && (backdrop[3] ?? 1) === 1);
    const opacity = text[3] ?? 1;
    const foreground = luminance(text.slice(0, 3).map((channel, index) => (channel * opacity + backdrop[index] * (1 - opacity)) / 255));
    const background = luminance(backdrop.slice(0, 3).map((channel) => channel / 255));
    rtl.workspace_trigger_contrast = (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
    assert.ok(rtl.workspace_trigger_contrast >= 4.5, JSON.stringify(rtl));
    await b.screenshot("stock-rtl.png");
    await page(`/app/org.example.canvas/?workspace=${workspace}`, "[aria-label='Canvas board']");
    await b.until(() => b.evaluate("[...document.querySelectorAll('textarea')].some(e => e.value === 'Minimal reference card')"), "Canvas fixture card");
    await page(`/app/org.example.notes/?workspace=${workspace}`, ".o_list_view");
    await b.until(() => b.evaluate("document.body.innerText.includes('Release reference A')"), "Notes tools row rendered");
    await b.clickText("td", "Release reference A");
    await b.until(() => b.evaluate("document.body.innerText.includes('Analyze saved note') && document.body.innerText.includes('Edit labels')"), "Labels and worker controls");
    await b.clickText("button", "Edit labels");
    await b.until(() => b.evaluate("document.querySelector('dialog[open].mp_label_dialog')?.textContent.includes('Edit note labels')"), "named Labels dialog");
    await b.key("Escape", "Escape", 27);
    await b.until(() => b.evaluate("!document.querySelector('dialog[open].mp_label_dialog')"), "Labels keyboard dismissal");
    await b.clickText("button", "Analyze saved note");
    await b.until(() => b.evaluate("document.body.innerText.includes('Saved revision 2: characters 30, words 3, lines 1.')"), "completed worker result");
    await page(`/app/settings?workspace=${workspace}`, "section[aria-label='Preferences']");
    await b.until(() => b.evaluate("document.body.innerText.includes('Preferences')"), "platform settings");
    const foreign = b.blocked.filter((row) => row.path !== "/mp-ui09-network-probe");
    assert.deepEqual(foreign, []);
    assert.deepEqual(b.exceptions, []);
    await b.save("rtl-plugin-pages.json", { result: "passed", image: input.image_id, rtl,
        notes_labels_canvas_settings_and_completed_worker_result: true, foreign_requests: foreign, foreign_control_blocked: true });
    console.log(JSON.stringify({ result: "passed", rtl }));
}

async function checkDraft() {
    await page("/", ".o_menu_systray");
    assert.equal(await b.evaluate("location.pathname"), "/odoo");
    const menu = ".o_menu_systray button[aria-haspopup=menu]";
    await b.until(() => b.evaluate(`!!document.querySelector('${menu}')`), "workspace button");
    const stockReadyMs = await b.evaluate("Math.round(performance.now())");
    assert.ok(stockReadyMs < 3000, `Warm stock bootstrap took ${stockReadyMs} ms`);
    assert.ok((await b.ax(menu)).some((node) => node.role === "button" && node.name === "Choose workspace"));
    await b.evaluate(`document.querySelector('${menu}').focus()`);
    await b.key("Enter", "Enter", 13);
    await b.until(() => b.evaluate(`document.querySelector('${menu}').getAttribute('aria-expanded') === 'true'`), "keyboard menu open");
    await b.key("Escape", "Escape", 27);
    await b.until(() => b.evaluate(`document.querySelector('${menu}').getAttribute('aria-expanded') === 'false'`), "keyboard menu close");
    await page(input.notes_route.replace(workspace, input.fixture.workspaces.B.public_id), ".o_list_view");
    await b.until(() => b.evaluate("document.body.innerText.includes('Release reference B')"), "viewer Notes row");
    assert.equal(await b.evaluate("document.body.innerText.includes('Release reference A')"), false);
    await b.clickText("td", "Release reference B");
    await b.until(() => b.evaluate("!!document.querySelector('.o_form_view .o_field_widget[name=title]')"), "viewer Notes form");
    assert.equal(await b.evaluate("!!document.querySelector('.o_field_widget[name=title] input')"), false);
    await page(input.notes_route, ".o_list_view");
    await b.until(() => b.evaluate("document.body.innerText.includes('Release reference A')"), "scoped Notes row");
    await b.clickText("td", "Release reference A");
    const title = ".o_field_widget[name=title] input";
    await b.until(() => b.evaluate(`!!document.querySelector('${title}')`), "stock Notes form");
    await b.screenshot("stock-native-notes.png");
    const layout = {};
    for (const [label, width, scale] of [["regular", 1280, 1], ["zoom200", 640, 2], ["narrow", 320, 1]]) {
        await b.rpc("Emulation.setDeviceMetricsOverride", { width, height: 900, deviceScaleFactor: scale, mobile: false });
        await b.delay(150);
        layout[label] = await b.evaluate(`({viewport:innerWidth, documentWidth:document.documentElement.scrollWidth,
            fieldWidth:document.querySelector('${title}').getBoundingClientRect().width})`);
        assert.ok(layout[label].fieldWidth > 0);
        assert.equal(layout[label].documentWidth, layout[label].viewport);
    }
    await b.rpc("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
    const formUrl = await b.evaluate("location.pathname + location.search");
    await b.evaluate(`document.querySelector('${title}').focus();document.querySelector('${title}').select()`);
    await b.rpc("Input.insertText", { text: "Unsaved stock form proof" });
    await exitAttempt("Page.reload");
    await exitAttempt("Page.close");

    const logout = await b.evaluate(`fetch('/web/session/destroy', { method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ jsonrpc:'2.0', method:'call', id:1, params:{} }) }).then(response => response.json())`);
    assert.ok(!logout.error);
    await b.evaluate("document.querySelector('.o_form_button_save').click()");
    await b.until(() => b.evaluate("document.body.innerText.includes('Sign in again')"), "expired-session recovery notice");
    assert.equal(await b.evaluate(`document.querySelector('${title}').value`), "Unsaved stock form proof");
    const foreign = b.blocked.filter((row) => row.path !== "/mp-ui09-network-probe");
    assert.deepEqual(foreign, []);
    assert.deepEqual(b.exceptions, []);
    await b.save("qualification.json", { result: "passed", image: input.image_id, formUrl, layout,
        warm_authenticated_webclient_ready_ms: stockReadyMs,
        workspace_keyboard_enter_escape: true, cancelled_reload_and_close_preserved_input: true,
        separate_viewer_workspace_and_read_only_form: true,
        expired_session_notice_preserved_input: true, foreign_requests: foreign, foreign_control_blocked: true,
        browser_runtime_exceptions: b.exceptions });
    console.log(JSON.stringify({ result: "passed", layout }));
}

try {
    if (input.rtl) {
        await checkRtlAndPluginPages();
    } else {
        await checkDraft();
    }
} catch (error) {
    const pageState = await b.evaluate("({path:location.pathname, title:document.title, ready:document.readyState, visible:document.body?.innerText.slice(0,220)})").catch(() => null);
    await b.save("failure.json", {error: error.message, page: pageState, network: b.network.slice(-25),
        blocked: b.blocked, exceptions: b.exceptions});
    throw error;
} finally {
    await b.close();
}
