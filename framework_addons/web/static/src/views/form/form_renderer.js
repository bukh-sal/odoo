import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { Notebook } from "@web/core/notebook/notebook";
import { Setting } from "./setting/setting";
import { Field } from "@web/views/fields/field";
import { browser } from "@web/core/browser/browser";
import { hasTouch } from "@web/core/browser/feature_detection";
import { useService } from "@web/core/utils/hooks";
import { useDebounced, useThrottleForAnimation } from "@web/core/utils/timing";
import { ButtonBox } from "@web/views/form/button_box/button_box";
import { InnerGroup, OuterGroup } from "@web/views/form/form_group/form_group";
import { ViewButton } from "@web/views/view_button/view_button";
import { useViewCompiler } from "@web/views/view_compiler";
import { Widget } from "@web/views/widgets/widget";
import { FormCompiler } from "./form_compiler";
import { FormLabel } from "./form_label";
import { uniqueId } from "@web/core/utils/strings";
import { StatusBarButtons } from "./status_bar_buttons/status_bar_buttons";

import {
    Component,
    onMounted,
    onWillUnmount,
    useEffect,
    useSubEnv,
    useRef,
    useState,
    xml,
} from "@odoo/owl";

export class FormRenderer extends Component {
    static template = xml`<t t-call="{{ templates.FormRenderer }}" t-call-context="{ __comp__: Object.assign(Object.create(this), { this: this }) }" />`;
    static components = {
        Field,
        FormLabel,
        ButtonBox,
        ViewButton,
        Widget,
        Notebook,
        Setting,
        OuterGroup,
        InnerGroup,
        StatusBarButtons,
    };
    static props = {
        archInfo: Object,
        Compiler: { type: Function, optional: true },
        record: Object,
        // Template props : added by the FormCompiler
        class: { type: String, optional: 1 },
        translateAlert: { type: [Object, { value: null }], optional: true },
        onNotebookPageChange: { type: Function, optional: true },
        activeNotebookPages: { type: Object, optional: true },
        readonly: { type: Boolean, optional: true },
        saveRecord: { type: Function, optional: true },
        setFieldAsDirty: { type: Function, optional: true },
        slots: { type: Object, optional: true },
    };
    static defaultProps = {
        activeNotebookPages: {},
        onNotebookPageChange: () => {},
    };

    setup() {
        this.fieldIdPrefix = uniqueId("form_field_");
        this.evaluateBooleanExpr = evaluateBooleanExpr;
        const { archInfo, Compiler, record } = this.props;
        const templates = { FormRenderer: archInfo.xmlDoc };
        this.state = useState({}); // Used by Form Compiler
        this.templates = useViewCompiler(Compiler || FormCompiler, templates);
        useSubEnv({ model: record.model });
        this.uiService = useService("ui");
        this.onResize = useDebounced(this.render, 200);
        this.onScrollThrottled = useThrottleForAnimation(this.onScroll);
        onMounted(() => browser.addEventListener("resize", this.onResize));
        onWillUnmount(() => browser.removeEventListener("resize", this.onResize));

        const { autofocusFieldIds } = archInfo;
        const rootRef = useRef("compiled_view_root");
        if (this.shouldAutoFocus) {
            useEffect(
                (isNew, rootEl) => {
                    if (!rootEl) {
                        return;
                    }
                    let elementToFocus;
                    if (isNew) {
                        const focusableSelectors = [
                            'input[type="text"]',
                            "textarea",
                            "[contenteditable]",
                        ];
                        for (const id of autofocusFieldIds) {
                            elementToFocus = rootEl.querySelector(`#${this.fieldId(id)}`);
                            if (elementToFocus) {
                                break;
                            }
                        }
                        elementToFocus =
                            elementToFocus ||
                            rootEl.querySelector(
                                focusableSelectors
                                    .map((sel) => `.o_content .o_field_widget ${sel}`)
                                    .join(", ")
                            );
                    }
                    if (elementToFocus) {
                        elementToFocus.focus();
                    }
                },
                () => [this.props.record.isNew, rootRef.el]
            );
        }

    }

    // DOM identity belongs to this form, not to its reusable architecture.
    // Never remove IDs from a background form when a nested dialog mounts.
    fieldId(archFieldId) {
        return `${this.fieldIdPrefix}-${archFieldId}`;
    }

    get shouldAutoFocus() {
        return !hasTouch() && !this.props.archInfo.disableAutofocus;
    }

    onScroll(ev) {
        this.state.isStatusbarStickyPinned =
            !this.env.inDialog && !this.env.isSmall && ev.target.scrollTop !== 0;
    }

    async onWillChangeNotebookPage() {
        // Hack to force _askChanges
        await this.props.record.isDirty();
        return true;
    }
}
