import { Component, onWillUpdateProps, useEffect, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Icon } from "@web/interface/icon";

const identity = value => typeof value === "string" && value.length > 0 && !/[\s\x00-\x1f\x7f]/.test(value);

/** Controlled presentation. The record owner supplies current content and guards. */
export class RecordTabs extends Component {
    static template = "web.interface.RecordTabs";
    static props = {
        items: Array, idPrefix: String, onSelect: Function,
        selectedId: { type: String, optional: true },
        label: { type: String, optional: true },
    };
    setup() {
        this.root = useRef("root");
        this.state = useState({ pending: false, focusId: null });
        onWillUpdateProps(() => { this.hadFocus = this.root.el?.contains(document.activeElement); });
        useEffect(() => {
            if (this.hadFocus && document.activeElement === document.body) this.focus(this.focusId);
            this.hadFocus = false;
        }, () => [this.props.selectedId, this.items.map(item => item.id).join("\n")]);
    }
    get items() {
        if (!identity(this.props.idPrefix)) throw new Error("Record tabs require a stable DOM identity");
        const ids = new Set(), panels = new Set();
        for (const item of this.props.items) {
            if (!identity(item.id) || !identity(item.panelId) || typeof item.label !== "string" || !item.label.trim() ||
                ids.has(item.id) || panels.has(item.panelId) || (item.disabled !== undefined && typeof item.disabled !== "boolean")) {
                throw new Error("Record tabs require unique keys/panels and plain labels");
            }
            ids.add(item.id); panels.add(item.panelId);
        }
        return this.props.items;
    }
    get label() { return this.props.label || _t("Record sections"); }
    get activeId() { return this.items.find(item => item.id === this.props.selectedId && !item.disabled)?.id || this.items.find(item => !item.disabled)?.id; }
    get focusId() { return this.items.find(item => item.id === this.state.focusId && !item.disabled)?.id || this.activeId; }
    tabId(item) { return this.props.idPrefix + "-tab-" + item.id; }
    focus(id) {
        const button = [...(this.root.el?.querySelectorAll("[role=tab]") || [])].find(element => element.dataset.recordTab === id);
        button?.focus();
    }
    onKeydown(event, id) {
        const items = this.items.filter(item => !item.disabled);
        if (!items.length || this.state.pending) return;
        let index = items.findIndex(item => item.id === id);
        const rtl = this.root.el && getComputedStyle(this.root.el).direction === "rtl";
        if (event.key === "Home") index = 0;
        else if (event.key === "End") index = items.length - 1;
        else if (event.key === "ArrowRight") index = (index + (rtl ? -1 : 1) + items.length) % items.length;
        else if (event.key === "ArrowLeft") index = (index + (rtl ? 1 : -1) + items.length) % items.length;
        else return;
        event.preventDefault();
        this.state.focusId = items[index].id;
        this.focus(this.state.focusId);
    }
    async choose(item) {
        if (this.state.pending || item.disabled || !this.items.some(current => current.id === item.id && !current.disabled)) return false;
        this.state.pending = true;
        try {
            const result = await this.props.onSelect(item.id);
            if (result !== false && this.items.some(current => current.id === item.id && !current.disabled)) this.state.focusId = item.id;
            return result;
        } finally { this.state.pending = false; }
    }
}

/** Informational card; the app supplies truthful data, actions and empty states. */
export class RecordSection extends Component {
    static template = "web.interface.RecordSection";
    static components = { Icon };
    static props = {
        title: String, icon: { type: String, optional: true },
        headingLevel: { type: Number, optional: true, validate: value => [2, 3, 4, 5, 6].includes(value) },
        slots: { type: Object, optional: true },
    };
    static defaultProps = { headingLevel: 2, slots: {} };
}
