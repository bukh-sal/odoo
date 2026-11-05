import { browser } from "@web/core/browser/browser";
import { router } from "@web/core/browser/router";
import { _t } from "@web/core/l10n/translation";
import { rpc, rpcBus } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useBus } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { ListController } from "@web/views/list/list_controller";
import { session } from "@web/session";

function guardDirtyExit(Controller, record) {
    patch(Controller.prototype, {
        setup() {
            super.setup(...arguments);
            useBus(this.model.bus, "FIELD_IS_DIRTY", (event) => {
                this.mpDirtyFieldRecord = event.detail ? record(this) : null;
            });
        },
        beforeUnload(event) {
            const current = record(this);
            if (current && (current.dirty || this.mpDirtyFieldRecord === current || !current.isValid)) {
                event.preventDefault();
                event.returnValue = "Unsaved changes";
            }
        },
    });
}

const token = session.mp_client_release_token;
if (token && !odoo.__mp_client_release__) {
    if (session.mp_stock_profile) {
        // The native unload beacon cannot carry the pinned release and workspace headers.
        guardDirtyExit(FormController, (controller) => controller.model.root);
        guardDirtyExit(ListController, (controller) => controller.editedRecord);
    }
    const releaseMismatch = "odoo.addons.mp_identity.release.ClientReleaseMismatch";
    const sessionExpired = "odoo.http.SessionExpiredException";
    const isRecoveryError = (error) => error?.exceptionName === releaseMismatch ||
        (session.mp_stock_profile && error?.exceptionName === sessionExpired);
    registry.category("services").add("mp_native_release_notice", {
        dependencies: ["notification"],
        start(env, { notification }) {
            let noticeOpen = false;
            rpcBus.addEventListener("RPC:RESPONSE", ({ detail }) => {
                if (noticeOpen || !isRecoveryError(detail.error)) {
                    return;
                }
                noticeOpen = true;
                const expired = detail.error.exceptionName === sessionExpired;
                notification.add(
                    expired ? _t("Sign in in a new tab. Keep this tab open to copy any unsaved changes.") :
                        _t("Open the current release in a new tab. Keep this tab open to copy any unsaved changes."),
                    {
                        title: expired ? _t("Session expired") : _t("Platform updated"),
                        type: "warning",
                        sticky: true,
                        onClose: () => { noticeOpen = false; },
                        buttons: [{
                            name: expired ? _t("Sign in again") : _t("Open current release"),
                            primary: true,
                            onClick: () => browser.open(browser.location.href, "_blank", "noopener"),
                        }],
                    }
                );
            });
        },
    });
    registry.category("error_handlers").add("mp_native_release_mismatch", (env, error, originalError) => {
        if (isRecoveryError(originalError)) {
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
