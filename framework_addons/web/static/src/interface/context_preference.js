import { useComponent, useEffect, useExternalListener, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { user } from "@web/core/user";

const CHANGE = "UI:CONTEXT-PREFERENCE-CHANGED";

/** Origin supplies the site boundary; store only a user/app presentation boolean. */
export function contextPreferenceKey(userId, contextKey) {
    if (!Number.isSafeInteger(userId) || userId <= 0 || typeof contextKey !== "string" ||
        !/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$/.test(contextKey)) return null;
    return `mp.context.v1:${userId}:${contextKey}`;
}

export function readContextCollapsed(storage, key) {
    if (!key) return false;
    try { return storage.getItem(key) === "true"; } catch { return false; }
}

export function writeContextCollapsed(storage, key, collapsed) {
    if (!key || typeof collapsed !== "boolean") return false;
    try { storage.setItem(key, JSON.stringify(collapsed)); return true; } catch { return false; }
}

/** No data, drafts, grants or navigation are persisted by this hook. */
export function useContextPreference(contextKey) {
    const component = useComponent();
    const key = () => contextPreferenceKey(user.userId, contextKey());
    const initial = key();
    const state = useState({ key: initial, collapsed: readContextCollapsed(browser.localStorage, initial) });
    const load = () => {
        state.key = key();
        state.collapsed = readContextCollapsed(browser.localStorage, state.key);
    };
    useEffect(load, () => [key()]);
    useExternalListener(window, "storage", event => {
        if (event.key === key() || event.key === null) load();
    });
    const changed = event => {
        if (key() && event.detail.key === key() && typeof event.detail.collapsed === "boolean") {
            state.key = key(); state.collapsed = event.detail.collapsed;
        }
    };
    useExternalListener(component.env.bus, CHANGE, changed);
    return {
        get collapsed() { return state.key === key() ? state.collapsed : readContextCollapsed(browser.localStorage, key()); },
        toggle() {
            const current = key();
            const collapsed = !(state.key === current ? state.collapsed : readContextCollapsed(browser.localStorage, current));
            state.key = current; state.collapsed = collapsed;
            writeContextCollapsed(browser.localStorage, current, collapsed);
            if (current) component.env.bus.trigger(CHANGE, { key: current, collapsed });
        },
    };
}
