import { Component } from "@odoo/owl";
import { ICON_NODES } from "@web/interface/icons/lucide";

const aliases = {
    cube: "box", apps: "grid-2x2", users: "users", bars: "menu", edit: "pencil",
    cog: "settings-2", sliders: "sliders-horizontal", columns: "columns-3",
    "angle-left": "chevron-left", "angle-right": "chevron-right",
    "angle-down": "chevron-down", "angle-up": "chevron-up",
    "times": "x", "check-circle": "circle-check", "exclamation-circle": "circle-alert",
    "question-circle": "circle-help", "refresh": "refresh-cw", "trash": "trash-2",
    "trash-o": "trash-2", "close": "x", "ellipsis-v": "ellipsis", "ellipsis-h": "ellipsis",
    "settings-adjust": "sliders-horizontal", "view-list": "list", "view-kanban": "layout-grid",
    "view-pivot": "columns-3", "view-graph": "chart-no-axes-combined", "view-calendar": "calendar",
    "view-cohort": "columns-3", "view-activity": "clock", "view-form": "file-text",
    "sort": "chevrons-up-down", "sort-asc": "arrow-up", "sort-desc": "arrow-down",
    "caret-down": "chevron-down", "caret-right": "chevron-right", "group": "layers",
    print: "printer", "files-o": "copy", "clone": "copy", "circle-o-notch": "loader-circle",
};

/** Only declared semantic names and neutral legacy glyph aliases, never markup or URLs. */
export function iconName(value) {
    if (typeof value !== "string") return "box";
    const name = value.trim().split(/\s+/).find(part => /^(?:fa|oi)-/.test(part) && !/^(?:fa|oi)-(?:fw|lg|[1-5]x|spin|pulse)$/.test(part))
        ?.replace(/^(?:fa|oi)-/, "") || value.trim();
    const mapped = Object.hasOwn(aliases, name) ? aliases[name] : name;
    return Object.hasOwn(ICON_NODES, mapped) ? mapped : "box";
}

/** Shared, locally pinned SVG geometry. The caller owns the control and its label. */
export class Icon extends Component {
    static template = "web.interface.Icon";
    static props = {
        name: String,
        size: { type: Number, optional: true },
        label: { type: String, optional: true },
        directional: { type: Boolean, optional: true },
        className: { type: String, optional: true },
    };
    static defaultProps = { size: 18, directional: false, className: "" };
    get nodes() {
        return ICON_NODES[iconName(this.props.name)];
    }
    get size() { return Number.isFinite(this.props.size) && this.props.size > 0 ? this.props.size : 18; }
}
