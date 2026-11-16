"""Private native record authority. Applications own capability names and roles.

Call register() before creating a resource with the same UUID, in the same
transaction. Inherit mp.resource.scoped for query/direct/cache guards. Trusted
native code remains trusted; this module does not sandbox SQL or sudo.
"""
import json
from uuid import uuid4

from odoo import api, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain
from odoo.tools import SQL
from odoo.addons.mp_identity.scopes import canonical_uuid


def _binding(records, action, capability=None):
    scope = records._mp_resource_base_guard(action)
    if action != 'read':
        # Membership/feature changes update this row. Repeatable-read requests
        # whose policy changed before locking retry instead of writing stale.
        records.env.cr.execute('SELECT id FROM mp_workspace WHERE id=%s FOR SHARE', [scope.workspace_id])
        scope = records._mp_resource_base_guard(action)
    actions = getattr(records, '_mp_resource_actions', None)
    if (not getattr(records, '_mp_scoped', False) or not isinstance(actions, dict)
            or set(actions) != {'read', 'create', 'write', 'unlink', 'manage'}
            or not all(isinstance(v, str) for v in actions.values())
            or 'public_id' not in records._fields):
        raise AccessError('Declared resource model and capabilities required')
    records.env['mp.plugin.installation'].flush_model(['state', 'manifest'])
    records.env.cr.execute("""SELECT i.id,i.manifest FROM mp_plugin_installation i
        JOIN mp_workspace_plugin f ON f.installation_id=i.id
        WHERE i.plugin_id=%s AND i.state='installed' AND i.runtime='native'
        AND f.workspace_id=%s AND f.plugin_id=i.plugin_id AND f.availability='enabled'""",
        [records._mp_plugin_id, scope.workspace_id])
    row = records.env.cr.fetchone()
    if not row:
        raise AccessError('Resource installation unavailable')
    installation, manifest = row
    defines = manifest.get('permissions', {}).get('defines', {})
    if (records._name not in manifest.get('data', {}).get('models', [])
            or not isinstance(defines, dict) or not set(actions.values()) <= defines.keys()):
        raise AccessError('Resource model/capability not declared by its installation')
    capability = actions[action] if capability is None else capability
    from .controllers import advertised_capabilities
    if (not isinstance(capability, str) or capability not in defines or records._mp_plugin_id + ':' + capability
            not in advertised_capabilities(records._mp_plugin_id, manifest, scope)):
        raise AccessError('Application capability ceiling denied')
    return scope, installation, capability, defines


def _caps(values, defines):
    if (not isinstance(values, (list, tuple)) or not all(isinstance(v, str) for v in values)
            or len(set(values)) != len(values) or not set(values) <= defines.keys()):
        raise ValidationError('Only declared distinct resource capabilities are supported')
    return sorted(values)


def _predicate(records, scope, installation, capability, alias, *, management=False):
    # All identifiers originate in a trusted registered native model. All
    # policy values are parameters. No browser SQL/domain fragment is used.
    return SQL("""EXISTS (SELECT 1 FROM mp_resource_policy rp
        WHERE rp.installation_id=%s AND rp.workspace_id=%s AND rp.model_name=%s
        AND rp.resource_id=%s AND ((rp.state='active' AND (
          rp.owner_id=%s OR %s OR rp.member_capabilities ? %s OR EXISTS (
            SELECT 1 FROM mp_resource_grant rg WHERE rg.policy_id=rp.id
            AND rg.principal_id=%s AND rg.capability=%s AND rg.state='approved')))
          OR (%s AND rp.state='revoked' AND (rp.owner_id=%s OR %s))))""",
        installation, scope.workspace_id, records._name, SQL.identifier(alias, 'public_id'),
        scope.principal_id, scope.role == 'administrator' and scope.principal_kind == 'human',
        capability, scope.principal_id, capability, management, scope.principal_id,
        scope.role == 'administrator' and scope.principal_kind == 'human')


def _require(records, scope, installation, capability, *, lock, management=False):
    ids = sorted({ident for ident in records._origin.ids if isinstance(ident, int)})
    if not ids:
        return
    if lock:
        records.env.cr.execute(SQL("""SELECT rp.id FROM mp_resource_policy rp JOIN %s resource
            ON resource.public_id=rp.resource_id AND resource.workspace_id=rp.workspace_id
            WHERE resource.id=ANY(%s) AND rp.workspace_id=%s AND rp.installation_id=%s
            AND rp.model_name=%s ORDER BY rp.id FOR UPDATE OF rp""",
            SQL.identifier(records._table), ids, scope.workspace_id, installation, records._name))
        if len(records.env.cr.fetchall()) != len(ids):
            raise AccessError('Resource unavailable')
    records.env.cr.execute(SQL('SELECT resource.id FROM %s resource WHERE resource.id=ANY(%s) AND %s',
        SQL.identifier(records._table), ids, _predicate(records, scope, installation, capability, 'resource', management=management)))
    if {row[0] for row in records.env.cr.fetchall()} != set(ids):
        raise AccessError('Resource unavailable')


