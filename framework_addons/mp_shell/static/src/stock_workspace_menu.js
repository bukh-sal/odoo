import { Component, onWillStart, xml } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

class StockWorkspaceMenu extends Component {
    static components = { Dropdown, DropdownItem };
    static props = {};
    static template = xml`
        <Dropdown>
            <button type="button" aria-haspopup="menu" t-esc="messages.reference"/>
            <t t-set-slot="content">
                <t t-if="selected">
                    <DropdownItem onSelected="() => this.open('/odoo/action-mp_example_notes.action_notes', selected.id)"><t t-esc="messages.notes"/></DropdownItem>
                    <DropdownItem onSelected="() => this.open('/app/org.example.canvas/', selected.id)"><t t-esc="messages.canvas"/></DropdownItem>
                    <DropdownItem onSelected="() => this.open('/app/settings', selected.id)"><t t-esc="messages.settings"/></DropdownItem>
                    <DropdownItem onSelected="() => this.open('/app/org.example.notes/', selected.id)"><t t-esc="messages.tools"/></DropdownItem>
                </t>
                <span t-if="!workspaces.length" class="dropdown-item-text" t-esc="emptyMessage"/>
            </t>
        </Dropdown>`;

    setup() {
        this.messages = { reference: _t("Reference tools"), notes: _t("Notes"), canvas: _t("Canvas"),
            settings: _t("Platform settings"), tools: _t("Notes tools") };
        this.workspaces = [];
        this.emptyMessage = _t("No workspaces available");
        onWillStart(async () => {
            try {
                const response = await browser.fetch("/api/v1/workspaces", { cache: "no-store" });
                if (!response.ok) {
                    throw new Error();
                }
                this.workspaces = (await response.json()).data;
            } catch {
                this.emptyMessage = _t("Could not load workspaces");
            }
        });
    }

    get selected() {
        const id = new URLSearchParams(browser.location.search).get("workspace");
        return this.workspaces.find((space) => space.id === id);
    }

    get label() {
        return this.selected?.name ?? _t("Choose workspace");
    }

    open(path, workspace) {
        const url = `${path}?${new URLSearchParams({ workspace })}`;
        browser.open(url, "_blank", "noopener");
    }
}

if (session.mp_stock_profile && !odoo.__mp_client_release__) {
    registry.category("systray").add("mp_reference_tools", { Component: StockWorkspaceMenu }, { sequence: 4 });
}
