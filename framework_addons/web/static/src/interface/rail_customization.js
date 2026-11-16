import { Component, onWillUnmount, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { Icon } from "@web/interface/icon";
import { railAppId } from "@web/interface/rail_preferences";

/** A local preference editor, not an app catalog or access editor. */
export class RailCustomization extends Component {
    static template = "web.interface.RailCustomization";
    static components = { Dialog, Icon };
    static props = { apps: Array, pins: [Array, {value: null}], onSave: Function, close: Function };
    setup() {
        onWillUnmount(() => { this.destroyed = true; });
        const available = new Set(this.props.apps.map(railAppId));
        this.state = useState({ ids: (this.props.pins === null ? this.props.apps.map(railAppId) : this.props.pins)
            .filter(id => id && available.has(id)), defaults: this.props.pins === null, error: "", busy: false });
    }
    get title() { return _t("Customize sidebar"); }
    get rows() {
        const map = new Map(this.props.apps.map(app => [railAppId(app), app]));
        return [...this.state.ids.map(id => map.get(id)).filter(Boolean),
            ...this.props.apps.filter(app => !this.state.ids.includes(railAppId(app)))];
    }
    id(app) { return railAppId(app); }
    selected(app) { return this.state.ids.includes(this.id(app)); }
    moveLabel(app, up) { return up ? _t("Move %s up", app.name) : _t("Move %s down", app.name); }
    toggle(app) {
        if (this.state.busy) return;
        const id = this.id(app); if (!id) return;
        this.state.defaults = false;
        this.state.ids = this.selected(app) ? this.state.ids.filter(item => item !== id) : [...this.state.ids, id];
    }
    canMove(app, direction) {
        const index = this.state.ids.indexOf(this.id(app));
        return index >= 0 && index + direction >= 0 && index + direction < this.state.ids.length;
    }
    move(app, direction) {
        if (this.state.busy || !this.canMove(app, direction)) return;
        const ids = this.state.ids.slice(), index = ids.indexOf(this.id(app));
        [ids[index], ids[index + direction]] = [ids[index + direction], ids[index]];
        this.state.defaults = false; this.state.ids = ids;
    }
    reset() {
        if (this.state.busy) return;
        this.state.defaults = true; this.state.ids = this.props.apps.map(railAppId).filter(Boolean);
    }
    async save() {
        if (this.state.busy || this.destroyed) return false;
        this.state.busy = true; this.state.error = "";
        try {
            const saved = await this.props.onSave(this.state.defaults ? null : this.state.ids.slice());
            if (this.destroyed) return false;
            if (saved !== true) {
                this.state.error = _t("Sidebar preferences could not be saved in this browser. Your choices are still here.");
                return false;
            }
            this.props.close(); return true;
        } catch {
            if (!this.destroyed) this.state.error = _t("Sidebar preferences could not be saved in this browser. Your choices are still here.");
            return false;
        } finally { if (!this.destroyed) this.state.busy = false; }
    }
}
