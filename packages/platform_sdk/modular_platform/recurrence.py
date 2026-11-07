"""Private fixed-UTC recurrence contract. No producer or authority in this module."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .durable import QueueError, _bounded, _uuid


def _utc(value, *, aligned=False):
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise QueueError('An aware UTC recurrence instant is required')
    value=value.astimezone(timezone.utc)
    if aligned and value.microsecond:
        raise QueueError('Recurrence anchors and cursors use whole UTC seconds')
    return value


@dataclass(frozen=True)
class RecurrenceRule:
    anchor_at: datetime
    interval_seconds: int
    validity_seconds: int
    attempt_seconds: int
    missed: str = 'coalesce_latest'
    grace_seconds: int = 5

    def __post_init__(self):
        object.__setattr__(self,'anchor_at',_utc(self.anchor_at,aligned=True))
        _bounded(self.interval_seconds,1,366*86400)
        _bounded(self.validity_seconds,1,86400)
        _bounded(self.attempt_seconds,1,3600)
        _bounded(self.grace_seconds,0,86400)
        if not isinstance(self.missed,str) or self.missed not in {'skip','coalesce_latest'}:
            raise QueueError('Explicit bounded missed-occurrence policy required')

    def wire(self):
        return dict(protocol=1,anchor_at=self.anchor_at.isoformat().replace('+00:00','Z'),
            interval_seconds=self.interval_seconds,validity_seconds=self.validity_seconds,
            attempt_seconds=self.attempt_seconds,missed=self.missed,grace_seconds=self.grace_seconds)

    @classmethod
    def from_wire(cls,value):
        keys={'protocol','anchor_at','interval_seconds','validity_seconds','attempt_seconds','missed','grace_seconds'}
        if not isinstance(value,dict) or set(value)!=keys or type(value['protocol']) is not int or value['protocol']!=1:
            raise QueueError('Versioned recurrence rule required')
        try:
            raw=value['anchor_at']
            rule=cls(datetime.fromisoformat(raw),**{key:item for key,item in value.items() if key not in {'protocol','anchor_at'}})
        except (ValueError,TypeError,OverflowError):
            raise QueueError('Invalid recurrence rule') from None
        if rule.wire()!=value:
            raise QueueError('Canonical UTC recurrence rule required')
        return rule


@dataclass(frozen=True)
class Selection:
    nominal_at: datetime | None
    next_at: datetime
    skipped: int


def cursor_after(rule,considered_at):
    """First instant on a new grid strictly after a durable high-water mark."""
    if not isinstance(rule,RecurrenceRule):raise QueueError('Typed recurrence rule required')
    considered_at=_utc(considered_at)
    if considered_at<rule.anchor_at:return rule.anchor_at
    steps=(considered_at-rule.anchor_at)//timedelta(seconds=rule.interval_seconds)+1
    try:return rule.anchor_at+timedelta(seconds=steps*rule.interval_seconds)
    except OverflowError:raise QueueError('Recurrence date range exhausted') from None


def select(rule,cursor,now):
    """Consider missed intervals once; caller commits cursor with enqueue/receipt."""
    if not isinstance(rule,RecurrenceRule):raise QueueError('Typed recurrence rule required')
    cursor=_utc(cursor,aligned=True);now=_utc(now)
    step=timedelta(seconds=rule.interval_seconds)
    if cursor<rule.anchor_at or (cursor-rule.anchor_at)%step:
        raise QueueError('Cursor is outside the recurrence grid')
    if now<cursor:return Selection(None,cursor,0)
    intervals=(now-cursor)//step
    nominal=cursor+intervals*step if rule.missed=='coalesce_latest' else cursor
    valid=(now-nominal).total_seconds()<rule.validity_seconds
    if rule.missed=='skip':
        valid=valid and intervals==0 and (now-cursor).total_seconds()<=rule.grace_seconds
    try:future=cursor+(intervals+1)*step
    except OverflowError:raise QueueError('Recurrence date range exhausted') from None
    return Selection(nominal if valid else None,future,intervals+1-int(valid))


def occurrence_key(schedule_id,nominal_at):
    _uuid(schedule_id)
    nominal_at=_utc(nominal_at,aligned=True)
    return 'rec:'+schedule_id+':'+nominal_at.isoformat().replace('+00:00','Z')
