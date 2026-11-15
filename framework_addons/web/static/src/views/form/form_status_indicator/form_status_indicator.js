import { Component, useEffect, useRef, useState } from "@odoo/owl";
import { useBus } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class FormStatusIndicator extends Component {
    static template = "web.FormStatusIndicator";
    static props = {
        model: Object,
        save: Function,
        discard: Function,
        editing: { type: Boolean, optional: true },
    };

    setup() {
        this.state = useState({
            fieldIsDirty: false,
            pending: null,
        });
        useBus(
            this.props.model.bus,
            "FIELD_IS_DIRTY",
            (ev) => (this.state.fieldIsDirty = ev.detail)
        );
        this.saveButton = useRef("save");
        this.root = useRef("statusRoot");
        this.statusLabel = useRef("statusLabel");
        // The normal button executor restores disabled attributes after its call.
        // Reassert validity after a pending command, including a refused save.
        useEffect(() => {
            if (this.saveButton.el) {
                this.saveButton.el.disabled = !!this.state.pending ||
                    (!this.props.model.root.isNew && this.indicatorMode === "invalid");
            }
        }, () => [this.props.model.root.isValid, this.props.model.root.isNew,
            this.state.fieldIsDirty, this.state.pending]);
    }

    get displayButtons() {
        return this.indicatorMode !== "saved" || !!this.state.pending || !!this.props.editing;
    }

    get indicatorMode() {
        const { isNew, isValid } = this.props.model.root;
        const isDirty = this.props.model.root.dirty || this.state.fieldIsDirty;
        if (!isValid) return "invalid";
        if (isNew || isDirty) {
            return "dirty";
        }
        return "saved";
    }

    get status() {
        if (this.state.pending === "save") return _t("Saving changes…");
        if (this.state.pending === "discard") return _t("Discarding changes…");
        if (this.indicatorMode === "invalid") return _t("Check fields");
        if (this.props.model.root.isNew) return _t("New record");
        if (this.indicatorMode === "saved" && this.props.editing) return _t("Editing");
        return this.indicatorMode === "dirty" ? _t("Unsaved changes") : _t("Saved");
    }

    get saveLabel() {
        return this.props.editing && this.indicatorMode === "saved" ? _t("Done") : _t("Save changes");
    }

    get discardLabel() {
        return this.props.editing && this.indicatorMode === "saved" ? _t("Cancel") : _t("Discard");
    }

    async perform(kind, callback) {
        if (this.state.pending) return;
        const focused = this.root.el?.contains(document.activeElement);
        this.state.pending = kind;
        try { return await callback(); }
        finally {
            this.state.pending = null;
            if (focused && (document.activeElement === document.body || this.root.el?.contains(document.activeElement))) {
                this.statusLabel.el?.focus({ preventScroll: true });
            }
        }
    }

    async discard() {
        return this.perform("discard", () => this.props.discard());
    }
    async save() {
        return this.perform("save", () => this.props.save());
    }
}
