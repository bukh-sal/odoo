import { deepEqual } from "@web/core/utils/objects";

const RELATED_ACTION_KEYS = new Set([
    "type", "target", "res_model", "res_id", "views", "context", "name", "display_name",
    // Added by the action service's normal preprocessing.
    "_originalAction", "jsId", "controllers", "domain",
]);

/**
 * Prefer an exact, real form ancestor for a plain related-record link. This is
 * only a same-page navigation choice: restore still owns the leave guard and
 * the reconstructed form performs its ordinary current server reads.
 * Unknown action/option semantics deliberately fall back to a new action.
 */
export function findRecordAncestor(stack, action, options, userContext) {
    if (
        options.preferExistingRecord !== true || options.newWindow ||
        Object.keys(options).some(key => !["preferExistingRecord", "newWindow"].includes(key)) ||
        action.type !== "ir.actions.act_window" || action.target !== "current" ||
        typeof action.res_model !== "string" || !action.res_model ||
        Object.keys(action).some(key => !RELATED_ACTION_KEYS.has(key)) ||
        (action.domain !== undefined && (!Array.isArray(action.domain) || action.domain.length !== 0)) ||
        !Number.isSafeInteger(action.res_id) || action.res_id <= 0 ||
        !Array.isArray(action.views) || action.views.length !== 1 ||
        !Array.isArray(action.views[0]) || action.views[0].length !== 2 ||
        action.views[0][1] !== "form" ||
        !(action.views[0][0] === false || (Number.isSafeInteger(action.views[0][0]) && action.views[0][0] > 0))
    ) {
        return;
    }
    const viewId = action.views[0][0] || false;
    const context = { ...userContext, ...action.context };
    // The current controller is not an ancestor. Nearest matching form wins.
    for (let index = stack.length - 2; index >= 0; index--) {
        const controller = stack[index];
        const { props, exportedState, action: previous } = controller;
        if (
            controller.virtual || !props || props.type !== "form" ||
            previous?.type !== "ir.actions.act_window" || previous.target !== "current" ||
            props.resModel !== action.res_model
        ) {
            continue;
        }
        // Match restore's exported-ID precedence, including an explicit false.
        const resId = exportedState && "resId" in exportedState ? exportedState.resId : props.resId;
        const previousViewId = props.viewId ?? previous.views.find(view => view[1] === "form")?.[0];
        if (
            resId === action.res_id && (previousViewId || false) === viewId &&
            deepEqual({ ...userContext, ...props.context }, context)
        ) {
            return controller;
        }
    }
}
