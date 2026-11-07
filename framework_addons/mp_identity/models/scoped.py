from contextlib import contextmanager

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.fields import Domain
from odoo.tools import SQL

from ..scopes import current_scope
from ..read_window import KEY, ReadWindow, active_window


class WorkspaceScoped(models.AbstractModel):
    _name = "mp.workspace.scoped"
    _description = "Workspace-owned native model enforcement"
    _mp_scoped = True
    _mp_plugin_id = None

    workspace_id = fields.Many2one("mp.workspace", required=True, index=True, ondelete="restrict")

    def _mp_guard(self, operation):
        scope = current_scope(self.env)
        if operation != "read" and scope.role not in {"editor", "administrator"}:
            raise AccessError("Operation not permitted in current workspace")
        if scope.allowed_actions is not None and operation not in scope.allowed_actions:
            raise AccessError("Technical action scope denied")
        # Constrained policy read after actor/membership authorization; does not
        # elevate the backing user or expose any business rows.
        self.env.cr.execute("SELECT availability FROM mp_workspace_plugin WHERE workspace_id=%s AND plugin_id=%s", [scope.workspace_id, self._mp_plugin_id])
        available = self.env.cr.fetchone()
        if not available or available[0] != "enabled":
            raise AccessError("Plugin feature unavailable")
        # Native onchange/new wrappers retain their persisted origin's scope.
        ids = [ident for ident in self._origin.ids if isinstance(ident, int)]
        if ids:
            # Ownership preflight avoids ORM-cache recursion and rejects a mixed
            # batch identically for nonexistent or foreign-workspace objects.
            self.env.cr.execute(SQL("SELECT id FROM %s WHERE id = ANY(%s) AND workspace_id = %s", SQL.identifier(self._table), ids, scope.workspace_id))
            if {row[0] for row in self.env.cr.fetchall()} != set(ids):
                raise AccessError("Resource unavailable in current workspace")
        return scope

    def _mp_validate_relations(self, values):
        for name, value in values.items():
            field = self._fields.get(name)
            if not field or field.type not in {"many2one", "many2many", "one2many"}:
                continue
            target = self.env[field.comodel_name]
            if not getattr(target, "_mp_scoped", False):
                continue
            if field.type == "many2one":
                ids = [value] if value else []
            else:
                ids = []
                for command in value or []:
                    if command[0] in [1, 2, 3, 4]:
                        ids.append(command[1])
                    elif command[0] == 6:
                        ids.extend(command[2])
            if ids:
                target.browse(ids)._mp_guard("read")

    def _check_access(self, operation):
        self._mp_guard(operation)
        return super()._check_access(operation)

    def has_access(self, operation):
        try:
            self._mp_guard(operation)
        except AccessError:
            return False
        return super().has_access(operation)

    @api.private
    def check_access(self, operation):
        self._mp_guard(operation)
        return super().check_access(operation)

    def read(self, fields=None, load="_classic_read"):
        with self._mp_read_window() as records:
            return super(WorkspaceScoped, records).read(fields, load=load)

    @api.private
    @contextmanager
    def _mp_read_window(self):
        if active_window(self):
            yield self
            return
        window = ReadWindow(self)
        try:
            window.start()
            records = self.with_context(**{KEY: window})
            window.bound_env = records.env
            yield records
        finally:
            window.close()

    @api.private
    def _mp_cached_read_scope(self):
        window = active_window(self)
        return window.scope if window else None

    @api.private
    def _mp_read_scope(self):
        return self._mp_cached_read_scope() or self._mp_guard("read")

    @api.private
    def _mp_read_policy(self, key, check):
        window = active_window(self)
        if window and key in window.policies:
            return window.policies[key]
        value = check()
        if type(value) is not bool:
            raise TypeError("A read policy check must return bool")
        if window and not window.invalid:
            window.policies[key] = value
        return value

    @api.model
    def _has_field_access(self, field, operation):
        # The native descriptor calls this before transaction field-cache
        # lookup. Model-only introspection and trusted sudo stay native.
        if operation == "read" and self._ids and not self.env.su:
            try:
                self._mp_read_scope()
            except AccessError:
                return False
        return super()._has_field_access(field, operation)

    @api.readonly
    def web_read(self, specification):
        # Native id-only/empty specifications deliberately skip read(). Scope
        # authorization still applies to this supported record entry point.
        self._mp_guard("read")
        return super().web_read(specification)

    @api.private
    def fetch(self, field_names=None):
        self._mp_guard("read")
        return super().fetch(field_names)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, *, active_test=True, bypass_access=False):
        scope = self._mp_guard("read")
        return super()._search(Domain(domain) & Domain("workspace_id", "=", scope.workspace_id), offset=offset, limit=limit, order=order, active_test=active_test, bypass_access=bypass_access)

    @api.model_create_multi
    def create(self, values_list):
        scope = self._mp_guard("create")
        clean = []
        for values in values_list:
            values = dict(values)
            if values.get("workspace_id", scope.workspace_id) != scope.workspace_id:
                raise AccessError("Workspace ownership cannot be reassigned")
            values["workspace_id"] = scope.workspace_id
            self._mp_validate_relations(values)
            clean.append(values)
        return super().create(clean)

    def write(self, values):
        scope = self._mp_guard("write")
        if "workspace_id" in values and values["workspace_id"] != scope.workspace_id:
            raise AccessError("Workspace ownership cannot be reassigned")
        if "public_id" in values:
            raise AccessError("Public identifiers are immutable")
        self._mp_validate_relations(values)
        return super().write(values)

    def unlink(self):
        self._mp_guard("unlink")
        return super().unlink()
