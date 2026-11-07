"""App-owned continuation state; no generic workflow or public RPC surface."""
from datetime import datetime,timedelta,timezone
import hashlib
import json
import re
from uuid import UUID,uuid4

from odoo import api,fields,models
from odoo.exceptions import MissingError,ValidationError
from odoo.addons.mp_core import job_dispatch
from odoo.addons.mp_core.controllers import PublicError
from modular_platform.durable import JobSchedule

from .models import PLUGIN

CHUNK=100
MAX_ITEMS=5000
CONTRACT=1
EMPTY_DIGEST='0'*64


def digest(value):
    return hashlib.sha256(json.dumps(value,separators=(',',':')).encode()).hexdigest()


class ReportRun(models.Model):
    _name='mp.background.report'
    _description='Private reference report continuation'

    public_id=fields.Char(required=True,index=True)
    workspace_id=fields.Many2one('mp.workspace',required=True,ondelete='restrict',index=True)
    actor_id=fields.Many2one('mp.principal',required=True,ondelete='restrict',index=True)
    request_key=fields.Char(required=True,size=120)
    request_first=fields.Integer(required=True)
    request_last=fields.Integer(required=True)
    contract_version=fields.Integer(required=True,default=CONTRACT)
    state=fields.Selection([('running','Running'),('completed','Completed'),('cancelled','Cancelled')],required=True)
    snapshot=fields.Json(required=True)
    snapshot_digest=fields.Char(required=True)
    cursor=fields.Integer(required=True,default=0)
    total=fields.Integer(required=True)
    points=fields.Integer(required=True,default=0)
    result_digest=fields.Char(required=True,default=EMPTY_DIGEST)
    expires_at=fields.Datetime(required=True)
    job_public_id=fields.Char(index=True)
    _identity=models.Constraint('UNIQUE(public_id)','Unique report identity required')
    _request=models.Constraint('UNIQUE(workspace_id,actor_id,request_key)','Unique scoped report request required')
    _bounds=models.Constraint('CHECK(cursor>=0 AND cursor<=total AND total BETWEEN 1 AND 5000 AND points BETWEEN 0 AND 5000000)',
        'Bounded report progress required')


