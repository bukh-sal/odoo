"""Pure read-only capacity advice; untrusted observations never grant actions."""
from datetime import datetime,timezone
import math


class CapacityError(ValueError):pass


def number(value,low,high):
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
        raise CapacityError('Finite bounded capacity value required')
    return value


def instant(value):
    try:parsed=datetime.fromisoformat(value)
    except (ValueError,TypeError):raise CapacityError('Timezone-aware observation time required') from None
    if parsed.utcoffset() is None:raise CapacityError('Timezone-aware observation time required')
    return parsed.astimezone(timezone.utc)


def advise(observation,policy,*,now=None,expected_pins=None):
    """Hold on unknown headroom; never turn this report into an approval."""
    now=now or datetime.now(timezone.utc)
    if (observation.get('protocol')!=1 or policy.get('protocol')!=1
            or set(policy)!={'protocol','maximum_age_seconds','startup_seconds','drain_seconds','pools','handlers','headroom'}
            or set(policy['pools'])!={'urgent','bulk'}):raise CapacityError('Known exact capacity policy required')
    age=(now-instant(observation['observed_at'])).total_seconds()
    maximum_age=number(policy['maximum_age_seconds'],1,300)
    startup=number(policy['startup_seconds'],0,120)
    window=number(policy['drain_seconds'],1,3600)
    reasons=[]
    if age<0 or age>maximum_age:reasons.append('stale_or_future_observation')
    if not observation.get('complete'):reasons.append('incomplete_queue_observation')
    if expected_pins is not None and observation.get('pins')!=expected_pins:reasons.append('release_or_resource_pins_changed')
    if observation.get('dispatch')!='enabled':reasons.append('dispatch_not_enabled')
    if observation.get('fleet_state')!='ready':reasons.append('fleet_not_ready')
    health=observation.get('health')
    limits=policy['headroom']
    if set(limits)!={'web_p95_ms','db_cpu_fraction','connection_fraction','lock_wait_seconds'}:
        raise CapacityError('Exact headroom limits required')
    for key,high in [('web_p95_ms',60000),('db_cpu_fraction',1),('connection_fraction',1),('lock_wait_seconds',3600)]:
        number(limits[key],0,high)
    if not isinstance(health,dict):reasons.append('missing_headroom')
    else:
        health_age=(now-instant(health['observed_at'])).total_seconds()
        if health_age<0 or health_age>maximum_age:reasons.append('stale_or_future_headroom')
        for key in ('web_p95_ms','db_cpu_fraction','lock_wait_seconds'):
            if key not in health:reasons.append('missing_'+key)
            elif number(health[key],0,3600000)>limits[key]:reasons.append('headroom_'+key)
    database=observation.get('database')
    if not isinstance(database,dict):
        reasons.append('missing_database_health')
        database=dict(max_connections=1,connections=1)
    maximum=number(database.get('max_connections'),1,1000000)
    used=number(database.get('connections'),0,maximum)
    connection_limit=math.floor(maximum*limits['connection_fraction'])
    if used>connection_limit:reasons.append('headroom_connections')
    if number(database.get('longest_lock_wait_seconds',0),0,1e9)>limits['lock_wait_seconds']:
        reasons.append('headroom_database_lock_wait')
    producer=observation.get('producer_lanes',0)
    if type(producer) is not int or producer not in (0,1):raise CapacityError('Bounded producer count required')
    groups=observation.get('groups',[])
    if not isinstance(groups,list) or len(groups)>1024:raise CapacityError('Bounded queue groups required')
    samples=observation.get('samples',[])
    if not isinstance(samples,list) or len(samples)>16000:raise CapacityError('Bounded runtime samples required')
    estimates={}
    if not isinstance(policy['handlers'],dict) or len(policy['handlers'])>200:raise CapacityError('Bounded handler defaults required')
    for key,value in policy['handlers'].items():
        if set(value)!={'pool','default_seconds','arrival_per_second'} or value['pool'] not in ('urgent','bulk'):
            raise CapacityError('Exact handler forecast required')
        default=number(value['default_seconds'],.001,3600)
        arrival=number(value['arrival_per_second'],0,10000)
        observed=[]
        for sample in samples:
            if sample['handler_version']!=key:continue
            sample_age=(now-instant(sample['at'])).total_seconds()
            if 0<=sample_age<=900:
                observed.append(number(sample['worker_seconds'],0,7200))
        p95=sorted(observed)[math.ceil(len(observed)*.95)-1] if observed else None
        estimates[key]=dict(pool=value['pool'],seconds=max(default,p95 or 0),samples=len(observed),
            fallback=len(observed)<20,arrival_per_second=arrival)
    pools={}
    minimums={}
    for pool in ('urgent','bulk'):
        spec=policy['pools'][pool]
        if set(spec)!={'minimum','maximum','start_target_seconds'}:raise CapacityError('Exact pool bounds required')
        if (type(spec['minimum']) is not int or type(spec['maximum']) is not int
                or not 1<=spec['minimum']<=spec['maximum']<=8):raise CapacityError('Warm bounded pools required')
        minimums[pool]=spec['minimum']
        number(spec['start_target_seconds'],.001,3600)
    if sum(minimums.values())+producer>8:raise CapacityError('Pool minima exceed eight-role site limit')
    if sum(spec['maximum'] for spec in policy['pools'].values())+producer>8:
        raise CapacityError('Pool maxima exceed eight-role site limit')
    spare_connections=max(0,(connection_limit-int(used))//3)
    for pool in ('urgent','bulk'):
        spec=policy['pools'][pool]
        work={};ready=0;oldest=0;validity=None;forecasts={};unresolved=[]
        for group in groups:
            if group['pool']!=pool or not group['current']:continue
            queued=number(group['ready'],0,100000);running=number(group['running'],0,8)
            key=group['handler']+':'+str(group['version'])
            estimate=estimates.get(key)
            if estimate and estimate['pool']!=pool:raise CapacityError('Handler pool changed')
            if estimate is None:
                if queued or running:unresolved.append(key)
                continue
            ready+=queued;oldest=max(oldest,number(group['original_wait_ms'],0,1e15)/1000)
            workspace=str(group['workspace'])
            if queued or running:work[workspace]=work.get(workspace,0)+(queued+running)*estimate['seconds']
            forecasts.setdefault(key,set()).add(workspace)
            if group['min_validity_ms'] is not None:
                value=number(group['min_validity_ms'],0,86400000)/1000
                validity=value if validity is None else min(validity,value)
        if unresolved:reasons.append('missing_handler_estimate:'+pool)
        if any(estimate['pool']==pool and estimate['arrival_per_second'] and key not in forecasts
               for key,estimate in estimates.items()):reasons.append('unallocated_arrival_forecast:'+pool)
        for key,workspaces in forecasts.items():
            arrival=estimates[key]['arrival_per_second']*window*estimates[key]['seconds']
            for workspace in workspaces:
                if arrival:work[workspace]=work.get(workspace,0)+arrival/len(workspaces)
        total=sum(work.values());usable=window-startup
        needed=max(spec['minimum'],math.ceil(total/usable)) if usable>0 else spec['maximum']+1
        slot_limit=max(spec['minimum'],len(work))
        other_min=sum(value for name,value in minimums.items() if name!=pool)
        role_limit=8-producer-other_min
        current=number(observation.get('ready_lanes',{}).get(pool,0),0,8)
        # Dedicated slot + work + heartbeat sessions budget three per new lane.
        connection_cap=int(current)+spare_connections
        cap=min(spec['maximum'],role_limit,slot_limit,connection_cap)
        constraints=[]
        if needed>cap:constraints.append('lane_or_connection_limit')
        if work and max(work.values())>max(0,usable):constraints.append('workspace_serial_limit')
        if usable<=0:constraints.append('startup_exceeds_drain_window')
        if ready and startup>=max(0,spec['start_target_seconds']-oldest):constraints.append('reactive_start_too_late')
        if validity is not None and startup>=validity:constraints.append('reactive_start_after_expiry')
        proposed=min(needed,cap)
        spare_connections-=max(0,proposed-int(current))
        if cap<spec['minimum']:constraints.append('insufficient_warm_capacity')
        predicted=max(total/max(1,proposed),max(work.values(),default=0))+startup
        pools[pool]=dict(ready=ready,worker_seconds=round(total,3),workspace_slots=len(work),
            needed_lanes=needed,advised_lanes=proposed,predicted_drain_seconds=round(predicted,3),
            oldest_original_wait_seconds=oldest,constraints=constraints,
            current_ready_lanes=current,startup_seconds=startup)
    if reasons:
        for value in pools.values():
            value['estimated_lanes']=value['advised_lanes'];value['advised_lanes']=None
    return dict(protocol=1,action='advice_only',state='hold' if reasons else 'advised',
        reasons=sorted(set(reasons)),pools=pools,estimates=estimates,observation_age_seconds=age,
        mutation_authorized=False)
