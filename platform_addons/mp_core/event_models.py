"""Native-owned private event routing/receipts; no generic human ORM CRUD."""
from odoo import fields,models


class EventSubscription(models.Model):
    _name='mp.event.subscription'
    _description='Private scoped domain-event subscription'
    _log_access=False
    public_id=fields.Char(required=True,index=True)
    site_id=fields.Char(required=True,index=True)
    workspace_id=fields.Many2one('mp.workspace',required=True,ondelete='restrict',index=True)
    actor_id=fields.Many2one('mp.principal',required=True,ondelete='restrict',index=True)
    installation_id=fields.Many2one('mp.plugin.installation',required=True,ondelete='restrict')
    topic=fields.Char(required=True,index=True)
    binding=fields.Json(required=True)
    release_digest=fields.Char(required=True)
    origin_installation_id=fields.Char()
    idempotency_key=fields.Char(required=True)
    input_digest=fields.Char(required=True)
    state=fields.Selection([('active','Active'),('closed','Closed')],required=True,default='active')
    created_at=fields.Datetime(required=True)
    expires_at=fields.Datetime(required=True,index=True)
    _public_unique=models.Constraint('UNIQUE(public_id)','Subscription ID must be unique')
    _key_unique=models.Constraint('UNIQUE(site_id,workspace_id,actor_id,installation_id,idempotency_key)','Scoped subscription key must be unique')


class EventDelivery(models.Model):
    _name='mp.event.delivery'
    _description='Private leased event delivery'
    _log_access=False
    public_id=fields.Char(required=True,index=True)
    subscription_id=fields.Many2one('mp.event.subscription',required=True,ondelete='restrict',index=True)
    event_id=fields.Many2one('mp.outbox',required=True,ondelete='restrict',index=True)
    state=fields.Selection([(x,x.title()) for x in ['pending','leased','acknowledged','dead_letter']],required=True,default='pending',index=True)
    generation=fields.Integer(required=True,default=0)
    attempts=fields.Integer(required=True,default=0)
    replays=fields.Integer(required=True,default=0)
    receipt=fields.Char()
    lease_until=fields.Datetime()
    available_at=fields.Datetime(required=True,index=True)
    acknowledged_at=fields.Datetime()
    error_code=fields.Char()
    _public_unique=models.Constraint('UNIQUE(public_id)','Delivery ID must be unique')
    _event_unique=models.Constraint('UNIQUE(subscription_id,event_id)','One receipt per subscription/event')
    _bounds=models.Constraint('CHECK(generation>=0 AND attempts BETWEEN 0 AND 5 AND replays BETWEEN 0 AND 3)','Invalid event-delivery bounds')


class EventConsumption(models.Model):
    _name='mp.event.consumption'
    _description='Private atomic native consumer deduplication'
    _log_access=False
    public_id=fields.Char(required=True,index=True)
    workspace_id=fields.Many2one('mp.workspace',required=True,ondelete='restrict')
    actor_id=fields.Many2one('mp.principal',required=True,ondelete='restrict')
    installation_id=fields.Many2one('mp.plugin.installation',required=True,ondelete='restrict')
    event_id=fields.Many2one('mp.outbox',required=True,ondelete='restrict')
    handler=fields.Char(required=True)
    created_at=fields.Datetime(required=True)
    _public_unique=models.Constraint('UNIQUE(public_id)','Consumption ID must be unique')
    _dedup_unique=models.Constraint('UNIQUE(installation_id,workspace_id,handler,event_id)','One native consumer effect per event')


class EventConsumerState(models.Model):
    _name='mp.event.consumer.state'
    _description='Private native event-consumer serialization'
    _log_access=False
    workspace_id=fields.Many2one('mp.workspace',required=True,ondelete='restrict')
    installation_id=fields.Many2one('mp.plugin.installation',required=True,ondelete='restrict')
    handler=fields.Char(required=True)
    generation=fields.Integer(required=True,default=1)
    _handler_unique=models.Constraint('UNIQUE(installation_id,workspace_id,handler)','One native consumer lock per scope')
