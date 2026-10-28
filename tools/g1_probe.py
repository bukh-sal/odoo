"""Real PostgreSQL/HTTP feasibility checks. Never print passwords/tokens."""
from __future__ import annotations

import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import g1

r0 = g1.r0


class Client:
    def __init__(self, state, fixture, actor):
        self.base = f"http://127.0.0.1:{state['port']}"
        self.jar = http.cookiejar.CookieJar()
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(self.jar))
        self.user = fixture["users"][actor]
        password = (r0.LOCAL / "bootstrap-password").read_text().strip()
        data = self.request("/web/session/authenticate", {"jsonrpc": "2.0", "method": "call", "id": 1, "params": {"db": state["active_db"], "login": self.user["login"], "password": password}})[1]
        assert data.get("result", {}).get("uid") == self.user["id"], "Fixture login failed"
        self.csrf = {}

    def request(self, path, payload=None, workspace=None, headers=None):
        values = dict(headers or {})
        if workspace:
            values["X-MP-Workspace"] = workspace
        body = None
        if payload is not None:
            values["Content-Type"] = "application/json"
            body = json.dumps(payload).encode()
        request = urllib.request.Request(self.base + path, data=body, headers=values)
        try:
            response = self.http.open(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read()
            try:
                result = json.loads(raw)
            except ValueError:
                result = {"non_json_status": response.code}
            return response.code, result

    def context(self, workspace):
        status, result = self.request("/mp/feas/context", workspace=workspace)
        assert status == 200 and "data" in result, "Scoped context failed"
        self.csrf[workspace] = result["data"]["csrf_token"]
        return result["data"]

    def native(self, method, args=None, kwargs=None, workspace=None, deny=False, model="mp.feas.record"):
        status, result = self.request(f"/web/dataset/call_kw/{model}.{method}", {"jsonrpc": "2.0", "method": "call", "id": 1, "params": {"model": model, "method": method, "args": args or [], "kwargs": kwargs or {}}}, workspace)
        if deny:
            name = result.get("error", {}).get("data", {}).get("name", "")
            assert name.endswith("AccessError"), "Expected native authorization denial, not another failure"
            return True
        assert status == 200 and "error" not in result, "Native operation unexpectedly denied/failed"
        return result.get("result")

    def gateway(self, workspace, body, deny=False):
        if workspace not in self.csrf:
            self.context(workspace)
        status, result = self.request("/mp/feas/gateway", body, workspace, {"X-CSRFToken": self.csrf[workspace]})
        if deny:
            assert status == 403 and result.get("error", {}).get("code") == "FORBIDDEN", "Expected typed gateway permission denial"
            return True
        assert status == 200 and "data" in result, "Gateway operation failed"
        return result["data"]


def main():
    state = g1.setup()
    fixture = json.loads((r0.LOCAL / "fixtures.json").read_text())
    assert fixture["database"] == state["active_db"]
    a = fixture["workspaces"]["A"]["public_id"]
    b = fixture["workspaces"]["B"]["public_id"]
    obj_a, obj_b = fixture["objects"]["A"], fixture["objects"]["B"]
    # Reset only explicit synthetic fixture policy/values, recording the action.
    # This is not a general database reset or a production operator interface.
    prepare = f"""from datetime import timedelta
from odoo import fields
from odoo.addons.mp_identity.scopes import scoped_environment
assert env.cr.dbname == {state['active_db']!r}
for ident,role in [({fixture['memberships']['aliceA']!r},'editor'),({fixture['memberships']['aliceB']!r},'viewer')]:
    env['mp.membership'].browse(ident).write({{'role':role,'state':'active'}})
env['mp.workspace.plugin'].search([('plugin_id','=','org.example.feasibility')]).write({{'availability':'enabled'}})
for uid,workspace,ident,amount in [({fixture['users']['alice']['id']!r},{a!r},{obj_a['id']!r},10),({fixture['users']['bob']['id']!r},{b!r},{obj_b['id']!r},20)]:
    scoped=scoped_environment(env(user=uid,su=False,context={{}}),workspace)
    scoped['mp.feas.record'].browse(ident).write({{'amount':amount}})
env['mp.service.credential'].browse({fixture['credential_id']!r}).write({{'expires_at':fields.Datetime.now()+timedelta(minutes=5),'state':'active'}})
env.cr.commit()
env.registry.signal_changes()
print('MP_G1_RESULT=known-fixture-policy-prepared')
"""
    g1.shell(state, "g1-prepare-probe", prepare)
    clients = {name: Client(state, fixture, name) for name in ["alice", "bob", "outsider"]}
    alice, bob, outsider = clients.values()
    checks = []

    def check(name, action):
        details = action()
        entry = {"name": name, "result": "passed"}
        if isinstance(details, dict):
            entry["details"] = details
        checks.append(entry)
        path.write_text(json.dumps({"state": "in_progress", "checks": checks}, indent=2) + "\n")

    path = r0.ROOT / state["evidence"] / (r0.now() + "-backend-feasibility.json")
    def roles():
        assert alice.context(a)["role"] == "editor"
        assert alice.context(b)["role"] == "viewer"
    check("same backing user has asymmetric roles", roles)
    def reads():
        for _ in range(8):
            for workspace, expected, forbidden, amount in [(a, obj_a, obj_b, 10), (b, obj_b, obj_a, 20)]:
                values = alice.native("search_read", kwargs={"domain": [("id", "in", [obj_a["id"], obj_b["id"]])], "fields": ["name", "amount"]}, workspace=workspace)
                assert [row["id"] for row in values] == [expected["id"]]
                groups = alice.native("read_group", kwargs={"domain": [("id", "in", [obj_a["id"], obj_b["id"]])], "fields": ["amount:sum"], "groupby": []}, workspace=workspace)
                assert len(groups) == 1 and groups[0]["amount"] == amount
    check("warmed native searches and aggregates stay in intended workspace", reads)
    check("viewer cannot create", lambda: alice.native("create", [{"name": "denied"}], workspace=b, deny=True))
    check("viewer cannot update", lambda: alice.native("write", [[obj_b["id"]], {"amount": 999}], workspace=b, deny=True))
    check("viewer cannot delete", lambda: alice.native("unlink", [[obj_b["id"]]], workspace=b, deny=True))
    check("missing workspace fails closed", lambda: alice.native("search_read", deny=True))
    check("nonmember cannot select workspace", lambda: outsider.native("search_read", workspace=a, deny=True))
    for method, args in [("read", [[obj_b["id"]], ["name"]]), ("write", [[obj_b["id"]], {"amount": 999}]), ("unlink", [[obj_b["id"]]])]:
        check("cross-workspace " + method + " rejected", lambda method=method, args=args: alice.native(method, args, workspace=a, deny=True))
    check("forged create owner rejected", lambda: alice.native("create", [{"name": "denied", "workspace_id": fixture["workspaces"]["B"]["id"]}], workspace=a, deny=True))
    check("ownership transfer rejected", lambda: alice.native("write", [[obj_a["id"]], {"workspace_id": fixture["workspaces"]["B"]["id"]}], workspace=a, deny=True))
    check("foreign many2one rejected", lambda: alice.native("write", [[obj_a["id"]], {"peer_id": obj_b["id"]}], workspace=a, deny=True))
    check("foreign many2many link rejected", lambda: alice.native("write", [[obj_a["id"]], {"peer_ids": [[4, obj_b["id"], 0]]}], workspace=a, deny=True))
    check("foreign many2many set rejected", lambda: alice.native("write", [[obj_a["id"]], {"peer_ids": [[6, 0, [obj_b["id"]]]]}], workspace=a, deny=True))
    check("forged platform context rejected", lambda: alice.native("search_read", kwargs={"context": {"mp_workspace_id": fixture["workspaces"]["B"]["id"], "sudo": True}}, workspace=a, deny=True))
    def allowed_crud():
        ident = alice.native("create", [{"name": "Owned temporary record", "amount": 3}], workspace=a)
        assert isinstance(ident, int)
        assert alice.native("write", [[ident], {"amount": 4}], workspace=a)
        assert alice.native("read", [[ident], ["amount"]], workspace=a)[0]["amount"] == 4
        assert alice.native("unlink", [[ident]], workspace=a)
    check("editor native CRUD succeeds without core patch", allowed_crud)
    def gateway_crud():
        record = alice.gateway(a, {"operation": "create", "input": {"name": "Gateway temporary", "amount": 2}})
        updated = alice.gateway(a, {"operation": "update", "object_id": record["public_id"], "input": {"amount": 3}})
        assert updated["public_id"] == record["public_id"]
        assert alice.gateway(a, {"operation": "delete", "object_id": record["public_id"]})["deleted"]
        for value in [obj_b["public_id"], "00000000-0000-0000-0000-000000000001"]:
            status, result = alice.request("/mp/feas/gateway", {"operation": "update", "object_id": value, "input": {"amount": 999}}, a, {"X-CSRFToken": alice.csrf[a]})
            assert status == 404 and result.get("error", {}).get("code") == "NOT_FOUND"
    check("gateway CRUD and forbidden/not-found consistency", gateway_crud)
    def forgery():
        values = alice.native("search_read", kwargs={"domain": [("id", "in", [obj_a["id"], obj_b["id"]])], "fields": ["name"], "context": {"uid": 1, "sudo": True}}, workspace=a)
        assert [row["id"] for row in values] == [obj_a["id"]]
        alice.native("search_read", kwargs={"context": {"allowed_company_ids": [999999]}}, workspace=a, deny=True)
    check("forged actor/sudo/company context cannot grant authority", forgery)
    def group_composition():
        code = """model=env['ir.model']._get('mp.feas.record')
assert env['ir.rule'].search_count([('model_id','=',model.id),('global','=',True)])
if not env['ir.rule'].search_count([('name','=','G1 deliberately broad group rule')]):
    env['ir.rule'].create({'name':'G1 deliberately broad group rule','model_id':model.id,'groups':[(6,0,env.ref('base.group_user').ids)],'domain_force':"[(1, '=', 1)]"})
env.cr.commit()
env.registry.signal_changes()
"""
        g1.shell(state, "g1-broad-group-rule", code)
        reads()
        alice.native("read", [[obj_b["id"]], ["name"]], workspace=a, deny=True)
    check("broad group rule cannot widen global workspace scope", group_composition)
    check("gateway viewer denial", lambda: alice.gateway(b, {"operation": "update", "object_id": obj_b["public_id"], "input": {"amount": 999}}, deny=True))
    check("provider chain preserves viewer authority", lambda: alice.gateway(b, {"operation": "provider_chain_write", "object_id": obj_b["public_id"], "input": {"amount": 999}, "attributed_plugin_id": "org.modularplatform.core", "actor_id": 1}, deny=True))
    def technical():
        token = (r0.LOCAL / "service-token").read_text().strip()
        headers = {"Authorization": "Bearer " + token}
        status, result = outsider.request("/mp/feas/technical", {"operation": "list"}, a, headers)
        assert status == 200 and "data" in result
        assert obj_a["public_id"] in {row["public_id"] for row in result["data"]}
        for workspace, body in [(a, {"operation": "create", "input": {"name": "denied"}, "actor_id": fixture["users"]["alice"]["id"], "sudo": True}), (b, {"operation": "list", "workspace_id": a})]:
            status, result = outsider.request("/mp/feas/technical", body, workspace, headers)
            assert status == 403 and result.get("error", {}).get("code") == "FORBIDDEN"
    check("scoped technical identity cannot create or switch workspace", technical)
    def revocation():
        membership = fixture["memberships"]["aliceB"]
        g1.shell(state, "g1-grant-editor-B", f"env['mp.membership'].browse({membership!r}).write({{'role':'editor'}})\nenv.cr.commit()\nenv.registry.signal_changes()\n")
        assert alice.native("write", [[obj_b["id"]], {"amount": 21}], workspace=b)
        g1.shell(state, "g1-revoke-editor-B", f"env['mp.membership'].browse({membership!r}).write({{'role':'viewer'}})\nenv.cr.commit()\nenv.registry.signal_changes()\n")
        started = time.monotonic()
        since = datetime.now(timezone.utc).isoformat()
        with ThreadPoolExecutor(max_workers=8) as executor:
            assert all(executor.map(lambda _: alice.native("write", [[obj_b["id"]], {"amount": 999}], workspace=b, deny=True), range(40)))
        assert time.monotonic() - started < 30
        log = r0.execute(state, "g1-revocation-worker-logs", r0.compose() + ["logs", "--no-color", "--since", since, "app"])
        workers = sorted(set(re.findall(r"\s(\d+)\s+(?:INFO|WARNING)\s+[^\n]*werkzeug:[^\n]*POST /web/dataset/call_kw/mp\.feas\.record\.write", log.read_text(errors="replace"))))
        assert len(workers) >= 2, "Revocation proof did not cover two workers"
        return {"worker_pids": workers, "elapsed_seconds": round(time.monotonic() - started, 3), "denied_requests": 40}
    check("committed role revocation affects fresh concurrent requests", revocation)
    def membership_revocation():
        membership = fixture["memberships"]["aliceB"]
        g1.shell(state, "g1-revoke-membership-B", f"env['mp.membership'].browse({membership!r}).write({{'state':'revoked'}})\nenv.cr.commit()\n")
        try:
            alice.native("search_read", workspace=b, deny=True)
            status, result = alice.request("/mp/feas/context", workspace=b)
            assert status == 403, "Revoked membership still has context access"
            assert result.get("error", {}).get("code") == "FORBIDDEN", "Context denial must use typed public errors"
        finally:
            g1.shell(state, "g1-restore-membership-B", f"env['mp.membership'].browse({membership!r}).write({{'state':'active'}})\nenv.cr.commit()\n")
    check("revoked membership denies both native and context routes", membership_revocation)
    def suspension():
        ident = fixture["workspaces"]["A"]["id"]
        g1.shell(state, "g1-suspend-A", f"env['mp.workspace.plugin'].search([('workspace_id','=',{ident!r}),('plugin_id','=','org.example.feasibility')]).write({{'availability':'suspended'}})\nenv.cr.commit()\n")
        try:
            alice.native("search_read", workspace=a, deny=True)
            alice.gateway(a, {"operation": "list"}, deny=True)
        finally:
            g1.shell(state, "g1-enable-A", f"env['mp.workspace.plugin'].search([('workspace_id','=',{ident!r}),('plugin_id','=','org.example.feasibility')]).write({{'availability':'enabled'}})\nenv.cr.commit()\n")
        assert obj_a["public_id"] in {row["public_id"] for row in alice.gateway(a, {"operation": "list"})}
    check("feature suspension gates both transports and preserves records", suspension)
    path.write_text(json.dumps({"state": "passed", "scope": "G1 backend proof only; browser/contract freeze still pending", "checks": checks}, indent=2) + "\n")
    print(json.dumps({"backend_checks": len(checks), "result": "passed", "evidence": str(path.relative_to(r0.ROOT))}))


if __name__ == "__main__":
    main()
