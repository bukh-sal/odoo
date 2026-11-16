import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { isMacOS } from "@web/core/browser/feature_detection";
import { Dialog } from "@web/core/dialog/dialog";

export class WorkspaceHelp extends Component {
    static template = "web.interface.WorkspaceHelp";
    static components = { Dialog };
    static props = { close: Function, onCommands: Function, onCustomize: {type:Function,optional:true} };
    get title() { return _t("Help and shortcuts"); }
    get commandKey() { return isMacOS() ? "\u2318 K" : "Ctrl K"; }
    commands() { this.props.close(); this.props.onCommands(); }
    customize() { this.props.close(); this.props.onCustomize?.(); }
}
