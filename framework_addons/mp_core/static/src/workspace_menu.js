import { Component, onWillStart, xml } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

// Navigation is a convenience, never an authority cache. Every request in the
// new page still resolves current membership, feature state and release pins.
export class WorkspaceMenu extends Component {
    static components = { Dropdown, DropdownItem };
    static props = {};
    static template = xml`
        <Dropdown>
            <button type="button" class="mp_stock_workspace" aria-haspopup="menu"
                t-att-title="messages.newTab" t-esc="label"/>
            <t t-set-slot="content">
                <DropdownItem t-foreach="workspaces" t-as="space" t-key="space.id"
                    onSelected="() => this.open(space.id)">
                    <span t-esc="space.name"/>
                </DropdownItem>
                <t t-if="selected">
                    <div class="dropdown-divider" role="separator"/>
                    <DropdownItem onSelected="() => this.open(selected.id, true)">
                        <t t-esc="messages.jobs"/>
                    </DropdownItem>
                </t>
                <span t-if="!workspaces.length" class="dropdown-item-text" t-esc="emptyMessage"/>
            </t>
        </Dropdown>`;

    setup() {
        this.messages = { newTab: _t("Open a workspace in a new tab"), jobs: _t("My background jobs") };
        this.workspaces = [];
        this.emptyMessage = _t("No workspaces available");
        onWillStart(async () => {
            const controller = new AbortController();
            const timer = browser.setTimeout(() => controller.abort(), 10000);
            try {
                const response = await browser.fetch("/api/v1/workspaces", {
                    cache: "no-store", signal: controller.signal,
                });
                if (!response.ok) {
                    throw new Error("Workspace list unavailable");
                }
                const rows = (await response.json()).data;
                const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
                if (!Array.isArray(rows) || rows.some((row) => !row || typeof row.name !== "string" ||
                    typeof row.id !== "string" || !uuid.test(row.id)) ||
                    new Set(rows.map((row) => row.id)).size !== rows.length) {
                    throw new Error("Invalid workspace list");
                }
                this.workspaces = rows.map(({ id, name }) => ({ id, name }));
            } catch {
                this.emptyMessage = _t("Could not load workspaces");
            } finally {
                browser.clearTimeout(timer);
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

    open(workspace, jobs = false) {
        if (!this.workspaces.some((space) => space.id === workspace)) {
            return;
        }
        // Do not carry the old action/record into another workspace or mutate
        // shared session state. Existing forms and their drafts stay untouched.
        const path = jobs ? "/odoo/action-mp_core.action_job_history" : "/odoo";
        browser.open(`${path}?${new URLSearchParams({ workspace })}`, "_blank", "noopener");
    }
}

if (session.mp_stock_profile && !odoo.__mp_client_release__) {
    registry.category("systray").add("mp_stock_workspace", { Component: WorkspaceMenu }, { sequence: 5 });
}
