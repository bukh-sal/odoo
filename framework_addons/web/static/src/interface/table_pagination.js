import { Icon } from "@web/interface/icon";
import { Component, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

/** A bounded page window. Gaps are inert markers, never destinations. */
export function pageWindow(current, total) {
    const count = Math.max(1, Math.floor(total));
    const page = Math.min(count, Math.max(1, Math.floor(current)));
    const values = count <= 7 ? Array.from({ length: count }, (_, i) => i + 1)
        : [...new Set([1, count, page - 1, page, page + 1])]
            .filter(value => value >= 1 && value <= count).sort((a, b) => a - b);
    const result = [];
    for (const value of values) {
        const previous = result.at(-1);
        if (typeof previous === "number" && value - previous === 2) result.push(previous + 1);
        else if (typeof previous === "number" && value - previous > 2) result.push(`gap-${previous}`);
        result.push(value);
    }
    return result;
}

export class TablePagination extends Component {
    static components = { Icon };
    static template = "web.interface.TablePagination";
    static props = {
        offset: Number, limit: Number, total: Number, onUpdate: Function,
        updateTotal: { type: Function, optional: true },
        label: { type: String, optional: true },
        isGrouped: { type: Boolean, optional: true },
        withAccessKey: { type: Boolean, optional: true },
        isEditable: { type: Boolean, optional: true },
        withPageSize: { type: Boolean, optional: true },
    };
    static defaultProps = { withAccessKey: true };
    setup() {
        this.root = useRef("pagination");
        this.state = useState({ busy: false, error: "" });
    }
    get valid() {
        return [this.props.offset, this.props.limit, this.props.total].every(Number.isSafeInteger)
            && this.props.offset >= 0 && this.props.limit > 0 && this.props.total >= 0;
    }
    get current() { return this.valid ? Math.floor(this.props.offset / this.props.limit) + 1 : 1; }
    get pageCount() { return this.valid ? Math.max(1, Math.ceil(this.props.total / this.props.limit)) : 1; }
    get limited() { return !!this.props.updateTotal; }
    get pages() { return this.limited ? [this.current] : pageWindow(this.current, this.pageCount); }
    get showControls() { return this.valid && (this.limited || this.pageCount > 1 || this.props.offset > 0); }
    get showPageSize() {
        return this.props.withPageSize && this.props.isEditable !== false && !this.props.isGrouped
            && this.valid && this.props.total > 0;
    }
    get pageSizes() { return [...new Set([10, 25, 50, 100, this.props.limit])].sort((a, b) => a - b); }
    async changePageSize(event) {
        const limit = Number(event.target.value);
        // Keep the select controlled by the native owner, including veto/failure.
        event.target.value = String(this.props.limit);
        if (!this.showPageSize || !this.pageSizes.includes(limit) || limit === this.props.limit) return;
        await this.perform(() => this.props.onUpdate({ offset: 0, limit }, true), ".mp-pagination-size select");
        event.target.value = String(this.props.limit);
    }
    get label() { return this.props.label || _t("Table pages"); }
    get canPrevious() { return this.valid && this.props.offset > 0; }
    get previousPage() { return this.limited ? this.current - 1 : Math.min(this.current - 1, this.pageCount); }
    get canNext() { return this.valid && (this.limited || this.current < this.pageCount); }
    get range() {
        if (!this.valid) return _t("Result count unavailable");
        if (!this.props.total) return this.props.isGrouped ? _t("No groups") : _t("No records");
        if (this.props.offset >= this.props.total && !this.limited) return this.props.isGrouped
            ? _t("No groups on this page · %s groups in total", this.props.total)
            : _t("No records on this page · %s records in total", this.props.total);
        const end = Math.min(this.props.total, this.props.offset + this.props.limit);
        if (this.props.isGrouped) return this.limited
            ? _t("%s–%s · more groups may be available", this.props.offset + 1, end)
            : _t("%s–%s of %s groups", this.props.offset + 1, end, this.props.total);
        return this.limited ? _t("%s–%s · more results may be available", this.props.offset + 1, end)
            : _t("%s–%s of %s records", this.props.offset + 1, end, this.props.total);
    }
    pageLabel(page) { return _t("Page %s", page); }
    async perform(callback, focusSelector) {
        if (this.state.busy || !this.valid) return;
        const focused = this.root.el?.contains(document.activeElement);
        this.state.busy = true; this.state.error = "";
        try { await callback(); }
        catch (error) { this.state.error = error.message || _t("Could not load this page. Your current results are kept."); }
        finally {
            this.state.busy = false;
            if (focused && (document.activeElement === document.body || this.root.el?.contains(document.activeElement))) {
                this.root.el?.querySelector(focusSelector || '[aria-current="page"], .mp-pagination-range')?.focus({ preventScroll: true });
            }
        }
    }
    async go(page) {
        if (!this.valid || !Number.isSafeInteger(page) || page < 1 || page === this.current
            || (!this.limited && page > this.pageCount) || (this.limited && page > this.current + 1)) return;
        const offset = (page - 1) * this.props.limit;
        if (!Number.isSafeInteger(offset)) return;
        // The model owns the resulting offset. Never optimistically advance on a refused save.
        await this.perform(() => this.props.onUpdate({ offset, limit: this.props.limit }, true));
    }
    count() { if (this.props.updateTotal) return this.perform(() => this.props.updateTotal()); }
}
