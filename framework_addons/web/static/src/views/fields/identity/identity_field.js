import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { CharField } from "@web/views/fields/char/char_field";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/** Presentation of already-loaded fields. Editing uses the ordinary char field. */
export class IdentityField extends Component {
    static template = "web.IdentityField";
    static components = { CharField };
    static props = {
        ...standardFieldProps,
        secondaryField: { type: String, optional: true },
    };

    get value() { return this.props.record.data[this.props.name] || ""; }
    get secondary() {
        const value = this.props.record.data[this.props.secondaryField];
        return typeof value === "string" ? value : "";
    }
    get initials() {
        const words = this.value.trim().split(/\s+/u).filter(Boolean);
        const first = Array.from(words[0] || "");
        const last = Array.from(words.at(-1) || "");
        return (words.length > 1 ? first[0] + last[0] : first.slice(0, 2).join("")).toLocaleUpperCase();
    }
    get charProps() {
        const { secondaryField, ...props } = this.props;
        return props;
    }
}

export const identityField = {
    component: IdentityField,
    displayName: _t("Identity"),
    supportedTypes: ["char"],
    supportedOptions: [
        { name: "secondary_field", label: _t("Secondary text"), type: "field", availableTypes: ["char"] },
    ],
    extractProps: ({ options }) => ({ secondaryField: options.secondary_field }),
    fieldDependencies: ({ options }) => options.secondary_field
        ? [{ name: options.secondary_field, type: "char", readonly: true }]
        : [],
};

registry.category("fields").add("mp_identity", identityField);