def require(records, capability, *, action='read'):
    """Fresh check for an additional app-owned capability; writes retain lock."""
    if action not in {'read', 'write', 'unlink'}:
        raise ValueError('Read or mutation action required')
    if not isinstance(capability, str):
        raise AccessError('Named application capability required')
    scope, installation, capability, _ = _binding(records, action, capability)
    _require(records, scope, installation, capability, lock=action != 'read')
    return scope


def register(model, resource_id, *, member_capabilities=()):
    """Register before app ORM creation. Owner and workspace come from scope."""
    if model._ids:
        raise ValueError('Register with the owning model before creating a record')
    canonical_uuid(resource_id)
    scope, installation, _, defines = _binding(model, 'create')
    capabilities = _caps(member_capabilities, defines)
    public_id = str(uuid4())
    model.env.cr.execute("""INSERT INTO mp_resource_policy
        (public_id,installation_id,workspace_id,model_name,resource_id,owner_id,state,revision,
         member_capabilities,create_uid,write_uid,create_date,write_date)
        VALUES (%s,%s,%s,%s,%s,%s,'active',1,%s::jsonb,%s,%s,timezone('UTC',now()),timezone('UTC',now()))""",
        [public_id, installation, scope.workspace_id, model._name, resource_id, scope.principal_id,
         json.dumps(capabilities), model.env.uid, model.env.uid])
    return public_id


def policy(records):
    """Current sharing metadata is management-only, never a broad member list."""
    records.ensure_one()
    scope, installation, _, _ = _binding(records, 'read', records._mp_resource_actions['manage'])
    _require(records, scope, installation, records._mp_resource_actions['manage'], lock=False, management=True)
    return _policy(records, scope, installation)


def _policy(records, scope, installation):
    records.env.cr.execute(SQL("""SELECT rp.public_id,rp.revision,rp.state,rp.member_capabilities,
        owner.public_id FROM mp_resource_policy rp JOIN %s resource ON resource.public_id=rp.resource_id
        JOIN mp_principal owner ON owner.id=rp.owner_id WHERE resource.id=%s
        AND rp.workspace_id=%s AND rp.installation_id=%s AND rp.model_name=%s""",
        SQL.identifier(records._table), records.id, scope.workspace_id, installation, records._name))
    row = records.env.cr.fetchone()
    if not row:
        raise AccessError('Resource unavailable')
    public_id, revision, state, capabilities, owner = row
    records.env.cr.execute("""SELECT p.public_id,g.capability,g.state FROM mp_resource_grant g
        JOIN mp_principal p ON p.id=g.principal_id JOIN mp_resource_policy r ON r.id=g.policy_id
        WHERE r.public_id=%s ORDER BY p.public_id,g.capability""", [public_id])
    return dict(policy_id=public_id, revision=revision, state=state, owner_id=owner,
                member_capabilities=capabilities,
                grants=[dict(principal_id=p, capability=c, state=s) for p, c, s in records.env.cr.fetchall()])


