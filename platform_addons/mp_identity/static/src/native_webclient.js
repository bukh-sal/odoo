import { browser } from "@web/core/browser/browser";
import { router } from "@web/core/browser/router";
import { _t } from "@web/core/l10n/translation";
import { rpc, rpcBus } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

const token = session.mp_client_release_token;
if (token && !odoo.__mp_client_release__) {
    const isReleaseMismatch = (error) =>
        error?.exceptionName === "odoo.addons.mp_identity.release.ClientReleaseMismatch";
    registry.category("services").add("mp_native_release_notice", {
        dependencies: ["notification"],
        start(env, { notification }) {
            let noticeOpen = false;
            rpcBus.addEventListener("RPC:RESPONSE", ({ detail }) => {
                if (noticeOpen || !isReleaseMismatch(detail.error)) {
                    return;
                }
                noticeOpen = true;
                notification.add(
                    _t("Open the current release in a new tab. Keep this tab open to copy any unsaved changes."),
                    {
                        title: _t("Platform updated"),
                        type: "warning",
                        sticky: true,
                        onClose: () => { noticeOpen = false; },
                        buttons: [{
                            name: _t("Open current release"),
                            primary: true,
                            onClick: () => browser.open(browser.location.href, "_blank", "noopener"),
                        }],
                    }
                );
            });
        },
    });
    registry.category("error_handlers").add("mp_native_release_mismatch", (env, error, originalError) => {
        if (isReleaseMismatch(originalError)) {
            error.event?.preventDefault();
            return true;
        }
        return false;
    }, { sequence: 96 });

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
