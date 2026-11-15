import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { Icon } from "@web/interface/icon";

/** The owner supplies real destinations and its existing action/leave callbacks. */
export class BreadcrumbTrail extends Component {
    static template = "web.interface.BreadcrumbTrail";
    static components = { Icon };
    static props = { items: Array };
    get label() { return _t("Breadcrumb"); }
    href(item) {
        return typeof item.href === "string" && !/[\\\x00-\x20\x7f]/.test(item.href) &&
            (/^\/(?!\/)/.test(item.href) || /^https?:\/\//.test(item.href)) ? item.href : undefined;
    }
    select(event, item) {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button) return;
        if (item.onSelected) { event.preventDefault(); return item.onSelected(); }
    }
}
