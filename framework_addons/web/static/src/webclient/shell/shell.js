import { Component, useExternalListener, useRef, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { useBus, useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { ErrorHandler } from "@web/core/utils/components";
import { UserMenu } from "@web/webclient/user_menu/user_menu";
import { user } from "@web/core/user";

/** Presentation over the existing menu/action services and their leave lifecycle. */
export class Shell extends Component {
    static template = "web.Shell";
    static components = { Dropdown, DropdownItem, ErrorHandler, UserMenu };
    static props = { slots: Object };

    setup() {
        this.menu = useService("menu");
        this.action = useService("action");
        this.command = useService("command");
        this.state = useState({ revision: 0, contextOpen: false });
        this.contextTrigger = useRef("contextTrigger");
        useBus(this.env.bus, "MENUS:APP-CHANGED", () => this.state.revision++);
        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => {
            this.state.revision++;
            this.state.contextOpen = false;
        });
        useBus(registry.category("systray"), "UPDATE", () => this.state.revision++);
        useExternalListener(window, "focus", () => this.menu.reload());
    }

    get apps() { return this.menu.getApps(); }
    get current() {
        const app = this.menu.getCurrentApp();
        return this.apps.find(item => item.id === app?.id);
    }
    get nativeContext() {
        return this.current && !registry.category("shell_context").contains(this.action.currentController?.action?.tag);
    }
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
        return "fa fa-" + (/^[a-z][a-z0-9-]*$/.test(icon || "") ? icon : "cube");
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
    closeContext(event) {
        if (event.key === "Escape") {
            event.stopPropagation();
            this.state.contextOpen = false;
            this.contextTrigger.el?.focus();
        }
    }
    handleItemError(error) { throw error; }
}
