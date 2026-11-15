import { Component } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { Icon } from "@web/interface/icon";

export class Breadcrumbs extends Component {
    static template = "web.Breadcrumbs";
    static components = { Dropdown, DropdownItem, Icon };
    static props = {
        breadcrumbs: Array,
        headingLevel: { type: Number, optional: true },
        slots: { type: Object, optional: true },
    };

    select(event, breadcrumb) {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button) return;
        event.preventDefault();
        return breadcrumb.onSelected();
    }

    getBreadcrumbTooltip({ isFormView, name }) {
        if (isFormView) {
            return _t('Back to "%s" form', name);
        }
        return _t('Back to "%s"', name);
    }
}
