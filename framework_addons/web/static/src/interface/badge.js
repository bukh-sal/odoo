import { Component } from "@odoo/owl";
import { Icon } from "@web/interface/icon";

const VARIANTS = new Set(["neutral", "info", "success", "warning", "danger"]);

/** A visual label, never a source of permissions or application state. */
export class Badge extends Component {
    static template = "web.interface.Badge";
    static components = { Icon };
    static props = {
        label: String,
        variant: { type: String, optional: true, validate: value => VARIANTS.has(value) },
        icon: { type: String, optional: true },
    };
    static defaultProps = { variant: "neutral" };
}
