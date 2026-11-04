"""Private CLI observation only: never execution authority or a journal outcome."""
from contextlib import contextmanager
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path
import threading
import time
from uuid import UUID,uuid4

from modular_platform.operator_os import ProcessLock,protect_directory,verify_private_directory,_not_link

INTERVAL_SECONDS=5
STALE_SECONDS=20
FIELDS={'schema_version','operation_id','plan_hash','invocation_id','process_id','action','state','started_at','observed_at','elapsed_seconds'}

def _now():return datetime.now(timezone.utc)
def _stamp(value):return value.isoformat()

def read_observation(store,operation,*,now=None):
    """Caller separately obtains authorized journal status; no authority here."""
    bundle=store.bundle(operation)
    directory=store.root/'progress'
    if not directory.exists():return {'state':'not_recorded','stale_after_seconds':STALE_SECONDS}
    verify_private_directory(directory)
    path=directory/(operation+'.json');_not_link(path)
    if not path.exists():return {'state':'not_recorded','stale_after_seconds':STALE_SECONDS}
    try:
        store._regular(path)
        if path.stat().st_size>4096:raise ValueError('size')
        value=json.loads(path.read_bytes())
        if not isinstance(value,dict) or set(value)!=FIELDS or type(value['schema_version']) is not int or value['schema_version']!=1:raise ValueError('shape')
        if value['operation_id']!=operation or value['plan_hash']!=bundle['plan_hash']:raise ValueError('binding')
        if str(UUID(value['invocation_id']))!=value['invocation_id']:raise ValueError('invocation')
        if type(value['process_id']) is not int or value['process_id']<=0:raise ValueError('process')
        if value['action'] not in ('apply','restore','resume','resume-unchanged') or value['state'] not in ('observing','returned','interrupted'):raise ValueError('state')
        if type(value['elapsed_seconds']) not in (int,float) or not math.isfinite(value['elapsed_seconds']) or value['elapsed_seconds']<0:raise ValueError('elapsed')
        started=datetime.fromisoformat(value['started_at']);observed=datetime.fromisoformat(value['observed_at'])
        if not started.tzinfo or not observed.tzinfo or observed<started:raise ValueError('clock')
        age=((now or _now())-observed).total_seconds()
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        return {'state':'unavailable','reason':'invalid_observation','stale_after_seconds':STALE_SECONDS}
    value['observation_state']=value['state']
    value['state']='clock_changed' if age<0 else 'stale' if value['state']=='observing' and age>STALE_SECONDS else value['state']
    value['age_seconds']=round(max(0,age),3);value['stale_after_seconds']=STALE_SECONDS
    value['meaning']='Observation only; use journal for outcome. Stale is not proof of failure or rollback.'
    return value

@contextmanager
def observe_execution(store,operation,action):
    """Observe one supported CLI invocation; executor still acquires its own locks."""
    if str(UUID(operation))!=operation or action not in ('apply','restore','resume','resume-unchanged'):
        raise ValueError('Canonical operation and supported observation action required')
    bundle=store.bundle(operation)
    directory=protect_directory(store.root/'progress')
    with ProcessLock(directory,'observation-'+operation):
        invocation=str(uuid4());path=directory/(operation+'.json');_not_link(path)
        start=_now();tick=time.monotonic();stop=threading.Event();errors=[]
        def pulse(state):
            value=dict(schema_version=1,operation_id=operation,plan_hash=bundle['plan_hash'],invocation_id=invocation,process_id=os.getpid(),action=action,state=state,started_at=_stamp(start),observed_at=_stamp(_now()),elapsed_seconds=round(time.monotonic()-tick,3))
            temporary=directory/(operation+'.'+invocation+'.tmp');_not_link(temporary)
            descriptor=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            try:
                with os.fdopen(descriptor,'w',encoding='utf8') as stream:
                    json.dump(value,stream,sort_keys=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
                _not_link(path);os.replace(temporary,path)
            finally:
                if temporary.exists():temporary.unlink()
        def run():
            while not stop.wait(INTERVAL_SECONDS):
                try:pulse('observing')
                except OSError:
                    # A failed observer becomes stale, never a fabricated outcome.
                    errors.append(True);return
        pulse('observing')
        thread=threading.Thread(target=run,name='operation-observation',daemon=True);thread.start()
        state='interrupted'
        try:
            yield
            state='returned'
        finally:
            # Retain the writer lock until the writer has stopped. Never let a
            # delayed old writer overwrite a later invocation's observation.
            stop.set();thread.join()
            # Preserve the executor's return/exception even if diagnostics fail.
            if not thread.is_alive() and not errors:
                try:pulse(state)
                except OSError:pass
