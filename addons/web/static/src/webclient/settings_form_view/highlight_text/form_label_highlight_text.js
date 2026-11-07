import { FormLabel } from "@web/views/form/form_label";
import { HighlightText } from "./highlight_text";

export class FormLabelHighlightText extends FormLabel {
    static template = "web.FormLabelHighlightText";
    static components = { HighlightText };
}
