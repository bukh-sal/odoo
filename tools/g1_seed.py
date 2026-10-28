"""Run only inside an operator native shell for a new disposable G1 site."""
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from odoo import fields
from odoo.addons.mp_identity.scopes import scoped_environment

assert env.cr.dbname.startswith("mp_disposable_r0_g1_")
assert not env["mp.principal"].search_count([]), "Fixture already provisioned; reconcile instead of replaying"
password = Path("/run/mp-bootstrap/password").read_text().strip()
base_group = env.ref("base.group_user")
users = {}
principals = {}
for key, kind in [("alice", "human"), ("bob", "human"), ("outsider", "human"), ("worker", "service")]:
    user = env["res.users"].with_context(no_reset_password=True).create({"name": "G1 " + key.title(), "login": "g1_" + key, "password": password, "group_ids": [(6, 0, base_group.ids)]})
    users[key] = user
    principals[key] = env["mp.principal"].create({"name": user.name, "user_id": user.id, "kind": kind})
workspaces = {key: env["mp.workspace"].create({"name": "G1 Workspace " + key}) for key in ["A", "B"]}
membership_rows = {}
for actor, space, role in [("alice", "A", "editor"), ("alice", "B", "viewer"), ("bob", "B", "editor"), ("worker", "A", "viewer")]:
    membership_rows[actor + space] = env["mp.membership"].create({"principal_id": principals[actor].id, "workspace_id": workspaces[space].id, "role": role})
for workspace in workspaces.values():
    env["mp.workspace.plugin"].create({"workspace_id": workspace.id, "plugin_id": "org.example.feasibility"})
objects = {}
for key, actor in [("A", "alice"), ("B", "bob")]:
    user_env = env(user=users[actor].id, su=False, context={})
    scoped = scoped_environment(user_env, workspaces[key].public_id)
    objects[key] = scoped["mp.feas.record"].create({"name": "Private " + key, "amount": 10 if key == "A" else 20})
token = Path("/run/mp-bootstrap/service_token").read_text().strip()
credential = env["mp.service.credential"].create({"name": "G1 restricted worker", "principal_id": principals["worker"].id, "workspace_id": workspaces["A"].id, "token_digest": hashlib.sha256(token.encode()).hexdigest(), "installation_public_id": str(uuid4()), "actions": "read", "expires_at": fields.Datetime.now() + timedelta(minutes=5)})
env.cr.commit()
print("MP_G1_RESULT=" + json.dumps({"database": env.cr.dbname, "workspaces": {k: {"id": w.id, "public_id": w.public_id} for k, w in workspaces.items()}, "users": {k: {"id": u.id, "login": u.login, "principal_id": principals[k].public_id} for k, u in users.items()}, "objects": {k: {"id": r.id, "public_id": r.public_id} for k, r in objects.items()}, "memberships": {k: row.id for k, row in membership_rows.items()}, "credential_id": credential.id}, sort_keys=True))
