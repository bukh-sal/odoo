import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

if (session.mp_stock_profile && !odoo.__mp_client_release__) {
    // Read at startup, reload and selection. Never serve another workspace's cached tree.
    registry.category("menu_sources").add("workspace", async () => {
        const controller = new AbortController();
        const timer = browser.setTimeout(() => controller.abort(), 10000);
        try {
            const response = await browser.fetch("/api/v1/native-navigation", {
                cache: "no-store",
                signal: controller.signal,
                headers: {
                    "X-MP-Workspace": new URLSearchParams(browser.location.search).get("workspace") || "",
                    "X-MP-Client-Release": session.mp_client_release_token,
                },
            });
            if (!response.ok) throw new Error("Navigation unavailable");
            const { data } = await response.json();
            if (!data?.root || !Array.isArray(data.root.children)) throw new Error("Invalid navigation");
            return data;
        } finally {
            browser.clearTimeout(timer);
        }
    });
}
