"""OS-proved inactive checkpoint sources, never a database-name exception.

This extends only the host's live-sharing observation. Retained databases, image
bytes, archives and checkpoint history are not removed or normalized.
"""
import hashlib
import re

from .artifact_removal import validate_removal_sites, validate_sharing_database_inventory
from .checkpoint_recovery_journal import CheckpointRecoveryJournal
from .contracts import load_json
from .deployment import DockerObserver, _run
from .operator_os import OperatorError, verify_private_directory
from .plans import data_digest
from .workers import snapshots


def _read(store,path):
    store._regular(path)
    return load_json(path.read_bytes())


def _candidates(store,configuration,extras):
    root=store.root/'checkpoint-restores'
    if not root.exists():raise OperatorError('Unknown sharing database has no completed recovery ownership')
    verify_private_directory(root);found={}
    for directory in sorted(root.iterdir()):
        verify_private_directory(directory)
        journal=CheckpointRecoveryJournal(store,directory.name);state=journal.status()
        decision=state['binding']['decision'];source=decision['configuration']
        if len(source['sites'])!=1:continue
        database=source['sites'][0]['database']
        if database not in extras:continue
        if (state['phase']!='resumed' or state['pending'] is not None or len(state['completed'])!=10
                or source['project']!=configuration['project'] or source['deployment_id']!=configuration['deployment_id']
                or source['sites'][0]['site_id']!=configuration['sites'][0]['site_id']
                or source['image_id']!=configuration['image_id'] or database in found
                or decision.get('source_effects',{}).get('policy')!='native-checkpoint-effects-v1'):
            raise OperatorError('Retained source needs an unambiguous resumed same-image native recovery')
        replacement=_read(store,store.root/'stages'/state['checkpoint_operation_id']/'worker-replacement.json')
        bundle=store.bundle(state['checkpoint_operation_id'])
        manifest=_read(store,store.root/'checkpoints'/state['checkpoint_operation_id']/'manifest.json')
        result=_read(store,directory/'result.json')
        if (bundle['plan']['operation_type']!='uninstall' or bundle['plan']['destructive'] is not True
                or any(p['runtime']!='native' for p in bundle['operation_lock']['release']['plugins'])
                or source!=replacement['configuration'] or source['published_release']!=bundle['operation_lock']['release']
                or data_digest(manifest)!=decision['checkpoint_digest']
                or manifest.get('reference_policy') is not None or manifest.get('recurrence_policy') is not None
                or (manifest.get('dispatch_profile') or {}).get('profile')!='r1-native-dispatch-v1'
                or data_digest(result)!=state['completed'][7]['completion']['details']['result_digest']
                or result['configuration']['sites'][0]['database']!=decision['fresh_database']
                or result.get('original_operation_state')!='completed'):
            raise OperatorError('Retained source configuration, checkpoint or verified result changed')
        if set(manifest['files'])!={'database.dump','database.dump.stderr.log','filestore.tar.gz','filestore.tar.gz.stderr.log'}:
            raise OperatorError('Exact retained checkpoint members required')
        for name,digest in manifest['files'].items():
            path=store.root/'checkpoints'/state['checkpoint_operation_id']/name;store._regular(path)
            if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                raise OperatorError('Retained source checkpoint bytes changed')
        found[database]=(source,state,result)
    if set(found)!=extras:
        raise OperatorError('Unknown sharing database lacks exact retained source ownership')
    return found


def _closed_sources(observer,candidates):
    configuration=observer.config
    if any(w['running'] and w['container_id']!=configuration.get('worker_id') for w in snapshots(configuration)):
        raise OperatorError('A noncurrent managed worker prevents retained-source reconciliation')
    for source,state,result in candidates.values():
        worker=source.get('worker_id','')
        if not re.fullmatch('[0-9a-f]{64}',worker):raise OperatorError('Exact retained source worker required')
        info=load_json(_run(['docker','inspect',worker]))[0];labels=info['Config'].get('Labels',{})
        if (info['Id']!=worker or info['Image']!=source['image_id'] or info['State']['Running']
                or info['State']['ExitCode']!=0 or labels.get('com.docker.compose.project')!=configuration['project']
                or labels.get('com.docker.compose.service')!='app'
                or labels.get('com.modular.release_operation')!=state['checkpoint_operation_id']):
            raise OperatorError('Retained source worker is not the exact stopped completed replacement')
        for operation in (state['recovery_id'],state['checkpoint_operation_id']):
            if _run(['docker','ps','-q','--filter','label=com.modular.operation='+operation]).strip():
                raise OperatorError('Live retained-source maintenance prevents removal')
    databases=sorted(candidates)
    if any(not re.fullmatch('mp_disposable_r0_r1_[a-z0-9_]+',name) for name in databases):
        raise OperatorError('Exact disposable retained database identities required')
    query="SELECT count(*) FROM pg_stat_activity WHERE datname IN ("+','.join("'"+name+"'" for name in databases)+");"
    if _run(['docker','exec','-i',observer._container('db'),'psql','-X','-qAt','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1'],input=query.encode()).strip()!=b'0':
        raise OperatorError('Retained source clients prevent removal')


