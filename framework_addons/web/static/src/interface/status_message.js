import { Component } from "@odoo/owl";

/** No fetch/retry policy: state, sanitized text and action slots belong to the caller. */
export class StatusMessage extends Component {
    static template = "web.interface.StatusMessage";
    static props = {
        kind: { type: String, optional: true, validate: value => ["loading", "empty", "info", "success", "warning", "error"].includes(value) },
        title: { type: String, optional: true },
        message: { type: String, optional: true },
        slots: { type: Object, optional: true },
    };
    static defaultProps = { kind: "info", slots: {} };
    get role() { return this.props.kind === "error" ? "alert" : "status"; }
}
