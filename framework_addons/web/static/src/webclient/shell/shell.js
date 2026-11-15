import { Component, useEffect, useExternalListener, useRef, useState, useSubEnv } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { useBus, useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { ErrorHandler } from "@web/core/utils/components";
import { UserMenu } from "@web/webclient/user_menu/user_menu";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { PageHeader } from "@web/interface/page_header";
import { StatusMessage } from "@web/interface/status_message";
import { Icon } from "@web/interface/icon";
import { useContextPreference } from "@web/interface/context_preference";

/** Presentation over the existing menu/action services and their leave lifecycle. */
export class Shell extends Component {
    static template = "web.Shell";
    static components = { Dropdown, DropdownItem, ErrorHandler, UserMenu, PageHeader, StatusMessage, Icon };
    static props = { slots: Object };

    setup() {
        this.menu = useService("menu");
        this.action = useService("action");
        this.command = useService("command");
        this.ui = useService("ui");
        this.state = useState({ revision: 0, contextOpen: false });
        useSubEnv({ interfaceContextTarget: ".mp-shell-context-controls" });
        this.contextPreference = useContextPreference(() => this.current?.pluginID);
        this.contextTrigger = useRef("contextTrigger");
        this.context = useRef("context");
        useEffect(() => {
            if (this.state.contextOpen) this.context.el?.focus();
        }, () => [this.state.contextOpen]);
        useEffect(() => {
            if (!this.ui.isSmall) this.state.contextOpen = false;
            if (this.contextCollapsed && this.context.el?.contains(document.activeElement)) this.contextTrigger.el?.focus();
        }, () => [this.ui.isSmall, this.contextCollapsed]);
        useBus(this.env.bus, "MENUS:APP-CHANGED", () => this.state.revision++);
        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => {
            this.state.revision++;
            this.state.contextOpen = false;
        });
        useBus(registry.category("systray"), "UPDATE", () => this.state.revision++);
        useExternalListener(window, "focus", () => this.menu.reload());
    }

    get apps() { return this.menu.getApps(); }
    get workspaceTitle() { return _t("Your workspace"); }
    get noAppsTitle() { return _t("No applications available in this workspace"); }
    get noAppsDescription() { return _t("Background jobs and account options remain available from the workspace menu."); }
    get emptyChooserLabel() {
        return this.menu.unavailable ? _t("Applications unavailable. Reload to try again.") : _t("No applications available in this workspace.");
    }
    get current() {
        const app = this.menu.getCurrentApp();
        return this.apps.find(item => item.id === app?.id);
    }
    get nativeContext() {
        return !this.blocked && this.current && !registry.category("shell_context").contains(this.action.currentController?.action?.tag);
    }
    get blocked() { return this.menu.unavailable || this.menu.currentAppUnavailable; }
    get sections() { return this.current ? this.menu.getMenuAsTree(this.current.id).childrenTree : []; }
    get utilities() {
        return registry.category("systray").getEntries()
            .filter(([key]) => key !== "burger_menu" &&
                (key !== "SwitchCompanyMenu" || user.allowedCompaniesWithAncestors.length > 1))
            .filter(([, item]) => item.Component !== UserMenu && (!item.isDisplayed || item.isDisplayed(this.env)))
            .map(([key, item]) => ({ key, ...item })).reverse();
    }
    icon(app) {
        const icon = app.appIcon;
        return /^[a-z][a-z0-9-]*$/.test(icon || "") ? icon : "box";
    }
    href(menu) {
        const path = menu.actionPath || "action-" + menu.actionID;
        const workspace = new URLSearchParams(browser.location.search).get("workspace");
        return "/odoo/" + encodeURIComponent(path) + (workspace ? "?workspace=" + encodeURIComponent(workspace) : "");
    }
    async select(event, menu) {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.button) return;
        event.preventDefault();
        await this.menu.selectMenu(menu);
    }
    active(menu) {
        return menu.actionID === this.action.currentController?.action?.id ? "page" : undefined;
    }
    openCommands() { this.command.openMainPalette(); }
    reopenWorkspace() {
        const workspace = new URLSearchParams(browser.location.search).get("workspace");
        browser.open("/odoo" + (workspace ? "?workspace=" + encodeURIComponent(workspace) : ""), "_blank", "noopener");
    }
    get contextCollapsed() { return !this.ui.isSmall && this.contextPreference.collapsed; }
    get contextExpanded() { return this.ui.isSmall ? this.state.contextOpen : !this.contextPreference.collapsed; }
    get contextToggleLabel() {
        return this.contextExpanded ? _t("Collapse %s navigation", this.current?.name || "") : _t("Expand %s navigation", this.current?.name || "");
    }
    toggleContext() {
        if (this.ui.isSmall) this.state.contextOpen = !this.state.contextOpen;
        else this.contextPreference.toggle();
    }
    closeContext(event) {
        if (event.key === "Escape" && !event.defaultPrevented && this.state.contextOpen) {
            event.preventDefault();
            event.stopPropagation();
            this.state.contextOpen = false;
            this.contextTrigger.el?.focus();
        }
    }
    handleItemError(error) { throw error; }
}
