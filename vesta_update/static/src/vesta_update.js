import { Component, onWillStart, proxy, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_plugin";

export class VestaUpdateControl extends Component {
    static template = "vesta_update.Control";

    props = useProps(standardActionServiceProps);

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.state = proxy({ data: null, busy: false });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.data = await this.orm.call("vesta.update", "get_update_data");
    }

    get stateLabels() {
        return {
            update_available: _t("Update available"),
            up_to_date: _t("Up to date"),
            not_published: _t("Not published"),
            restart_required: _t("Restart Odoo"),
            error: _t("Error"),
        };
    }

    stateClass(state) {
        return (
            {
                update_available: "text-bg-info",
                up_to_date: "text-bg-success",
                restart_required: "text-bg-warning",
                error: "text-bg-danger",
            }[state] || "text-bg-secondary"
        );
    }

    async run(method, args = [], message = "") {
        this.state.busy = true;
        try {
            const result = await this.orm.call("vesta.update", method, args);
            if (message) {
                this.notification.add(message, { type: "success", sticky: method !== "check_updates" });
            }
            return result;
        } finally {
            this.state.busy = false;
            await this.load();
        }
    }

    checkUpdates() {
        return this.run("check_updates");
    }

    applyUpdate(module) {
        return this.run(
            "apply_update",
            [module.name],
            _t("The files of %(module)s %(version)s are on the server. Restart Odoo, then press Upgrade.", {
                module: module.name,
                version: module.check.latest,
            })
        );
    }

    restoreBackup(module) {
        return this.run(
            "restore_backup",
            [module.name],
            _t("The previous files of %(module)s are back. Restart Odoo.", { module: module.name })
        );
    }

    async upgradeModule(module) {
        this.state.busy = true;
        const action = await this.orm.call("vesta.update", "upgrade_module", [module.name]);
        await this.action.doAction(action);
    }
}

registry.category("actions").add("vesta_update.control", VestaUpdateControl);
