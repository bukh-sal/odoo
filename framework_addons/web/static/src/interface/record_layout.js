import { Component } from "@odoo/owl";

/** The owner supplies already-authorized content; empty aside has no reserved column. */
export class RecordLayout extends Component {
    static template = "web.interface.RecordLayout";
    static props = {
        slots: { type: Object, optional: true },
        showAside: { type: Boolean, optional: true },
        asideLabel: { type: String, optional: true },
    };
    static defaultProps = { slots: {}, showAside: true };
}

export class RecordHeader extends Component {
    static template = "web.interface.RecordHeader";
    static props = {
        title: String,
        subtitle: { type: String, optional: true },
        initials: { type: String, optional: true },
        slots: { type: Object, optional: true },
    };
    static defaultProps = { slots: {} };
}
