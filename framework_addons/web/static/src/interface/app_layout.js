import { Component, useChildSubEnv, useEffect, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { uniqueId } from "@web/core/utils/functions";
import { useService } from "@web/core/utils/hooks";
import { Icon } from "@web/interface/icon";
import { useContextPreference } from "@web/interface/context_preference";

/** Context presentation only. Slots keep the owning app's state and components mounted. */
export class AppLayout extends Component {
    static template = "web.interface.AppLayout";
    static components = { Icon };
    static props = {
        contextTitle: String,
        contextKey: { type: String, optional: true },
        contentLabel: { type: String, optional: true },
        showContext: { type: Boolean, optional: true },
        className: { type: String, optional: true },
        slots: { type: Object, optional: true },
    };
    static defaultProps = { showContext: true, className: "", slots: {} };

    setup() {
        this.ui = useService("ui");
        this.state = useState({ contextOpen: false });
        this.contextPreference = useContextPreference(() => this.props.contextKey);
        useChildSubEnv({ interfaceContextTarget: null });
        this.contextId = uniqueId("mp-app-context-");
        this.context = useRef("context");
        this.content = useRef("content");
        this.trigger = useRef("trigger");
        this.focusAfterClose = null;
        useEffect(() => {
            if (!this.props.showContext && this.state.contextOpen) {
                this.closeContext("content");
                return;
            }
            if (this.state.contextOpen) this.context.el?.focus();
            else if (this.focusAfterClose === "trigger") this.trigger.el?.focus();
            else if (this.focusAfterClose === "content") this.content.el?.focus();
            this.focusAfterClose = null;
        }, () => [this.state.contextOpen, this.props.showContext, this.contextCollapsed]);
        useEffect(() => {
            if (!this.ui.isSmall) this.state.contextOpen = false;
            if (this.contextCollapsed && this.context.el?.contains(document.activeElement)) this.trigger.el?.focus();
        }, () => [this.ui.isSmall, this.contextCollapsed]);
    }

    get contentLabel() { return this.props.contentLabel || _t("Work area"); }
    get toolbarTarget() { return this.env.inDialog ? null : this.env.interfaceContextTarget; }
    get contextCollapsed() { return !this.ui.isSmall && this.contextPreference.collapsed; }
    get contextExpanded() { return this.ui.isSmall ? this.state.contextOpen : !this.contextPreference.collapsed; }
    get toggleLabel() {
        return this.contextExpanded ? _t("Collapse %s navigation", this.props.contextTitle) : _t("Expand %s navigation", this.props.contextTitle);
    }
    toggleContext() {
        if (!this.props.showContext) return;
        if (!this.ui.isSmall) {
            this.focusAfterClose = "trigger";
            this.contextPreference.toggle();
            return;
        }
        if (this.state.contextOpen) this.closeContext("trigger");
        else this.state.contextOpen = true;
    }
    closeContext(focus) {
        this.focusAfterClose = focus;
        this.state.contextOpen = false;
    }
    onContextKeydown(event) {
        if (event.key === "Escape" && !event.defaultPrevented && this.state.contextOpen) {
            event.preventDefault();
            event.stopPropagation();
            this.closeContext("trigger");
        }
    }
    onContextSelection(event) {
        if (!this.state.contextOpen || event.ctrlKey || event.metaKey || event.shiftKey || event.button) return;
        const destination = event.target?.closest?.("[data-mp-context-destination]");
        if (destination && this.context.el?.contains(destination)) this.closeContext("content");
    }
}
