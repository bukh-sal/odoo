import { registry } from "@web/core/registry";
import { RelationalModel } from "@web/model/relational_model/relational_model";
import { formView } from "@web/views/form/form_view";
import { session } from "@web/session";

class NoteRecord extends RelationalModel.Record {
    get context() {
        const context = super.context;
        // Use the revision in this form's snapshot for the server's compare-and-swap.
        const revision = this.data?.revision;
        if (this.resModel === "mp.example.note" && this.resId && Number.isInteger(revision)) {
            return { ...context, expected_revision: revision };
        }
        return context;
    }
}

class NoteFormModel extends RelationalModel {
    static Record = NoteRecord;
}

const stockClient = session.mp_client_release_token && !odoo.__mp_client_release__;
registry.category("views").add("mp_notes_revision_form", {
    ...formView,
    Model: stockClient ? NoteFormModel : formView.Model,
});
