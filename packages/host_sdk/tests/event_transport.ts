/** Wire types coexist with the unchanged major1 plugin facade. */
import type {EventTransportRequest,EventTransportResult,DomainEventEnvelope,HostEvent} from '../src/index';
const uuid='00000000-0000-4000-8000-000000000001';
const requests:readonly EventTransportRequest[]=[
    {protocol:1,kind:'subscribe_request',request_id:uuid,topic:'org.example.notes.changed',idempotency_key:uuid},
    {protocol:1,kind:'poll_request',request_id:uuid,subscription_id:uuid,limit:50},
    {protocol:1,kind:'ack_request',request_id:uuid,subscription_id:uuid,receipts:[{delivery_id:uuid,receipt:uuid,generation:1}]},
    {protocol:1,kind:'status_request',request_id:uuid,subscription_id:uuid},
    {protocol:1,kind:'replay_request',request_id:uuid,subscription_id:uuid,event_ids:[uuid]},
    {protocol:1,kind:'close_request',request_id:uuid,subscription_id:uuid},
];
const event:DomainEventEnvelope={id:uuid,topic:'org.example.notes.changed',schema_version:1,owner_plugin_id:'org.example.notes',aggregate_id:uuid,aggregate_sequence:1,site_id:uuid,workspace_id:uuid,occurred_at:'2026-10-29T15:00:00Z',correlation_id:uuid,causation_id:null,payload:{note_id:uuid,revision:1,change:'created'}};
const result:EventTransportResult={protocol:1,kind:'poll_result',subscription_id:uuid,deliveries:[{id:uuid,receipt:uuid,generation:1,attempt:1,lease_expires_at:'2026-10-29T15:00:15Z',event}],has_more:false,dead_letter_count:0,next_poll_ms:2000};
const facadeEvent:HostEvent={id:event.id,topic:event.topic,data:event.payload,generation:1};
void requests;void result;void facadeEvent;
