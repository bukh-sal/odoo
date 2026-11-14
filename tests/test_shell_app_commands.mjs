import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (await readFile(new URL("../framework_addons/web/static/src/webclient/shell/app_commands.js", import.meta.url), "utf8"))
    .replace(/^import .*;\r?\n/gm, "");
let serial = 0;
async function provider(stock = true) {
    const providers = {};
    globalThis.appCommandsFixture = {
        registry: {category: category => ({add: (key, value) => providers[category] = value})},
        DefaultCommandItem: class {}, _t: value => value, session: {mp_stock_profile: stock},
    };
    await import("data:text/javascript;base64," + Buffer.from("const {registry,DefaultCommandItem,_t,session}=globalThis.appCommandsFixture;\n" + source).toString("base64") + "#" + serial++);
    return providers.command_provider;
}
test("default palette reads current apps before building results and uses normal guarded selection", async () => {
    const p = await provider();
    const order = [], app = {id: 42, name: "Current workspace app"};
    const items = await p.provide({services: {menu: {
        reload: async () => order.push("fresh"),
        getApps: () => {order.push("apps"); return [app];},
        selectMenu: item => order.push(item),
    }}});
    assert.deepEqual(order, ["fresh", "apps"]);
    assert.equal(items[0].name, app.name);
    items[0].action();
    assert.equal(order[2], app);
});
test("empty current projection contributes no stale app results", async () => {
    const p = await provider();
    assert.deepEqual(await p.provide({services: {menu: {reload: async () => {}, getApps: () => []}}}), []);
});
test("optional shell keeps its own app discovery", async () => {
    const p = await provider(false);
    assert.deepEqual(await p.provide({services: {}}), []);
});
