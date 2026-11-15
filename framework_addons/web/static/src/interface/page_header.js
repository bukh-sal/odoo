import { Component } from "@odoo/owl";
import { BreadcrumbTrail } from "@web/interface/breadcrumb_trail";

/** Shared page hierarchy. Applications supply the title, counts and actions. */
export class PageHeader extends Component {
    static template = "web.interface.PageHeader";
    static components = { BreadcrumbTrail };
    static props = {
        title: String,
        eyebrow: { type: String, optional: true },
        subtitle: { type: String, optional: true },
        breadcrumbs: { type: Array, optional: true },
        count: { type: Number, optional: true },
        countLabel: { type: String, optional: true },
        slots: { type: Object, optional: true },
    };
    static defaultProps = { slots: {} };
}
