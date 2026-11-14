import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (await readFile(new URL("../framework_addons/web/static/src/webclient/menus/menu_service.js", import.meta.url), "utf8"))
    .replace(/^import .*;\r?\n/gm, "");
let serial = 0;
const menus = (id = 1) => ({root: {id: "root", children: [id]}, [id]: {id, appID: id, actionID: id * 10}});
async function fixture() {
    const actions = [], events = [], writes = [];
    let provider = async () => menus();
    globalThis.scopedMenuFixture = {
        session: { registry_hash: "same" },
        registry: { category: () => ({ get: () => () => provider(), add: () => {} }) },
        browser: {
            localStorage: { getItem: () => "foreign cached workspace", setItem: (...args) => writes.push(args) },
            sessionStorage: { setItem: () => {} },
        },
    };
    const prefix = "const {session,registry,browser} = globalThis.scopedMenuFixture;\n";
    const { menuService } = await import("data:text/javascript;base64," + Buffer.from(prefix + source).toString("base64") + "#" + serial++);
    const service = await menuService.start({services: {action: {doAction: (...args) => actions.push(args)}}, bus: {trigger: (...args) => events.push(args)}});
    return { service, actions, events, writes, provider: fn => provider = fn };
}

test("scoped startup ignores foreign storage and selection rechecks current availability", async () => {
    const f = await fixture();
    assert.equal(f.service.getApps()[0].id, 1);
    f.provider(async () => ({root: {id: "root", children: []}}));
    await f.service.selectMenu({id: 1});
    assert.equal(f.actions.length, 0);
    assert.deepEqual(f.writes, []);
});
test("navigation failure clears prior names and stays unavailable until a successful read", async () => {
    const f = await fixture();
    f.provider(async () => {throw new Error("Denied");});
    await f.service.reload();
    assert.equal(f.service.unavailable, true);
    assert.deepEqual(f.service.getApps(), []);
    f.provider(async () => menus(2));
    await f.service.reload();
    assert.equal(f.service.unavailable, false);
    await f.service.selectMenu(2);
    assert.equal(f.actions[0][0], 20);
});
test("older successful menu read cannot overwrite a newer denial", async () => {
    const f = await fixture();
    let release;
    f.provider(() => new Promise(resolve => release = resolve));
    const pending = f.service.reload();
    f.provider(async () => {throw new Error("revoked");});
    await f.service.reload();
    release(menus(9));
    await pending;
    assert.deepEqual(f.service.getApps(), []);
    assert.equal(f.service.unavailable, true);
});
