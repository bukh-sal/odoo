"""Private credential-footprint guard for the future reviewed recurrence role.

Not selected by the lifecycle executor yet. Only the independent operator may
supply a reviewed policy; schedule data cannot select this maintenance profile.
"""
from datetime import datetime,timezone

from .durable import _bounded,_uuid,QueueError


MAX_CREDENTIALS=1024
ACTIONS={'read','create','write','unlink'}
FIELDS={'credential_id','principal_id','workspace_id','installation_id','actions','expires_at'}


class RecurrenceAuthorityError(ValueError):
    pass


def _canonical_expiry(value):
    if not isinstance(value,datetime) or value.tzinfo is not None:
        raise RecurrenceAuthorityError('Native credential expiry must use a UTC database timestamp')
    return value.replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')


def _bindings(cr,site_id):
    try:_uuid(site_id)
    except QueueError:raise RecurrenceAuthorityError('Exact recurrence site required') from None
    cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.site_id'")
    if cr.fetchall()!=[(site_id,)]:raise RecurrenceAuthorityError('Recurrence credential site differs')
    cr.execute("SELECT count(*) FROM mp_service_credential WHERE state='active'")
    count,=cr.fetchone()
    if not 0<=count<=MAX_CREDENTIALS:raise RecurrenceAuthorityError('Recurrence credential footprint exceeds its bound')
    # LEFT JOIN retains malformed credentials so missing metadata cannot make a
    # credential disappear from the reviewed footprint. Never read token bytes.
    cr.execute("""SELECT c.id,c.principal_id,c.workspace_id,c.installation_public_id,c.actions,c.expires_at,
        p.kind='service' AND p.user_id<>1 AND p.state='active' AND u.active
        AND w.state='active' AND m.state='active' AND i.runtime='native' AND c.audience='mp-host-v1'
        AND NOT EXISTS (SELECT 1 FROM res_groups_users_rel g JOIN ir_model_data d ON d.res_id=g.gid
            AND d.model='res.groups' AND d.module='base' AND d.name IN ('group_system','group_erp_manager')
            WHERE g.uid=p.user_id)
        AND EXISTS (SELECT 1 FROM mp_job_schedule s WHERE s.site_id=%s
            AND s.actor_id=c.principal_id AND s.workspace_id=c.workspace_id AND s.installation_id=i.id
            AND s.payload#>>'{context,credential_id}'=c.id::text
            AND s.payload#>>'{context,authenticated_installation_id}'=c.installation_public_id)
        FROM mp_service_credential c LEFT JOIN mp_principal p ON p.id=c.principal_id
        LEFT JOIN res_users u ON u.id=p.user_id LEFT JOIN mp_workspace w ON w.id=c.workspace_id
        LEFT JOIN mp_membership m ON m.principal_id=c.principal_id AND m.workspace_id=c.workspace_id
        LEFT JOIN mp_plugin_installation i ON i.public_id=c.installation_public_id
        WHERE c.state='active' ORDER BY c.id LIMIT %s""",[site_id,MAX_CREDENTIALS+1])
    rows=cr.fetchall()
    if len(rows)!=count:raise RecurrenceAuthorityError('Credential footprint is incomplete or duplicated')
    bindings=[]
    for credential,principal,workspace,installation,actions,expiry,eligible in rows:
        if eligible is not True or not isinstance(actions,str):
            raise RecurrenceAuthorityError('Only scoped non-administrator native schedule credentials are supported')
        granted=actions.split(',')
        if not granted or len(set(granted))!=len(granted) or not set(granted)<=ACTIONS:
            raise RecurrenceAuthorityError('Explicit bounded native credential actions required')
        try:
            for ident in (credential,principal,workspace):_bounded(ident,1,2**31-1)
            _uuid(installation)
        except QueueError:raise RecurrenceAuthorityError('Invalid recurrence credential identity') from None
        bindings.append(dict(credential_id=credential,principal_id=principal,workspace_id=workspace,
            installation_id=installation,actions=sorted(granted),expires_at=_canonical_expiry(expiry)))
    return bindings


def review(cr,site_id):
    """Read safe bindings for a protected OS-owned role review, not app input."""
    return dict(protocol=1,kind='native-recurring-credentials-v1',site_id=site_id,credentials=_bindings(cr,site_id))


def validate(cr,site_id,policy):
    if (not isinstance(policy,dict) or set(policy)!={'protocol','kind','site_id','credentials'}
            or type(policy['protocol']) is not int or policy['protocol']!=1
            or policy['kind']!='native-recurring-credentials-v1' or policy['site_id']!=site_id
            or not isinstance(policy['credentials'],list) or len(policy['credentials'])>MAX_CREDENTIALS):
        raise RecurrenceAuthorityError('Exact independently reviewed recurrence credential policy required')
    expected={}
    for binding in policy['credentials']:
        if not isinstance(binding,dict) or set(binding)!=FIELDS:
            raise RecurrenceAuthorityError('Exact reviewed credential binding required')
        try:
            for key in ('credential_id','principal_id','workspace_id'):_bounded(binding[key],1,2**31-1)
            _uuid(binding['installation_id'])
        except QueueError:raise RecurrenceAuthorityError('Invalid reviewed credential identity') from None
        actions=binding['actions']
        if (not isinstance(actions,list) or not actions or any(not isinstance(item,str) for item in actions)
                or actions!=sorted(set(actions)) or not set(actions)<=ACTIONS):
            raise RecurrenceAuthorityError('Exact reviewed action scope required')
        try:
            expiry=datetime.fromisoformat(binding['expires_at'])
            canonical=expiry.astimezone(timezone.utc).isoformat().replace('+00:00','Z') if expiry.tzinfo else None
        except (ValueError,TypeError):canonical=None
        if canonical!=binding['expires_at'] or binding['credential_id'] in expected:
            raise RecurrenceAuthorityError('Canonical unique credential binding required')
        expected[binding['credential_id']]=binding
    if list(expected)!=sorted(expected):raise RecurrenceAuthorityError('Canonical ordered credential policy required')
    current=_bindings(cr,site_id)
    if any(expected.get(binding['credential_id'])!=binding for binding in current):
        raise RecurrenceAuthorityError('Active credential authority changed after the independent review')
    # A reviewed credential may have been revoked. Its absence never restores it.
    return dict(active_credentials=len(current),reviewed_credentials=len(expected))
