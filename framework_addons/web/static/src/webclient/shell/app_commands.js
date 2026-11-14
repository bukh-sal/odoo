import { registry } from "@web/core/registry";
import { DefaultCommandItem } from "@web/core/commands/command_palette";
import { _t } from "@web/core/l10n/translation";
import { session } from "@web/session";

registry.category("command_categories").add("workspace_apps", {
    name: _t("Applications"), namespace: "default", sequence: 20,
});
registry.category("command_provider").add("workspace_apps", {
    async provide(env) {
        if (!session.mp_stock_profile) return [];
        const menu = env.services.menu;
        await menu.reload();
        return menu.getApps().map(app => ({
            Component: DefaultCommandItem,
            category: "workspace_apps",
            name: app.name,
            action: () => menu.selectMenu(app),
        }));
    },
});
