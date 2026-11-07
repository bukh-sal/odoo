"""Private managed selection hint, never an execution or authorization grant."""
from dataclasses import dataclass
import json
import re
from uuid import uuid4

from . import durable


def _key(site,release,pool):
    durable._uuid(site)
    if pool not in ('urgent','bulk') or not isinstance(release,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',release):
        raise durable.QueueError('Known managed pool and exact release required')
    return 'mp.jobs.rotation.'+site+'.'+pool


def _after(raw,release):
    if raw is None:return 0
    if not isinstance(raw,str) or len(raw)>512:raise durable.QueueError('Bounded private rotation hint required')
    try:
        value=json.loads(raw)
        if (not isinstance(value,dict) or set(value)!={'release','workspace','token'} or value['release']!=release
                or type(value['workspace']) is not int or not 0<=value['workspace']<2**31):return 0
        durable._uuid(value['token'])
        return value['workspace']
    except (ValueError,TypeError):return 0


@dataclass(frozen=True)
class Ticket:
    site: str
    release: str
    pool: str
    raw: str | None
    after: int


def read(cr,site,release,pool):
    key=_key(site,release,pool)
    cr.execute('SELECT value FROM ir_config_parameter WHERE key=%s',[key]);found=cr.fetchone()
    raw=found[0] if found else None
    return Ticket(site,release,pool,raw,_after(raw,release))


def reserve(registry,ticket,workspace):
    if not isinstance(ticket,Ticket):raise durable.QueueError('Private selection ticket required')
    key=_key(ticket.site,ticket.release,ticket.pool)
    durable._bounded(workspace,1,2**31-1)
    if ticket.after!=_after(ticket.raw,ticket.release):raise durable.QueueError('Selection ticket changed')
    value=json.dumps(dict(release=ticket.release,workspace=workspace,token=str(uuid4())),sort_keys=True,separators=(',',':'))
    with registry.cursor() as cr:
        # No ORM is used. A stale compare returns no row rather than holding
        # a repeatable-read metadata snapshot through business preparation.
        cr.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
        cr.execute("SET LOCAL statement_timeout='2s'; SET LOCAL lock_timeout='200ms'")
        durable.control(cr,ticket.site,ticket.release)
        cr.execute("SELECT key,value FROM ir_config_parameter WHERE key IN ('mp.site_id','mp.release_digest')")
        if dict(cr.fetchall())!={'mp.site_id':ticket.site,'mp.release_digest':ticket.release}:
            raise durable.DispatchPaused('Managed rotation release changed')
        if ticket.raw is None:
            cr.execute("""INSERT INTO ir_config_parameter(key,value,create_uid,write_uid,create_date,write_date)
                VALUES(%s,%s,1,1,timezone('UTC',now()),timezone('UTC',now()))
                ON CONFLICT(key) DO NOTHING RETURNING value""",[key,value])
        else:
            cr.execute("""UPDATE ir_config_parameter SET value=%s,write_date=timezone('UTC',now())
                WHERE key=%s AND value=%s RETURNING value""",[value,key,ticket.raw])
        changed=cr.fetchone() is not None
        cr.commit()
    return changed
