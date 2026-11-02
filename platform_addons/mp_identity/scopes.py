"""Native authorization adapter; these are private G1 proof contracts."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from odoo.exceptions import AccessError
from odoo.http import request


@dataclass(frozen=True)
class Scope:
    database: str
    user_id: int
    principal_id: int
    principal_public_id: str
    principal_kind: str
    workspace_id: int
    workspace_public_id: str
    role: str
    policy_generation: int
    credential_id: int | None = None
    authenticated_installation_id: str | None = None
    allowed_actions: frozenset[str] | None = None


def canonical_uuid(value):
    try:
        normalized = str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise AccessError("Invalid workspace selection") from None
    if normalized != value:
        raise AccessError("Invalid workspace selection")
    return normalized


def _flush_identity_policy(env):
    """Publish pending authorized ORM metadata before constrained SQL reads.

    Native callers can change policy and use a supported service in one
    transaction. A later savepoint may flush too late for its authorization.
    These are policy fields only; business records stay under their ORM gates.
    """
    for model, names in (
        ("res.users", ["active"]),
        ("mp.principal", ["user_id", "public_id", "kind", "state"]),
        ("mp.membership", ["principal_id", "workspace_id", "role", "state"]),
        ("mp.workspace", ["public_id", "state", "policy_generation"]),
        ("mp.workspace.plugin", ["workspace_id", "plugin_id", "availability"]),
        ("mp.service.credential", ["principal_id", "workspace_id", "installation_public_id", "audience", "actions", "expires_at", "state"]),
    ):
        env[model].flush_model(names)


def resolve_scope(env, workspace_public_id, previous=None):
    """Read only current actor/workspace authority, never arbitrary resources.

    Deliberate metadata ACL bypass: after established HTTP authentication or a
    typed trusted native scope, constrain the lookup to env.uid + one workspace.
    No sudo user/environment fallback is created. Business data stays in ORM.
    """
    canonical_uuid(workspace_public_id)
    if not env.uid:
        raise AccessError("Authentication required")
    if previous is not None and (not isinstance(previous, Scope) or previous.database != env.cr.dbname or previous.user_id != env.uid):
        raise AccessError("Actor or site context mismatch")
    _flush_identity_policy(env)
    env.cr.execute("""
        SELECT p.id, p.public_id, p.kind, w.id, w.public_id,
               m.role, w.policy_generation
          FROM mp_principal p
          JOIN res_users u ON u.id = p.user_id
          JOIN mp_membership m ON m.principal_id = p.id
          JOIN mp_workspace w ON w.id = m.workspace_id
         WHERE p.user_id = %s AND w.public_id = %s
           AND u.active AND p.state = 'active' AND w.state = 'active'
           AND m.state = 'active'
    """, [env.uid, workspace_public_id])
    row = env.cr.fetchone()
    if not row:
        raise AccessError("Workspace unavailable")
    credential_id = previous.credential_id if previous else None
    installation = None
    actions = previous.allowed_actions if previous else None
    if row[2] == "service":
        if not credential_id:
            actions = frozenset()
        else:
            env.cr.execute("""
                SELECT installation_public_id, actions
                  FROM mp_service_credential
                 WHERE id = %s AND principal_id = %s AND workspace_id = %s
                   AND state = 'active' AND audience = 'mp-host-v1'
                   AND expires_at > timezone('UTC', now())
            """, [credential_id, row[0], row[3]])
            credential = env.cr.fetchone()
            if not credential:
                raise AccessError("Technical credential unavailable")
            installation, granted = credential
            granted = frozenset(filter(None, granted.split(",")))
            actions = granted if actions is None else granted & actions
    return Scope(env.cr.dbname, env.uid, *row[:3], *row[3:], credential_id, installation, actions)


def scope_carrier(env, required=True):
    """Private typed carrier lookup only; it is not an authorization decision."""
    scope = None
    if request and request.db == env.cr.dbname:
        if getattr(request, "_mp_scope_failure", False):
            if required:
                raise AccessError("Workspace unavailable")
            return None
        scope = getattr(request, "_mp_authoritative_scope", None)
    if scope is None:
        scope = env.context.get("_mp_scope")
    if scope is None:
        if required:
            raise AccessError("Explicit workspace context required")
        return None
    if not isinstance(scope, Scope):
        raise AccessError("Untrusted workspace context")
    from .release import require_client_release
    require_client_release(env)
    return scope


def current_scope(env, required=True):
    """Native call_kw replaces context; request-bound authority survives it."""
    scope = scope_carrier(env, required=required)
    return resolve_scope(env, scope.workspace_public_id, previous=scope) if scope else None


def scoped_environment(env, workspace_public_id):
    """Trusted native entry point; not an RPC method or a permission grant."""
    scope = resolve_scope(env, workspace_public_id)
    return env(context={**env.context, "_mp_scope": scope})
