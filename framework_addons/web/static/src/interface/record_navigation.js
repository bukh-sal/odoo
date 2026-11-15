import { _t } from "@web/core/l10n/translation";
import { TablePagination } from "@web/interface/table_pagination";

/** Traverse the form's loaded IDs, using its existing save/load callback. */
export class RecordNavigation extends TablePagination {
    static template = "web.interface.RecordNavigation";
    get valid() { return super.valid && this.props.limit === 1; }
    get label() { return this.props.label || _t("Record navigation"); }
    get range() {
        if (!this.valid) return _t("Record position unavailable");
        if (!this.props.total) return _t("No loaded records");
        if (this.props.offset >= this.props.total) return _t("No loaded record at this position");
        return _t("Record %s of %s loaded", this.current, this.props.total);
    }
}
