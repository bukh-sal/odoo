from odoo import models
from odoo.exceptions import AccessError
from odoo.http import request

from ..scopes import resolve_scope


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _pre_dispatch(cls, rule, args):
        super()._pre_dispatch(rule, args)
        # Authentication has already established env.uid; workspace is per request,
        # never a mutable session value. Global bootstrap/session routes need none.
        selected = request.httprequest.headers.get("X-MP-Workspace")
        if selected and request.env.uid:
            try:
                request._mp_authoritative_scope = resolve_scope(request.env, selected)
            except AccessError:
                # Native dataset dispatch already has a typed JSON-RPC error
                # envelope. HTTP/JSON gateways normalize this at their boundary
                # instead of inheriting an HTML error page from middleware.
                request._mp_scope_failure = True
                if request.httprequest.path.startswith("/web/dataset/"):
                    raise
        if request.httprequest.path.startswith("/web/dataset/"):
            payload = request.get_json_data().get("params", {})
            context = payload.get("kwargs", {}).get("context", {}) or {}
            if not isinstance(context, dict) or any(key.startswith(("mp_", "_mp_")) for key in context):
                raise AccessError("Client cannot supply platform authority context")