def reconcile_retained_sources(store,observer,observation,inventory):
    configuration=observer.config
    configured={row['database'] for row in configuration['sites']}|{'postgres'}
    if (not isinstance(inventory,dict) or set(inventory)!={'databases','maintenance_relations'}
            or not isinstance(inventory['databases'],list) or any(not isinstance(name,str) for name in inventory['databases'])
            or len(set(inventory['databases']))!=len(inventory['databases'])
            or inventory['maintenance_relations']!=[] or not configured<=set(inventory['databases'])):
        raise OperatorError('Exact complete database and empty maintenance inventory required')
    extras=set(inventory['databases'])-configured
    if not extras:return inventory,[]
    if len(configuration['sites'])!=1 or not observation['runtime']['inventory'].get('artifacts'):
        raise OperatorError('Retained sources require the known single-site native package profile')
    policy=store._policy()
    if configuration['sites'][0]['site_id'] not in policy['deployments'].get(configuration['deployment_id'],[]):
        raise OperatorError('Independent store does not authorize this retained-source deployment')
    candidates=_candidates(store,configuration,extras);_closed_sources(observer,candidates)
    plugins=sorted(observation['runtime']['inventory']['artifacts']);proofs=[]
    for database,(source,state,result) in sorted(candidates.items()):
        retired=DockerObserver(source).read(quiesced=True)
        site=retired['sites'][0]
        if (retired['image_id']!=configuration['image_id'] or site['release_digest']!=data_digest(source['published_release'])
                or str(site['release_generation'])!=str(source['published_release']['generation'])
                or site['active_inventory_digest']!=source['published_release']['core_inventory_digest']):
            raise OperatorError('Retained source published release differs from completed history')
        validate_removal_sites({'state':{'site_ids':[source['sites'][0]['site_id']]}},retired['sites'],plugins,observation['runtime'])
        proofs.append(dict(database=database,recovery_id=state['recovery_id'],checkpoint_operation_id=state['checkpoint_operation_id'],
            journal_digest=state['chain_digest'],source_configuration_digest=data_digest(source),result_digest=data_digest(result),
            observed_site_digest=data_digest(site),image_id=retired['image_id'],worker_id=source['worker_id']))
    if data_digest(_candidates(store,configuration,extras))!=data_digest(candidates):
        raise OperatorError('Retained recovery history changed during observation')
    for proof in proofs:
        current=DockerObserver(candidates[proof['database']][0]).read(quiesced=True)
        if data_digest(current['sites'][0])!=proof['observed_site_digest']:
            raise OperatorError('Retained source metadata changed during observation')
    query="""BEGIN READ ONLY; SET LOCAL statement_timeout='5s';
SELECT jsonb_build_object('databases',(SELECT jsonb_agg(datname ORDER BY datname) FROM pg_database WHERE NOT datistemplate),
'maintenance_relations',COALESCE((SELECT jsonb_agg(c.relname ORDER BY c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f','S')),'[]'::jsonb)); ROLLBACK;"""
    latest=load_json(_run(['docker','exec','-i',observer._container('db'),'psql','-X','-qAt','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1'],input=query.encode()))
    if latest!=inventory:raise OperatorError('Sharing database inventory changed during observation')
    _closed_sources(observer,candidates)
    # Keep the original strict validator, including its configuration/site checks.
    live=dict(databases=sorted(configured),maintenance_relations=inventory['maintenance_relations'])
    validate_sharing_database_inventory(configuration,observation,live)
    return live,proofs
