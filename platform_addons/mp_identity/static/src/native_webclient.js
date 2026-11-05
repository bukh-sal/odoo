import { router } from "@web/core/browser/router";
import { rpc } from "@web/core/network/rpc";
import { session } from "@web/session";

const token = session.mp_client_release_token;
if (token && !odoo.__mp_client_release__) {
    // Each stock WebClient page holds its own workspace and release. Open a new
    // page to change context, so an existing action cannot cross workspaces.
    const workspace = new URLSearchParams(window.location.search).get("workspace");
    router.addLockedKey("workspace");
    const nativeRPC = rpc._rpc;
    rpc._rpc = function (url, params, settings) {
        if (!url.startsWith("/web/dataset/")) {
            return nativeRPC.call(this, url, params, settings);
        }
        return nativeRPC.call(this, url, params, {
            ...settings,
            cache: false,
            headers: {
                ...settings.headers,
                "X-MP-Client-Release": token,
                ...(workspace ? { "X-MP-Workspace": workspace } : {}),
            },
        });
    };
}
