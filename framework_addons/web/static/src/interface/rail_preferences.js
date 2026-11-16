import { useComponent, useEffect, useExternalListener, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { user } from "@web/core/user";
import { session } from "@web/session";

const CHANGE = "UI:RAIL-PREFERENCE-CHANGED";
const identity = value => typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,511}$/.test(value);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export function railPreferenceKey(userId, database, workspace) {
    if (!Number.isSafeInteger(userId) || userId <= 0 || typeof database !== "string" ||
        !database || database.length > 256 || /[\x00-\x1f\x7f]/.test(database) || !UUID.test(workspace || "")) return null;
    // Origin is supplied by localStorage. No data or authorization lives here.
    return `mp.rail.v1:${userId}:${encodeURIComponent(database)}:${workspace}`;
}

export function railAppId(app) {
    if (identity(app.xmlid)) return "xmlid:" + app.xmlid;
    if (identity(app.pluginID)) return "plugin:" + app.pluginID;
    if (identity(app.id)) return "menu:" + app.id;
    return Number.isSafeInteger(app.id) && app.id > 0 ? "menu:" + app.id : null;
}

export function validRailPins(value) {
    return value === null || (Array.isArray(value) && value.every(identity) && new Set(value).size === value.length);
}

export function readRailPins(storage, key) {
    if (!key) return null;
    try {
        const raw = storage.getItem(key);
        // A presentation record cannot justify parsing unbounded corrupted data.
        if (raw === null || raw.length > 65536) return null;
        const value = JSON.parse(raw);
        return validRailPins(value) ? value : null;
    } catch { return null; }
}

export function writeRailPins(storage, key, value) {
    if (!key || !validRailPins(value)) return false;
    const raw = JSON.stringify(value);
    if (raw.length > 65536) return false;
    try { storage.setItem(key, raw); return true; } catch { return false; }
}

export function pinnedRailApps(apps, pins) {
    if (pins === null) return apps;
    const current = new Map(apps.map(app => [railAppId(app), app]));
    return pins.map(id => current.get(id)).filter(Boolean);
}

export function useRailPreferences(apps) {
    const component = useComponent();
    const storage = () => { try { return browser.localStorage; } catch { return null; } };
    const key = () => railPreferenceKey(user.userId, session.db,
        new URLSearchParams(browser.location.search).get("workspace"));
    const state = useState({ key: key(), pins: readRailPins(storage(), key()) });
    const load = () => { state.key = key(); state.pins = readRailPins(storage(), state.key); };
    useEffect(load, () => [key()]);
    useExternalListener(window, "storage", event => { if (event.key === key() || event.key === null) load(); });
    useExternalListener(component.env.bus, CHANGE, event => { if (event.detail.key === key()) load(); });
    const pins = () => state.key === key() ? state.pins : readRailPins(storage(), key());
    return {
        get pins() { return pins(); },
        get apps() { return pinnedRailApps(apps(), pins()); },
        save(value) {
            const current = key();
            if (!writeRailPins(storage(), current, value)) return false;
            state.key = current; state.pins = value === null ? null : value.slice();
            component.env.bus.trigger(CHANGE, { key: current });
            return true;
        },
    };
}
