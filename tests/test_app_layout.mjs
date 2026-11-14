import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (await readFile(new URL("../framework_addons/web/static/src/interface/app_layout.js", import.meta.url), "utf8"))
    .replace(/^import .*;\r?\n/gm, "");
let serial = 0;
async function fixture(props = {}) {
    const focused = [], effects = [], destination = {};
    const refs = {
        trigger: { el: { focus: () => focused.push("trigger") } },
        context: { el: { focus: () => focused.push("context"), contains: node => node === destination } },
        content: { el: { focus: () => focused.push("content") } },
    };
    let ids = 0;
    globalThis.appLayoutFixture = {
        Component: class { constructor(props) { this.props = props; } },
        useState: value => value, useRef: name => refs[name],
        useEffect: callback => effects.push(callback),
        _t: value => value, uniqueId: prefix => prefix + ++ids,
    };
    const prefix = "const {Component,useState,useRef,useEffect,_t,uniqueId}=globalThis.appLayoutFixture;\n";
    const { AppLayout } = await import("data:text/javascript;base64," + Buffer.from(prefix + source).toString("base64") + "#" + serial++);
    const layout = new AppLayout({ ...AppLayout.defaultProps, contextTitle: "Long workspace destinations", ...props });
    layout.setup();
    return { layout, focused, destination, flush: () => effects.forEach(callback => callback()) };
}

test("context opener and Escape request the correct focus targets", async () => {
    const f = await fixture();
    f.layout.toggleContext(); f.flush();
    assert.equal(f.layout.state.contextOpen, true); assert.deepEqual(f.focused, ["context"]);
    const handled = [];
    f.layout.onContextKeydown({ key: "Escape", preventDefault: () => handled.push("prevent"), stopPropagation: () => handled.push("stop") });
    f.flush();
    assert.equal(f.layout.state.contextOpen, false); assert.deepEqual(f.focused, ["context", "trigger"]);
    assert.deepEqual(handled, ["prevent", "stop"]);
});
test("only an explicit destination in this context dismisses to the work area", async () => {
    const f = await fixture();f.layout.toggleContext();f.flush();
    f.layout.onContextSelection({ target: { closest: () => null } });
    assert.equal(f.layout.state.contextOpen, true);
    f.layout.onContextSelection({ target: { closest: () => ({ foreign: true }) } });
    assert.equal(f.layout.state.contextOpen, true);
    f.layout.onContextSelection({ target: { closest: () => f.destination } });f.flush();
    assert.equal(f.layout.state.contextOpen, false);assert.deepEqual(f.focused, ["context", "content"]);
});
test("modified clicks keep the original context open for normal new-tab behavior", async () => {
    for (const modifier of ["ctrlKey", "metaKey", "shiftKey", "button"]) {
        const f = await fixture();f.layout.toggleContext();f.flush();
        f.layout.onContextSelection({ [modifier]: true, target: { closest: () => f.destination } });
        assert.equal(f.layout.state.contextOpen, true);
    }
});
test("Escape already handled by a nested control does not dismiss its parent", async () => {
    const f = await fixture();f.layout.toggleContext();f.flush();
    f.layout.onContextKeydown({ key: "Escape", defaultPrevented: true, preventDefault: () => assert.fail(), stopPropagation: () => assert.fail() });
    assert.equal(f.layout.state.contextOpen, true);
});
test("context-free pages cannot open an absent context and toggle close restores focus", async () => {
    const empty = await fixture({ showContext: false });empty.layout.toggleContext();empty.flush();
    assert.equal(empty.layout.state.contextOpen, false);assert.deepEqual(empty.focused, []);
    const f = await fixture();f.layout.toggleContext();f.flush();f.layout.toggleContext();f.flush();
    assert.deepEqual(f.focused, ["context", "trigger"]);
});
test("losing an open context clears its state and requests work-area focus", async () => {
    const f = await fixture();f.layout.toggleContext();f.flush();
    f.layout.props.showContext = false;f.flush();f.flush();
    assert.equal(f.layout.state.contextOpen, false);
    assert.deepEqual(f.focused, ["context", "content"]);
    f.layout.props.showContext = true;f.flush();
    assert.equal(f.layout.state.contextOpen, false);
});
