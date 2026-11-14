import { Component, useExternalListener, useRef, xml } from "@odoo/owl";

/** Inline query controls. The owning view supplies labelled inputs and owns the query. */
export class QueryDisclosure extends Component {
    static props = { label: String, count: { type: Number, optional: true }, slots: Object };
    static template = xml`
        <details class="mp-query" t-ref="root" t-on-keydown="onKeydown">
            <summary class="mp-query-trigger" t-ref="trigger">
                <i class="fa fa-sliders" aria-hidden="true"/>
                <t t-esc="props.label"/>
                <span t-if="props.count" class="mp-query-count" t-esc="props.count"/>
            </summary>
            <div class="mp-query-fields"><t t-slot="default"/></div>
        </details>`;

    setup() {
        this.root = useRef("root");
        this.trigger = useRef("trigger");
        useExternalListener(window, "pointerdown", this.closeOutside, { capture: true });
        useExternalListener(window, "focusin", this.closeOutside);
    }

    closeOutside(event) {
        const root = this.root.el;
        if (root?.open && !root.contains(event.target)) {
            root.open = false;
        }
    }

    onKeydown(event) {
        if (event.key === "Escape" && this.root.el.open) {
            event.stopPropagation();
            this.root.el.open = false;
            this.trigger.el.focus();
        }
    }
}
