from datetime import timezone
from uuid import uuid4
import base64
import json

from odoo import api, fields, models
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.addons.mp_identity.scopes import current_scope
from odoo.addons.mp_core.controllers import PublicError


class Note(models.Model):
    _name = 'mp.example.note'
    _description = 'Workspace note'
    _inherit = ['mp.workspace.scoped']
    _mp_plugin_id = 'org.example.notes'
    _rec_name = 'title'
    _order = 'write_date desc,id desc'

    public_id = fields.Char(default=lambda self:str(uuid4()),required=True,index=True,readonly=True)
    title = fields.Char(required=True,size=200)
    body = fields.Text(default='')
    author_id = fields.Many2one('mp.principal',required=True,ondelete='restrict',readonly=True)
    revision = fields.Integer(default=1,required=True,readonly=True)
    _public_unique = models.Constraint('UNIQUE(public_id)', 'Note ID must be unique')
    _revision_positive = models.Constraint('CHECK(revision > 0)', 'Note revision must be positive')

    @api.constrains('title','body')
    def _validate_content(self):
        for record in self:
            if not record.title.strip() or len(record.body or '')>20000:
                raise ValidationError('Title required; body must be at most 20000 characters')

    @api.model_create_multi
    def create(self, values_list):
        scope=self._mp_guard('create')
        clean=[]
        for values in values_list:
            if set(values)-{'title','body','workspace_id'}:raise AccessError('Only declared note input fields may be created')
            clean.append({**values,'author_id':scope.principal_id,'revision':1})
        return super().create(clean)

    def write(self,values):
        self._mp_guard('write')
        if set(values)-{'title','body'}:raise AccessError('Only declared note fields may be updated')
        if self.ids:
            # Serialize revision increments for native and gateway writes alike.
            self.env.cr.execute('SELECT id FROM mp_example_note WHERE id=ANY(%s) ORDER BY id FOR UPDATE',[self.ids])
            self.invalidate_recordset(['revision'])
        expected=self.env.context.get('expected_revision')
        expected_batch=self.env.context.get('expected_revisions',{})
        for record in self:
            desired=expected_batch.get(str(record.id),expected) if isinstance(expected_batch,dict) else None
            if type(desired)is not int or desired!=record.revision:raise PublicError('CONFLICT',{'field':'revision','outcome':'not_started'})
            super(Note,record).write({**values,'revision':record.revision+1})
        return True

    def unlink(self):
        self._mp_guard('unlink')
        self.env.cr.execute('SELECT id,revision FROM mp_example_note WHERE id=ANY(%s) ORDER BY id FOR UPDATE',[self.ids])
        expected=self.env.context.get('expected_revision');batch=self.env.context.get('expected_revisions',{})
        for ident,revision in self.env.cr.fetchall():
            desired=batch.get(str(ident),expected) if isinstance(batch,dict) else None
            if type(desired)is not int or desired!=revision:raise PublicError('CONFLICT',{'field':'revision','outcome':'not_started'})
        return super().unlink()

    def _load_records_write(self,values):
        # Native imports retain their resolved database ID in the update values.
        # Consume that routing reference only here, after ownership preflight;
        # the public write/create contracts still reject identity assignment.
        self.ensure_one();self._mp_guard('write')
        values=dict(values)
        if values.pop('id',self.id)!=self.id:raise AccessError('Import identity mismatch')
        return super()._load_records_write(values)

    def _dto(self):
        self.ensure_one();self._mp_guard('read')
        updated=self.write_date or self.create_date
        return {'id':self.public_id,'title':self.title,'body':self.body or '', 'revision':self.revision,'labels':[], 'updated_at':updated.replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')}

    @api.model
    def _by_public(self,ident,action='read'):
        self._mp_guard(action)
        record=self.search([('public_id','=',ident)],limit=1)
        if not record:raise MissingError('Resource unavailable')
        return record

    @api.model
    def _mp_service_list(self,values):
        self._mp_guard('read')
        offset=0
        if values.get('cursor'):
            try:
                raw=json.loads(base64.urlsafe_b64decode(values['cursor']+'==='))
                if set(raw)!={'offset'} or not isinstance(raw['offset'],int) or not 0<=raw['offset']<=100000:raise ValueError()
                offset=raw['offset']
            except (ValueError,TypeError):raise ValidationError('Invalid paging cursor') from None
        domain=[('title','ilike',values['query'])] if values.get('query') else []
        order='title,id' if values.get('order')=='title_asc' else 'write_date desc,id desc'
        rows=self.search(domain,limit=values['limit']+1,offset=offset,order=order)
        more=len(rows)>values['limit'];rows=rows[:values['limit']]
        cursor=base64.urlsafe_b64encode(json.dumps({'offset':offset+len(rows)}).encode()).decode().rstrip('=') if more else None
        return {'items':[r._dto() for r in rows],'next_cursor':cursor}

    @api.model
    def _mp_service_get(self,values):return self._by_public(values['note_id'])._dto()

    @api.model
    def _mp_service_create(self,values):return self.create(values)._dto()

    def _expected(self,values,action):
        record=self._by_public(values['note_id'],action)
        self.env.cr.execute('SELECT revision FROM mp_example_note WHERE id=%s FOR UPDATE',[record.id])
        if self.env.cr.fetchone()[0]!=values['expected_revision']:raise PublicError('CONFLICT',{'field':'revision','outcome':'not_started'})
        record.invalidate_recordset()
        return record

    @api.model
    def _mp_service_update(self,values):
        record=self._expected(values,'write')
        record.with_context(expected_revision=values['expected_revision']).write({k:v for k,v in values.items() if k in {'title','body'}})
        return record._dto()

    @api.model
    def _mp_service_delete(self,values):
        record=self._expected(values,'unlink');ident=record.public_id;record.with_context(expected_revision=values['expected_revision']).unlink()
        return {'id':ident,'deleted':True}

    def _v2_dto(self):
        value=self._dto()
        return {'document_id':value['id'],'content':{'headline':value['title'],'text':value['body']},'revision':value['revision'],'labels':value['labels'],'updated_at':value['updated_at']}

    @api.model
    def _mp_service_v2_get(self,values):return self._by_public(values['document_id'])._v2_dto()

    @api.model
    def _mp_service_v2_list(self,values):
        self._mp_guard('read')
        return {'documents':[record._v2_dto() for record in self.search([],limit=values['limit'],order='title,id')]}