def change_policy(records, *, expected_revision, member_capabilities, grants, state='active'):
    """Replace effective grants using CAS; retain revoked rows as tombstones.

    Grants are full requested active assignments, not a native RPC relation
    command. Revoking an already inactive subject is always possible by omission.
    A newly positive grant requires a current active workspace principal. A
    service principal still needs its independently valid scoped credential at
    use time; sharing metadata never creates or widens that credential.
    """
    records.ensure_one()
    if type(expected_revision) is not int or not 0 < expected_revision < 2**31-1:
        raise ValidationError('Exact positive policy revision required')
    if state not in {'active', 'revoked'} or not isinstance(grants, list):
        raise ValidationError('Invalid resource policy')
    scope, installation, capability, defines = _binding(records, 'write', records._mp_resource_actions['manage'])
    _require(records, scope, installation, capability, lock=True, management=True)
    capabilities = _caps(member_capabilities, defines)
    assignments = []; seen = set()
    for grant in grants:
        if not isinstance(grant, dict) or set(grant) != {'principal_id', 'capabilities'}:
            raise ValidationError('Exact resource subject/capabilities required')
        canonical_uuid(grant['principal_id'])
        if grant['principal_id'] in seen:
            raise ValidationError('Duplicate resource subject')
        seen.add(grant['principal_id'])
        caps = _caps(grant['capabilities'], defines)
        records.env.cr.execute("""SELECT p.id FROM mp_principal p JOIN res_users u ON u.id=p.user_id
            JOIN mp_membership m ON m.principal_id=p.id WHERE p.public_id=%s
            AND p.state='active' AND u.active AND m.workspace_id=%s AND m.state='active'""",
            [grant['principal_id'], scope.workspace_id])
        subject = records.env.cr.fetchone()
        if not subject:
            raise AccessError('Resource subject unavailable in current workspace')
        assignments.extend((subject[0], cap) for cap in caps)
    records.env.cr.execute(SQL("""UPDATE mp_resource_policy rp SET revision=revision+1,state=%s,
        member_capabilities=%s::jsonb,write_uid=%s,write_date=timezone('UTC',now())
        FROM %s resource WHERE rp.resource_id=resource.public_id AND resource.id=%s
        AND rp.workspace_id=%s AND rp.installation_id=%s AND rp.model_name=%s
        AND rp.revision=%s RETURNING rp.id""", state, json.dumps(capabilities), records.env.uid,
        SQL.identifier(records._table), records.id, scope.workspace_id, installation, records._name, expected_revision))
    row = records.env.cr.fetchone()
    if not row:
        from .controllers import PublicError
        raise PublicError('CONFLICT')
    policy_id = row[0]
    records.env.cr.execute("UPDATE mp_resource_grant SET state='revoked' WHERE policy_id=%s", [policy_id])
    for subject, cap in assignments:
        records.env.cr.execute("""INSERT INTO mp_resource_grant
            (policy_id,principal_id,capability,state,create_uid,write_uid,create_date,write_date)
            VALUES (%s,%s,%s,'approved',%s,%s,timezone('UTC',now()),timezone('UTC',now()))
            ON CONFLICT(policy_id,principal_id,capability) DO UPDATE
            SET state='approved',write_uid=EXCLUDED.write_uid,write_date=EXCLUDED.write_date""",
            [policy_id, subject, cap, records.env.uid, records.env.uid])
    return _policy(records, scope, installation)


class ResourceScoped(models.AbstractModel):
    _name = 'mp.resource.scoped'
    _inherit = 'mp.workspace.scoped'
    _description = 'Opt-in native resource capability enforcement'
    _mp_resource_actions = None

    @api.private
    def _mp_resource_base_guard(self, operation):
        return super()._mp_guard(operation)

    def _mp_guard(self, operation):
        scope, installation, capability, _ = _binding(self, operation)
        if operation != 'create':
            _require(self, scope, installation, capability, lock=operation != 'read')
        return scope

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, *, active_test=True, bypass_access=False):
        scope, installation, capability, _ = _binding(self, 'read')
        owned = Domain.custom(to_sql=lambda model, alias, query:
            _predicate(model, scope, installation, capability, alias))
        return super()._search(Domain(domain) & owned, offset=offset, limit=limit, order=order,
            active_test=active_test, bypass_access=bypass_access)

    @api.model_create_multi
    def create(self, values_list):
        scope, installation, _, _ = _binding(self, 'create')
        for values in values_list:
            # Only a private in-transaction registration can supply this row.
            canonical_uuid(values.get('public_id'))
            self.env.cr.execute("""SELECT id FROM mp_resource_policy WHERE installation_id=%s
                AND workspace_id=%s AND model_name=%s AND resource_id=%s
                AND owner_id=%s AND state='active' FOR UPDATE""",
                [installation, scope.workspace_id, self._name, values['public_id'], scope.principal_id])
            if not self.env.cr.fetchone():
                raise AccessError('Private resource registration required before creation')
        return super().create(values_list)

    def unlink(self):
        scope, installation, capability, _ = _binding(self, 'unlink')
        _require(self, scope, installation, capability, lock=True)
        self.env.cr.execute(SQL('SELECT public_id FROM %s WHERE id=ANY(%s)', SQL.identifier(self._table), self.ids))
        resources = [row[0] for row in self.env.cr.fetchall()]
        result = super().unlink()
        self.env.cr.execute("""UPDATE mp_resource_policy SET state='revoked',revision=revision+1,
            member_capabilities='[]'::jsonb WHERE installation_id=%s AND workspace_id=%s
            AND model_name=%s AND resource_id=ANY(%s)""", [installation, scope.workspace_id, self._name, resources])
        return result
