import { Component, onWillUnmount, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { uniqueId } from "@web/core/utils/functions";
import { Icon } from "@web/interface/icon";

const key = value => typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$/.test(value);
const label = value => typeof value === "string" && value.trim().length > 0;

/** Sidebar destinations are internal links. External links belong in explicit content/actions. */
export function contextHref(value) {
    return typeof value === "string" && /^(?:\/(?!\/)|#)/.test(value) && !/[\\\x00-\x1f\x7f]/.test(value);
}

export function validateContextGroups(groups) {
    if (!Array.isArray(groups)) throw new Error("Context groups must be an array");
    const ids = new Set(), objects = new Set();
    const checkKey = id => {
        if (!key(id) || ids.has(id)) throw new Error("Context keys must be unique and stable");
        ids.add(id);
    };
    const visit = items => {
        if (!Array.isArray(items)) throw new Error("Context children must be an array");
        for (const item of items) {
            if (!item || objects.has(item)) throw new Error("Context items cannot contain cycles or reused objects");
            objects.add(item); checkKey(item.id);
            if (!label(item.label) || (item.href !== undefined && !contextHref(item.href)) ||
                (item.icon !== undefined && typeof item.icon !== "string") ||
                (item.countLabel !== undefined && !label(item.countLabel)) ||
                (item.disabled !== undefined && typeof item.disabled !== "boolean") ||
                (item.current !== undefined && typeof item.current !== "boolean") ||
                (item.expanded !== undefined && typeof item.expanded !== "boolean") ||
                (item.count !== undefined && (!Number.isSafeInteger(item.count) || item.count < 0))) {
                throw new Error("Context item presentation is invalid");
            }
            if (item.children !== undefined) visit(item.children);
        }
    };
    for (const group of groups) {
        if (!group || (group.label !== undefined && !label(group.label))) throw new Error("Context group label is invalid");
        checkKey(group.id); visit(group.items);
    }
    return groups;
}

/** Controlled destinations and truthful counts; no data request or authority inference. */
export class ContextNav extends Component {
    static template = "web.interface.ContextNav";
    static components = { Icon };
    static props = {
        groups: Array,
        label: { type: String, optional: true },
        onNavigate: { type: Function, optional: true },
        onToggle: { type: Function, optional: true },
        slots: { type: Object, optional: true },
    };
    static defaultProps = { slots: {} };
    setup() {
        this.root = useRef("root");
        this.prefix = uniqueId("mp-context-nav-");
        this.state = useState({ expanded: {}, pending: {} });
        onWillUnmount(() => { this.destroyed = true; });
    }
    get groups() { return validateContextGroups(this.props.groups); }
    get label() { return this.props.label || _t("Navigation"); }
    toggleLabel(item) { return this.expanded(item) ? _t("Collapse %s", item.label) : _t("Expand %s", item.label); }
    childrenId(item) { return this.prefix + "-" + item.id; }
    expanded(item) {
        return Object.hasOwn(this.state.expanded, item.id) ? this.state.expanded[item.id] : item.expanded !== false;
    }
    contains(id) {
        const visit = items => items.some(item => item.id === id || visit(item.children || []));
        return this.groups.some(group => visit(group.items));
    }
    async toggle(item) {
        if (!item.children?.length || this.state.pending[item.id] === true || !this.contains(item.id)) return false;
        const next = !this.expanded(item);
        this.state.pending[item.id] = true;
        try {
            if (await this.props.onToggle?.(item.id, next) === false || this.destroyed || !this.contains(item.id)) return false;
            this.state.expanded[item.id] = next;
            return true;
        } finally { if (!this.destroyed) this.state.pending[item.id] = false; }
    }
    async navigate(item, event) {
        if (item.disabled || !this.contains(item.id)) { event.preventDefault(); return false; }
        if (item.href && (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button)) return true;
        if (!this.props.onNavigate) return true;
        event.preventDefault();
        return this.props.onNavigate(item, event);
    }
    onKeydown(event) {
        if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
        const moves = ["ArrowDown", "ArrowUp", "Home", "End"];
        if (!moves.includes(event.key)) return;
        const targets = [...this.root.el.querySelectorAll('[data-mp-context-focus]:not(:disabled):not([aria-disabled="true"])')]
            .filter(el => el.getClientRects().length);
        const index = targets.indexOf(document.activeElement);
        if (index < 0 || !targets.length) return;
        const next = event.key === "Home" ? 0 : event.key === "End" ? targets.length - 1 :
            (index + (event.key === "ArrowDown" ? 1 : -1) + targets.length) % targets.length;
        event.preventDefault(); targets[next].focus();
    }
}
