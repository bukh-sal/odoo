"""G2 event wire/golden limits; real delivery authority remains G6 evidence."""
import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.contracts import ContractError,validate
CASES=json.loads((ROOT/'packages/contracts/fixtures/v1/event-transport-cases.json').read_text())['valid']


class EventContracts(unittest.TestCase):
    def valid(self,name):return copy.deepcopy(CASES[name])

    def test_all_twelve_golden_requests_and_results(self):
        self.assertEqual(len(CASES),12)
        for name,value in CASES.items():
            with self.subTest(message=name):self.assertIs(validate('event-transport',value),value)

    def test_requests_never_accept_authority_claims(self):
        for name in CASES:
            if not name.endswith('_request'):continue
            for field in ['actor_id','user_id','role','workspace_id','site_id','permissions','credential','approved','consumer_installation_id']:
                value=self.valid(name);value[field]='untrusted'
                with self.subTest(message=name,field=field),self.assertRaises(ContractError):validate('event-transport',value)

    def test_protocol_version_topic_and_identifiers_are_strict(self):
        for field,wrong in [('protocol',True),('protocol',2),('request_id','1'),('request_id',CASES['subscribe_request']['request_id']+'\n'),('topic','org.example.notes.changed\n'),('idempotency_key',1),('kind','unknown')]:
            value=self.valid('subscribe_request');value[field]=wrong
            with self.subTest(field=field,value_type=type(wrong).__name__),self.assertRaises(ContractError):validate('event-transport',value)
        # A valid routing/topic shape confers no current registry permission.
        value=self.valid('subscribe_request');value['topic']='org.example.unknown.changed';validate('event-transport',value)

    def test_notes_payload_is_minimized_and_coherent(self):
        for field in ['title','body','labels','role']:
            value=self.valid('poll_result');value['deliveries'][0]['event']['payload'][field]='private synthetic content'
            with self.subTest(field=field),self.assertRaises(ContractError) as error:validate('event-transport',value)
            self.assertNotIn('private synthetic content',str(error.exception))
        for field,wrong in [('schema_version',2),('owner_plugin_id','org.example.other'),('aggregate_id',CASES['poll_result']['subscription_id']),('aggregate_sequence',3),('aggregate_sequence',None)]:
            value=self.valid('poll_result');value['deliveries'][0]['event'][field]=wrong
            with self.subTest(field=field),self.assertRaises(ContractError):validate('event-transport',value)

    def test_UTC_calendar_and_lease_bounds(self):
        for date in ['2026-02-30T15:00:00Z','2026-13-01T15:00:00Z','2026-10-29T15:00:00+00:00','2026-10-29T15:00:00Z\n','2026-10-29T25:00:00Z']:
            value=self.valid('poll_result');value['deliveries'][0]['lease_expires_at']=date
            with self.subTest(timestamp=date),self.assertRaises(ContractError):validate('event-transport',value)
        for field,wrong in [('generation',True),('generation',0),('attempt',6),('attempt',0)]:
            value=self.valid('poll_result');value['deliveries'][0][field]=wrong
            with self.subTest(field=field,wrong=wrong),self.assertRaises(ContractError):validate('event-transport',value)

    def test_duplicate_delivery_event_and_acknowledgement_targets_fail(self):
        value=self.valid('poll_result');value['deliveries']*=2
        with self.assertRaises(ContractError):validate('event-transport',value)
        value=self.valid('poll_result');other=copy.deepcopy(value['deliveries'][0]);other['id']=value['subscription_id'];value['deliveries'].append(other)
        with self.assertRaises(ContractError):validate('event-transport',value)
        value=self.valid('ack_request');other=copy.deepcopy(value['receipts'][0]);other['generation']=2;value['receipts'].append(other)
        with self.assertRaises(ContractError):validate('event-transport',value)

    def generic(self):
        value=self.valid('poll_result');event=value['deliveries'][0]['event'];event['topic']='org.example.other.changed';event['owner_plugin_id']='org.example.other';return value,event

    def test_bounded_depth_and_event_and_message_bytes(self):
        value,event=self.generic();child=event['payload']={}
        for _ in range(20):child['nested']={};child=child['nested']
        with self.assertRaisesRegex(ContractError,'depth'):validate('event-transport',value)
        value,event=self.generic();event['payload']={str(i):'x'*2048 for i in range(8)}
        with self.assertRaisesRegex(ContractError,'Event exceeds byte limit'):validate('event-transport',value)
        value,event=self.generic();event['payload']={str(i):'x'*2048 for i in range(3)};value['deliveries']*=20
        with self.assertRaisesRegex(ContractError,'message exceeds byte limit'):validate('event-transport',value)

    def test_invalid_numbers_unicode_and_unknown_error_text_fail_safely(self):
        for wrong in [float('nan'),float('inf'),9007199254740992,'\ud800']:
            value,event=self.generic();event['payload']={'value':wrong}
            with self.subTest(value_type=type(wrong).__name__),self.assertRaises(ContractError):validate('event-transport',value)
        value=self.valid('status_result');value['deliveries'][0]['error_code']='raw SQL or exception text'
        with self.assertRaises(ContractError) as error:validate('event-transport',value)
        self.assertNotIn('raw SQL or exception text',str(error.exception))

    def test_array_retention_retry_and_replay_bounds(self):
        for name,field,wrong in [('poll_request','limit',0),('poll_request','limit',51),('subscribe_result','replay_window_seconds',0),('subscribe_result','ack_lease_seconds',60),('subscribe_result','max_attempts',6),('subscribe_result','max_replays',4),('replay_request','event_ids',[]),('ack_request','receipts',[])]:
            value=self.valid(name);value[field]=wrong
            with self.subTest(message=name,field=field),self.assertRaises(ContractError):validate('event-transport',value)


if __name__=='__main__':unittest.main()
