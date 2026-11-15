import { Component, useChildSubEnv, useExternalListener, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dialog } from "@web/core/dialog/dialog";
import { ConnectionAbortedError, ConnectionLostError } from "@web/core/network/rpc";
import { useBus, useService } from "@web/core/utils/hooks";
import { Icon } from "@web/interface/icon";
import { FormViewDialog } from "./form_view_dialog";

export class CreationSurfaceDialog extends Dialog {
    static props = { ...Dialog.props, requestClose: Function, sheet: { type: Boolean, optional: true } };
    setup() { super.setup(); this.ui = useService("ui"); }
    get isFullscreen() { return this.props.fullscreen || this.ui.isSmall; }
    async dismiss() { return this.props.requestClose(); }
    get contentStyle() { return this.props.sheet || this.isFullscreen ? "" : super.contentStyle; }
}

export class RecordCreationHeader extends Component {
    static template = "web.RecordCreationHeader";
    static components = { Icon };
    static props = {
        title: String, close: Function,
        fullscreen: { type: Boolean, optional: true },
        onExpand: { type: Function, optional: true },
        busy: { type: Boolean, optional: true },
        closeLabel: { type: String, optional: true },
    };
    setup() { this.ui = useService("ui"); }
    get closeLabel() { return this.props.closeLabel || _t("Close form"); }
    get expandLabel() { return this.props.fullscreen ? _t("Return to creation panel") : _t("Use full screen"); }
}

/** Keeps the actual selected native form/model mounted in every presentation. */
export class RecordCreateDialog extends FormViewDialog {
    static template = "web.RecordCreateDialog";
    static components = { ...FormViewDialog.components, Dialog: CreationSurfaceDialog, RecordCreationHeader };
    static props = {
        close: Function, resModel: String,
        context: { type: Object, optional: true },
        viewId: { type: [Number, Boolean], optional: true },
        title: { type: String, optional: true },
        surface: { type: String, optional: true, validate: value => ["dialog", "sheet"].includes(value) },
        onRecordSaved: { type: Function, optional: true },
    };
    static defaultProps = { surface: "dialog", onRecordSaved: () => {} };

    setup() {
        super.setup();
        this.dialog = useService("dialog");
        this.state = useState({ fullscreen: false, saving: false, closing: false, uncertain: false, saved: false, hasInput: false, error: "" });
        this.record = null;
        this.closeDecision = null;
        Object.assign(this.viewProps, {
            buttonTemplate: "web.RecordCreateDialog.buttons",
            preventCreate: true, preventAutoSave: true,
            onRecordReady: record => { this.record = record; },
            saveRecord: record => this.saveRecord(record),
        });
        useChildSubEnv({ recordCreation: { state: this.state } });
        useBus(this.env.bus, "CLEAR-UNCOMMITTED-CHANGES", event => {
            event.detail.push(() => this.requestClose());
        });
        useExternalListener(window, "beforeunload", event => {
            if (this.state.hasInput || this.record?.dirty || this.state.saving || this.state.uncertain) {
                event.preventDefault();
                event.returnValue = _t("Unsaved creation draft");
            }
        });
    }

    get title() { return this.props.title || _t("New record"); }
    get contentClass() { return "mp-record-create" + (this.props.surface === "sheet" ? " mp-create-sheet" : ""); }
    toggleFullscreen() { this.state.fullscreen = !this.state.fullscreen; }
    onInput() { this.state.hasInput = true; }
    discardRecord(record) { return this.requestClose(record); }

    async saveRecord(record) {
        if (this.state.saving || this.state.closing || this.state.uncertain || this.state.saved) return false;
        this.state.saving = true;
        this.state.error = "";
        try {
            let saved;
            try {
                saved = await record.save({ reload: false });
            } catch (error) {
                if (error instanceof ConnectionLostError || error instanceof ConnectionAbortedError) {
                    this.state.uncertain = true;
                    this.state.error = _t("The save could not be confirmed. The record may already exist. Keep this draft and check the directory before creating another record.");
                    return false;
                }
                throw error;
            }
            if (!saved) return false;
            this.state.saved = true;
            this.state.hasInput = false;
            try {
                await this.props.onRecordSaved(record);
            } catch {
                this.state.error = _t("The record was created, but the directory could not refresh. Close this panel and refresh the directory. Do not create it again.");
                return true;
            }
            this.props.close();
            return true;
        } finally {
            this.state.saving = false;
        }
    }

    async requestClose(record = this.record) {
        if (this.state.saving) return false;
        if (this.closeDecision) return this.closeDecision;
        this.state.closing = true;
        this.closeDecision = this.decideClose(record);
        try { return await this.closeDecision; }
        finally { this.closeDecision = null; this.state.closing = false; }
    }

    async decideClose(record) {
        if (this.state.saved || (!this.state.uncertain && !(await record?.isDirty()))) {
            this.props.close();
            return true;
        }
        return new Promise(resolve => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Discard this creation draft?"),
                body: this.state.uncertain
                    ? _t("The record may already have been created. Closing discards only this local draft and does not undo a saved record. Check the directory before starting another.")
                    : _t("Your unsaved changes will be lost."),
                confirmLabel: _t("Discard draft"), cancelLabel: _t("Keep editing"),
                confirm: () => { this.props.close(); resolve(true); },
                cancel: () => resolve(false),
            }, { onClose: () => resolve(false) });
        });
    }
}
