"""Bounded private queue observations. No dispatch or sizing authority."""
from datetime import timezone

MAX_LIVE=100000
MAX_GROUPS=1024


def observe(cr,site,release,routes):
    cr.execute("SET LOCAL statement_timeout='5s'; SET LOCAL lock_timeout='1s'")
    cr.execute("SELECT timezone('UTC',statement_timestamp())")
    now,=cr.fetchone()
    result=dict(protocol=1,site_id=site,release_digest=release,observed_at=now.replace(tzinfo=timezone.utc).isoformat())
    cr.execute('SELECT count(*) FROM (SELECT 1 FROM mp_job WHERE site_id=%s LIMIT %s) bounded',[site,MAX_LIVE+1])
    count,=cr.fetchone()
    result.update(live_rows_observed=count,complete=count<=MAX_LIVE,groups=[])
    if not result['complete']:
        result['reason']='live_table_limit';return result
    cr.execute("""SELECT current_setting('max_connections')::integer,
        count(*),count(*) FILTER (WHERE wait_event_type='Lock'),
        COALESCE(max(extract(epoch FROM clock_timestamp()-query_start)) FILTER (WHERE wait_event_type='Lock'),0)
        FROM pg_stat_activity""")
    maximum,connections,waiting,wait_seconds=cr.fetchone()
    result['database']=dict(max_connections=maximum,connections=connections,lock_waiters=waiting,
        longest_lock_wait_seconds=float(wait_seconds))
    cr.execute("""SELECT handler,handler_version,workspace_id,
        CASE WHEN workspace_id IS NULL THEN 'n:'||lpad(installation_id::text,10,'0')
             ELSE 'w:'||lpad(workspace_id::text,10,'0') END AS partition,release_digest=%s AS current,
        count(*) FILTER (WHERE runnable),count(*) FILTER (WHERE state='running'),
        count(*) FILTER (WHERE state IN ('pending','retry') AND available_at>stamp AND deadline_at>stamp),
        count(*) FILTER (WHERE state IN ('pending','retry') AND deadline_at<=stamp),
        count(*) FILTER (WHERE state='held'),count(*) FILTER (WHERE state='outcome_unknown'),
        count(*) FILTER (WHERE state='retry'),
        COALESCE(max(extract(epoch FROM stamp-available_at)*1000) FILTER (WHERE runnable),0),
        COALESCE(max(extract(epoch FROM stamp-original_at)*1000) FILTER (WHERE runnable),0),
        min(extract(epoch FROM deadline_at-stamp)*1000) FILTER (WHERE runnable),
        count(*) FILTER (WHERE created_at>=stamp-interval '60 seconds' AND created_at<=stamp),
        count(*) FILTER (WHERE state='completed' AND finished_at>=stamp-interval '60 seconds' AND finished_at<=stamp)
        FROM (SELECT j.*,timezone('UTC',statement_timestamp()) AS stamp,
            CASE WHEN payload->>'schema_version'='2' THEN
                (payload->'schedule'->>'run_at')::timestamptz AT TIME ZONE 'UTC' ELSE available_at END AS original_at,
            state IN ('pending','retry') AND NOT cancel_requested AND attempts<max_attempts
                AND available_at<=timezone('UTC',statement_timestamp())
                AND deadline_at>timezone('UTC',statement_timestamp()) AS runnable
            FROM mp_job j WHERE site_id=%s) jobs
        GROUP BY handler,handler_version,workspace_id,partition,current
        ORDER BY handler,handler_version,partition,current LIMIT %s""",[release,site,MAX_GROUPS+1])
    rows=cr.fetchall()
    result['complete']=len(rows)<=MAX_GROUPS
    if not result['complete']:result['reason']='group_limit'
    route_map={route:pool for pool,values in routes.items() for route in values}
    keys=('ready','running','future','expired','held','unknown','retry','retry_wait_ms','original_wait_ms',
          'min_validity_ms','arrivals_60s','completions_60s')
    for handler,version,workspace,partition,current,*counts in rows[:MAX_GROUPS]:
        pool=route_map.get((handler,version)) if current else None
        group=dict(pool=pool,handler=handler,version=version,workspace=workspace,partition=partition,current=current)
        group.update({key:int(value) if value is not None else None for key,value in zip(keys,counts,strict=True)})
        result['groups'].append(group)
    return result
