"""Restored native HTTP/session/assets checks; no application data mutation."""
import hashlib
import http.cookiejar
import json
import urllib.request
from clean_recovery_fixture import LOCAL, OUTPUT, load, save, guard
from clean_recovery_data import context, call, PAYLOAD
from modular_platform.contracts import validate
from modular_platform.operator_store import OperatorStore
from modular_platform.native_executor import NativeExecutor
from modular import configuration
from r1_probe import Client as BaseClient


class Client(BaseClient):
    def __init__(self, state, fixture, actor, password_file, success=True):
        self.state=state; self.fixture=fixture; self.base='http://127.0.0.1:'+str(state['port'])
        self.jar=http.cookiejar.CookieJar()
        self.http=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(self.jar))
        status, result=self.request('/web/session/authenticate',dict(jsonrpc='2.0',method='call',id=1,params=dict(db=state['active_db'],login=fixture['users'][actor]['login'],password=(LOCAL/password_file).read_text().strip())))
        assert status==200
        if not success:
            assert 'error' in result and 'result' not in result
            return
        assert result.get('result',{}).get('uid')==fixture['users'][actor]['id']
        status, result=self.request('/api/v1/session'); assert status==200
        self.csrf=result['data']['csrf_token']
        status,result=self.request('/api/v1/client-release'); assert status==200
        validate('client-release',result['data']); self.release_token=result['data']['token']


def main():
    state,target,reader,document,fixture=context()
    assert state['phase']=='restored_resumed'
    Client(state,fixture,'alice','bootstrap-password',success=False)
    alice=Client(state,fixture,'alice','alice-new-password')
    bob=Client(state,fixture,'bob','bootstrap-password')
    operator=Client(state,fixture,'operator','bootstrap-password')
    data=load(LOCAL/'recovery-data.json')
    for space,client in [('A',alice),('B',bob)]:
        result=client.call('list',dict(limit=25),space)
        assert {n['id'] for n in result['items']}=={n['id'] for n in data['notes'][space]}
        for note in data['notes'][space]:assert client.call('get',dict(note_id=note['id']),space)==note
        views=client.native('get_views',kwargs=dict(views=[(False,'list'),(False,'form')],options={}),workspace=space)
        assert '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
        board=call(client,document,fixture,'org.example.canvas','boards','get',{},space)
        old=load(LOCAL/('reference-board-'+space+'.json'))['board']
        assert board['id']==old['public_id'] and board['cards']==old['cards'] and board['revision']==old['revision']
    alice.call('list',dict(limit=25),'B',expect=403,code='FORBIDDEN')
    old=load(LOCAL/'session.json')
    for actor,values in old.items():
        # An expired session response may replace that jar's cookie. Isolate it
        # from the freshly authenticated client used for the release fence.
        expired=BaseClient.__new__(BaseClient)
        expired.base=alice.base; expired.fixture=fixture
        expired.http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        status,_=expired.request('/api/v1/session',headers={'Cookie':'session_id='+values['session_id'],'X-MP-Client-Release':alice.release_token})
        assert status==401
    stale=alice.call('list',dict(limit=25),'A',expect=409,code='CONFLICT',headers={'X-MP-Client-Release':old['alice']['release_token']})
    request=urllib.request.Request(operator.base+'/web/content/'+str(data['attachment_id'])+'?download=1',headers={'X-MP-Client-Release':operator.release_token})
    with operator.http.open(request,timeout=30) as response:
        assert response.status==200 and response.read()==PAYLOAD
    assets=load(OUTPUT/'assets-before-fault.json')
    for asset in assets:
        with operator.http.open(operator.base+asset['path'],timeout=30) as response:
            raw=response.read()
            assert response.status==200 and response.geturl()==operator.base+asset['path']
            assert hashlib.sha256(raw).hexdigest()==asset['sha256'] and len(raw)==asset['bytes']
            assert response.headers['Content-Type']==asset['content_type']
    operation=load(LOCAL/'fault-operation.json')['operation_id']
    store=OperatorStore(LOCAL/'operator/control')
    native=NativeExecutor(store,LOCAL/'operator/target.json',LOCAL/'operator/catalog',configuration(LOCAL/'operator/trust.json'))
    status=store.status(operation)
    assert status['state']=='revoked' and status['phase']=='restore_traffic_resumed' and status['traffic_resumed']
    try:native.apply(operation)
    except Exception as error:
        from modular_platform.operator_os import OperatorError
        assert isinstance(error,OperatorError)
    else:raise AssertionError('Retired native operation replay accepted')
    assert store.status(operation)==status
    guard(state)
    save('restored-HTTP.json',dict(result='passed',generation=4,old_Alice_password_denied=True,new_Alice_password_valid=True,current_Alice_B_revocation_enforced=True,Bob_B_native_and_gateway=True,standard_list_form='native Odoo',reference_boards_exact=2,old_sessions_invalidated=len(old),old_release_conflict=True,native_private_attachment_bytes=len(PAYLOAD),immutable_nonredirect_asset_hashes=len(assets),traffic_resumed_by_separate_exact_review=True,retired_operation_apply_refused_without_journal_change=True,application_data_mutations=0))
    print(json.dumps(dict(result='passed_restored_HTTP',native_views=True,assets=len(assets))))


if __name__=='__main__':main()
