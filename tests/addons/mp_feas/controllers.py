"""Minimal G1 proof transport, not the frozen/public R1 service registry."""
import hashlib
import json
import secrets
from dataclasses import replace

from odoo import http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request

from odoo.addons.mp_identity.scopes import current_scope, resolve_scope


def _body():
    if request.httprequest.mimetype != "application/json" or len(request.httprequest.get_data()) > 65536:
        raise ValidationError("Expected bounded JSON input")
    value = json.loads(request.httprequest.get_data())
    if not isinstance(value, dict):
        raise ValidationError("Expected an object")
    return value


def _dispatch(body):
    # Only registered fixture operations, never arbitrary model/method dispatch.
    model = request.env["mp.feas.record"]
    operation = body.get("operation")
    scope = current_scope(request.env)
    if operation == "context":
        return {"principal_id": scope.principal_public_id, "workspace_id": scope.workspace_public_id, "role": scope.role, "policy_generation": scope.policy_generation}
    if operation == "list":
        return model.search_read([], ["public_id", "name", "amount"], limit=100)
    if operation == "create":
        values = body.get("input", {})
        if not isinstance(values, dict) or set(values) - {"name", "amount", "peer_id", "peer_ids"}:
            raise ValidationError("Unknown input fields")
        record = model.create(values)
        return {"public_id": record.public_id, "name": record.name}
    if operation in {"update", "delete"}:
        record = model.search([("public_id", "=", body.get("object_id"))], limit=1)
        if not record:
            raise MissingError("Resource unavailable")
        if operation == "delete":
            record.unlink()
            return {"deleted": True}
        values = body.get("input", {})
        if not isinstance(values, dict) or set(values) - {"name", "amount", "peer_id", "peer_ids"}:
            raise ValidationError("Unknown input fields")
        record.write(values)
        return {"public_id": record.public_id, "name": record.name}
    if operation == "provider_chain_write":
        # Provider B receives the same actor/scope as A. No provider-owned admin
        # environment is substituted. Forged browser attribution is not authority.
        return _dispatch({"operation": "update", "object_id": body.get("object_id"), "input": body.get("input", {})})
    raise ValidationError("Unknown fixture operation")


def _respond(handler):
    try:
        data = handler()
        return request.make_json_response({"data": data})
    except (AccessError, MissingError, ValidationError, ValueError, TypeError) as error:
        # Roll back any partial ORM work; safe fixed taxonomy, no SQL/stack data.
        request.env.cr.rollback()
        code = "FORBIDDEN" if isinstance(error, AccessError) else "NOT_FOUND" if isinstance(error, MissingError) else "VALIDATION_FAILED"
        status = 403 if code == "FORBIDDEN" else 404 if code == "NOT_FOUND" else 400
        return request.make_json_response({"error": {"code": code, "message": "Operation denied or invalid", "request_id": secrets.token_hex(8)}}, status=status)


class FeasibilityGateway(http.Controller):
    @http.route('/app/org.example.feasibility/<path:page>', type='http', auth='user', methods=['GET'])
    def host(self, page, **kwargs):
        # Bootstrap is workspace-free. The host validates the explicit URL scope
        # through /context before mounting any business page.
        context = request.env['ir.http'].webclient_rendering_context()
        response = request.render('mp_feas.host_bootstrap', context)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Frame-Options'] = 'DENY'
        return response

    @http.route('/mp/feas/workspaces', type='http', auth='user', methods=['GET'])
    def workspaces(self):
        # Existing global membership rules constrain this list to this actor.
        return request.make_json_response({'data': request.env['mp.workspace'].search_read([], ['name', 'public_id'])})

    @http.route("/mp/feas/gateway", type="http", auth="user", methods=["POST"], csrf=False)
    def gateway(self):
        def run():
            # Native JSON-RPC's protection does not cover this HTTP/JSON route.
            # Explicitly validate the existing session CSRF token in a header.
            if not request.validate_csrf(request.httprequest.headers.get("X-CSRFToken")):
                raise AccessError("CSRF validation failed")
            return _dispatch(_body())
        return _respond(run)

    @http.route("/mp/feas/context", type="http", auth="user", methods=["GET"])
    def context(self):
        def run():
            data = _dispatch({"operation": "context"})
            data["csrf_token"] = request.csrf_token()
            return data
        return _respond(run)

    @http.route("/mp/feas/technical", type="http", auth="none", methods=["POST"], csrf=False, save_session=False)
    def technical(self):
        def run():
            authorization = request.httprequest.headers.get("Authorization", "")
            if not authorization.startswith("Bearer "):
                raise AccessError("Technical authentication required")
            digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
            # Constrained credential lookup authenticates one technical actor;
            # no administrator environment is used as a fallback.
            request.env.cr.execute("""
                SELECT c.id, p.user_id, w.public_id
                  FROM mp_service_credential c
                  JOIN mp_principal p ON p.id=c.principal_id
                  JOIN mp_workspace w ON w.id=c.workspace_id
                 WHERE c.token_digest=%s AND c.state='active'
                   AND c.audience='mp-host-v1' AND p.kind='service'
                   AND c.expires_at > timezone('UTC', now())
            """, [digest])
            row = request.env.cr.fetchone()
            if not row:
                raise AccessError("Technical authentication failed")
            credential_id, user_id, workspace = row
            requested = request.httprequest.headers.get("X-MP-Workspace")
            if requested != workspace:
                raise AccessError("Credential workspace mismatch")
            request.update_env(user=user_id, context={}, su=False)
            initial = resolve_scope(request.env, workspace)
            request._mp_authoritative_scope = resolve_scope(request.env, workspace, previous=replace(initial, credential_id=credential_id, allowed_actions=None))
            return _dispatch(_body())
        return _respond(run)
