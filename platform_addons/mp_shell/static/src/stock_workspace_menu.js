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
            <button type="button" aria-haspopup="menu" t-esc="label"/>
            <t t-set-slot="content">
                <DropdownItem t-foreach="workspaces" t-as="space" t-key="space.id"
                    onSelected="() => this.open('/odoo', space.id)">
                    <span t-esc="space.name"/>
                </DropdownItem>
                <t t-if="selected">
                    <div class="dropdown-divider" role="separator"/>
                    <DropdownItem onSelected="() => this.open('/odoo/action-mp_example_notes.action_notes', selected.id)">Notes</DropdownItem>
                    <DropdownItem onSelected="() => this.open('/app/org.example.canvas/', selected.id)">Canvas</DropdownItem>
                    <DropdownItem onSelected="() => this.open('/app/settings', selected.id)">Platform settings</DropdownItem>
                    <DropdownItem onSelected="() => this.open('/app/org.example.notes/', selected.id)">Notes tools</DropdownItem>
                </t>
                <span t-if="!workspaces.length" class="dropdown-item-text" t-esc="emptyMessage"/>
            </t>
        </Dropdown>`;

    setup() {
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
    registry.category("systray").add("mp_stock_workspace", { Component: StockWorkspaceMenu }, { sequence: 5 });
}
