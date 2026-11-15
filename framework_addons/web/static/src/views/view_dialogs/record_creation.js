import { RecordCreateDialog } from "./record_create_dialog";

/** Native author presentation only; validation and permission remain server-owned. */
export function creationSurface(value) {
    const surface = value === undefined ? "page" : value;
    if (!["page", "dialog", "sheet"].includes(surface)) {
        throw new Error("create_surface must be page, dialog or sheet");
    }
    return surface;
}

export function openRecordCreation({ context, resModel, title, viewId, dialog, openPage, onRecordSaved }) {
    const surface = creationSurface(context.create_surface);
    if (surface === "page") return openPage();
    const createContext = { ...context };
    if (context.create_form_view_ref !== undefined) {
        if (typeof context.create_form_view_ref !== "string" || !context.create_form_view_ref.trim() || context.create_form_view_ref.length > 256) {
            throw new Error("create_form_view_ref must be a nonempty native form reference");
        }
        createContext.form_view_ref = context.create_form_view_ref;
        viewId = false;
    }
    return new Promise((resolve) => {
        dialog.add(RecordCreateDialog, {
            resModel, title, context: createContext, viewId: viewId || false,
            surface, onRecordSaved: onRecordSaved || (() => {}),
        }, { onClose: resolve });
    });
}