class TaskReports(models.Model):
    _inherit='mp.background.task'

    def _report_row(self,ident,*,lock=False):
        try:
            if type(ident) is not str or str(UUID(ident))!=ident:raise ValueError()
        except (ValueError,TypeError,AttributeError):raise ValidationError('Canonical report identity required') from None
        scope=self._mp_guard('read')
        job_dispatch._locked_scope(self._job_env())
        self.env.cr.execute('SELECT to_jsonb(r) FROM mp_background_report r WHERE public_id=%s AND workspace_id=%s AND actor_id=%s'
            +(' FOR UPDATE' if lock else ''),[ident,scope.workspace_id,scope.principal_id])
        found=self.env.cr.fetchone()
        if not found:raise MissingError('Report unavailable.')
        return found[0]

    def _queue_report_chunk(self,row,cursor):
        now=fields.Datetime.now().replace(tzinfo=timezone.utc)
        expiry=datetime.fromisoformat(row['expires_at']).replace(tzinfo=timezone.utc)
        return job_dispatch.enqueue_scheduled(self._job_env(),'jobs',PLUGIN+':report_chunk',
            dict(run=row['public_id'],cursor=cursor),row['public_id']+':chunk:'+str(cursor),version=CONTRACT,
            schedule=JobSchedule(now,expiry,20))

    @api.model
    def _start_report(self,first,last,key):
        if (type(first) is not int or type(last) is not int or not 1<=first<=last<2**31
                or type(key) is not str or not re.fullmatch(r'[A-Za-z0-9._:-]{1,120}',key)):
            raise ValidationError('A bounded task range and request key are required.')
        scope=self._mp_guard('read')
        job_dispatch._locked_scope(self._job_env())
        # Native savepoint flush/cache handling also protects callers that
        # catch a failed enqueue and commit unrelated work.
        with self.env.cr.savepoint():
            self.env.cr.execute('SELECT public_id,request_first,request_last FROM mp_background_report WHERE workspace_id=%s AND actor_id=%s AND request_key=%s',
                [scope.workspace_id,scope.principal_id,key])
            found=self.env.cr.fetchone()
            if found:
                if found[1:]!=(first,last):raise PublicError('CONFLICT')
                return found[0]
            records=self.search([('id','>=',first),('id','<=',last)],order='id',limit=MAX_ITEMS+1)
            if not 1<=len(records)<=MAX_ITEMS:raise ValidationError('Select between one and 5000 authorized tasks.')
            items=[[row['id'],row['points']] for row in records.read(['points'])]
            ident=str(uuid4());now=fields.Datetime.now();expiry=now+timedelta(hours=1)
            self.env.cr.execute("""INSERT INTO mp_background_report
                (public_id,workspace_id,actor_id,request_key,request_first,request_last,contract_version,state,
                snapshot,snapshot_digest,cursor,total,points,result_digest,expires_at,create_uid,write_uid,create_date,write_date)
                VALUES(%s,%s,%s,%s,%s,%s,1,'running',%s::jsonb,%s,0,%s,0,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(workspace_id,actor_id,request_key) DO UPDATE SET request_key=EXCLUDED.request_key
                RETURNING public_id,request_first,request_last""",
                [ident,scope.workspace_id,scope.principal_id,key,first,last,json.dumps(items),digest(items),len(items),
                 EMPTY_DIGEST,expiry,self.env.uid,self.env.uid,now,now])
            actual=self.env.cr.fetchone()
            if actual[1:]!=(first,last):raise PublicError('CONFLICT')
            if actual[0]!=ident:return actual[0]
            row=self._report_row(ident)
            job=self._queue_report_chunk(row,0)
            self.env['mp.background.report'].sudo().browse(row['id']).write(dict(job_public_id=job))
            self.env.flush_all()
            return ident

    def _report_stage(self,values):
        row=self._report_row(values['run'],lock=True)
        if (row['contract_version']!=CONTRACT or row['state']!='running' or row['cursor']!=values['cursor']
                or not 0<=row['cursor']<row['total']):raise PublicError('CONFLICT')
        items=row['snapshot']
        if not isinstance(items,list) or len(items)!=row['total'] or digest(items)!=row['snapshot_digest']:
            raise ValidationError('Report snapshot changed.')
        chunk=items[row['cursor']:row['cursor']+CHUNK]
        # Snapshot values remain immutable, but current source access still
        # matters. Deleted/foreign source IDs cannot be silently included.
        records=self.browse([item[0] for item in chunk]);records.check_access('read')
        return row,dict(points=[item[1] for item in chunk],cursor=row['cursor'],next_cursor=row['cursor']+len(chunk),
            snapshot_digest=row['snapshot_digest'])

    def _apply_report_chunk(self,values,prepared,computed):
        row,current=self._report_stage(values)
        if current!=prepared or computed['count']!=len(current['points']) or computed['points']!=sum(current['points']):
            raise PublicError('CONFLICT')
        cursor=current['next_cursor'];complete=cursor==row['total']
        updates=dict(cursor=cursor,points=row['points']+computed['points'],
            result_digest=digest([row['result_digest'],computed['digest']]))
        if complete:updates.update(state='completed',snapshot=[])
        else:updates['job_public_id']=self._queue_report_chunk(row,cursor)
        self.env['mp.background.report'].sudo().browse(row['id']).write(updates)
        # The enclosing native run_fenced transaction owns this flush and the
        # successor enqueue. Neither can survive a failed apply on its own.
        self.env.flush_all()
        return computed

    @api.model
    def _report_status(self,ident):
        row=self._report_row(ident)
        self.env.cr.execute('SELECT state,error_code FROM mp_job WHERE public_id=%s AND workspace_id=%s AND actor_id=%s',
            [row['job_public_id'],row['workspace_id'],row['actor_id']])
        found=self.env.cr.fetchone()
        state=row['state']
        if state=='running' and found and found[0] in ('dead_letter','held','outcome_unknown','cancelled'):state='blocked'
        return dict(id=ident,state=state,cursor=row['cursor'],total=row['total'],points=row['points'],
            digest=row['result_digest'],snapshot_digest=row['snapshot_digest'],job=row['job_public_id'],
            job_state=found[0] if found else None,error=found[1] if found else None,contract=row['contract_version'])

    @api.model
    def _cancel_report(self,ident):
        with self.env.cr.savepoint():
            before=self._report_row(ident)
            if before['state']!='running':return False
            # Match worker lock order:job first, application run second. A
            # concurrent advance raises serialization/conflict for a fresh
            # transaction retry instead of cancelling an unseen successor.
            job_dispatch.cancel_scheduled(self._job_env(),before['job_public_id'])
            row=self._report_row(ident,lock=True)
            if row['state']!='running':return False
            if row['job_public_id']!=before['job_public_id']:raise PublicError('CONFLICT')
            self.env['mp.background.report'].sudo().browse(row['id']).write(dict(state='cancelled',snapshot=[]))
            self.env.flush_all()
            return True
