"""Explicit exact-hash restore into a NEW disposable database, traffic closed.

This first profile has no jobs/outbox/external runtimes. It retains the failed
database and original filestore, rotates sessions/technical credentials, and
reconciles current human revocations before starting the restored registry.
"""
import configparser
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets

from .catalog import Catalog
from .contracts import load_json
from .deployment import DockerObserver, _run
from .operator_os import OperatorError, OperationLocks, current_identity, protect_directory
from .operator_store import _write_new
from .plans import data_digest
from .recovery_reviews import RecoveryReviews
from .workers import snapshots,ensure,wait_ready
from .projection import runtime_inputs


AUTHORITY_SELECT = """SELECT jsonb_build_object(
'principals',COALESCE((SELECT jsonb_agg(jsonb_build_object('principal_id',p.public_id,'state',p.state,'active',u.active)) FROM mp_principal p JOIN res_users u ON u.id=p.user_id),'[]'::jsonb),
'memberships',COALESCE((SELECT jsonb_agg(jsonb_build_object('principal_id',p.public_id,'workspace_id',w.public_id,'state',m.state,'role',m.role)) FROM mp_membership m JOIN mp_principal p ON p.id=m.principal_id JOIN mp_workspace w ON w.id=m.workspace_id),'[]'::jsonb),
'operators',COALESCE((SELECT jsonb_agg(jsonb_build_object('principal_id',p.public_id,'state',o.state)) FROM mp_application_operator o JOIN mp_principal p ON p.id=o.principal_id),'[]'::jsonb),
'api_key_count',(SELECT count(*) FROM res_users_apikeys),
'has_dispatch_tables',to_regclass('mp_job') IS NOT NULL OR to_regclass('mp_outbox') IS NOT NULL);
"""

EFFECTS_SELECT = """SELECT jsonb_build_object(
'job_table',to_regclass('public.mp_job') IS NOT NULL,
'outbox_table',to_regclass('public.mp_outbox') IS NOT NULL,
'api_key_count',(SELECT count(*) FROM res_users_apikeys),
'active_technical_credentials',(SELECT count(*) FROM mp_service_credential WHERE state='active'),
'external_installations',(SELECT count(*) FROM mp_plugin_installation WHERE runtime<>'native'));
"""

EXTRACT_FILESTORE = Path(__file__).with_name('restore_filestore.py').read_text()


def authority_sql(snapshot):
    payload = json.dumps(snapshot).replace("'", "''")
    secret = secrets.token_hex(32)
    return ("CREATE TEMP TABLE restore_authority(payload jsonb); INSERT INTO restore_authority VALUES ('"+payload+"'::jsonb);\n"+"""
UPDATE mp_principal SET state='suspended';
UPDATE mp_principal p SET state=a.state FROM restore_authority r,
 jsonb_to_recordset(r.payload->'principals') AS a(principal_id text,state text,active boolean) WHERE p.public_id=a.principal_id;
UPDATE res_users SET active=false WHERE id IN (SELECT user_id FROM mp_principal);
UPDATE res_users u SET active=a.active FROM mp_principal p,restore_authority r,
 jsonb_to_recordset(r.payload->'principals') AS a(principal_id text,state text,active boolean) WHERE p.public_id=a.principal_id AND u.id=p.user_id;
UPDATE mp_membership SET state='revoked';
UPDATE mp_membership m SET state=a.state,role=a.role FROM mp_principal p,mp_workspace w,restore_authority r,
 jsonb_to_recordset(r.payload->'memberships') AS a(principal_id text,workspace_id text,state text,role text)
 WHERE m.principal_id=p.id AND m.workspace_id=w.id AND p.public_id=a.principal_id AND w.public_id=a.workspace_id;
UPDATE mp_application_operator SET state='revoked';
UPDATE mp_application_operator o SET state=a.state FROM mp_principal p,restore_authority r,
 jsonb_to_recordset(r.payload->'operators') AS a(principal_id text,state text) WHERE o.principal_id=p.id AND p.public_id=a.principal_id;
UPDATE mp_service_credential SET state='revoked';
UPDATE mp_workspace SET policy_generation=policy_generation+1;
"""+"UPDATE ir_config_parameter SET value='"+secret+"' WHERE key='database.secret';\n")


def canonical_authority(value):
    value = copy.deepcopy(value)
    for key in ('principals','memberships','operators'):
        value[key].sort(key=lambda item: (item['principal_id'], item.get('workspace_id','')))
    return value


def recovery_configuration(current,manifest,bundle,replacement=None):
    """Only the checkpoint or exact privately recorded replacement is eligible."""
    base=manifest['configuration']
    expected=dict(base,image_id=bundle['operation_lock'].get('staged_image',{}).get('target_image_id',base['image_id']),
        generation=bundle['operation_lock']['release']['generation'],release_created_at=bundle['plan']['created_at'])
    if 'published_release' in base or replacement is not None and 'published_release' in replacement.get('configuration',{}):
        expected['published_release']=bundle['operation_lock']['release']
    if replacement is not None:
        worker=replacement.get('container_id','')
        expected['worker_id']=worker
        if (not re.fullmatch('[0-9a-f]{64}',worker) or replacement!=
                {'container_id':worker,'configuration':expected,'previous_image_id':base['image_id']}):
            raise OperatorError('Private worker replacement differs from approved target')
    if current!=base and (replacement is None or current!=expected):
        raise OperatorError('Current configuration is neither checkpoint nor exact approved replacement')
    target=copy.deepcopy(base);target.pop('worker_id',None)
    target['generation']=max(current['generation'],base['generation'],bundle['operation_lock']['release']['generation'])+1
    target['release_created_at']=bundle['plan']['created_at']
    lock=copy.deepcopy(manifest['previous_release']['release_lock'])
    lock.update(generation=target['generation'],created_at=target['release_created_at'])
    target['published_release']=copy.deepcopy(lock)
    return target,lock


def restored_release_sql(configuration,lock,operation):
    # All input is fixed/private canonical metadata. Use a JSON record rather
    # than interpolating database identifiers or executable plan fragments.
    values={'mp.release_generation':str(configuration['generation']),
        'mp.release_digest':data_digest(lock),'mp.active_inventory_digest':lock['core_inventory_digest'],
        'mp.last_operation_id':'restore:'+operation}
    payload=json.dumps(values).replace("'","''")
    return ("INSERT INTO ir_config_parameter(key,value,create_uid,write_uid,create_date,write_date) "
        "SELECT key,value,1,1,timezone('UTC',now()),timezone('UTC',now()) FROM jsonb_each_text('"+payload+"'::jsonb) "
        "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,write_date=EXCLUDED.write_date;\n")


class RestoreExecutor:
    def __init__(self, native):
        self.native = native
        self.store, self.config = native.store, native.config
        self.observer = native.observer

    def _supported_effects(self, database):
        container=self.observer._container('db')
        value=load_json(_run(['docker','exec','-i',container,'psql','-X','-qAt','-U','postgres','-d',database,
            '-v','ON_ERROR_STOP=1'],input=EFFECTS_SELECT.encode()))
        flags={'job_table','outbox_table'};counts={'api_key_count','active_technical_credentials','external_installations'}
        if (not isinstance(value,dict) or set(value)!=flags|counts or any(type(value[k]) is not bool for k in flags)
                or any(type(value[k]) is not int or value[k]<0 for k in counts) or any(value.values())):
            raise OperatorError('Restored dispatch/API/technical identities require reconciliation; traffic must remain closed')
        return value

    def _restore_state(self, operation):
        status = self.store.status(operation)
        if status['state'] != 'recovery_required' or status['traffic_resumed']:
            raise OperatorError('Fresh-target recovery is permitted only before traffic resumes')
        bundle = self.store.bundle(operation)
        self.store._authorize_plan(bundle['plan'])
        if len(self.config['sites']) != 1:
            raise OperatorError('Restore profile requires exactly one disposable site')
        checkpoint = self.store.root/'checkpoints'/operation
        manifest = load_json((checkpoint/'manifest.json').read_bytes())
        if manifest['operation_id'] != operation or manifest['plan_hash'] != bundle['plan_hash']:
            raise OperatorError('Checkpoint does not match the exact failed operation')
        replacement=self.store.root/'stages'/operation/'worker-replacement.json'
        if replacement.exists():self.store._regular(replacement)
        target,restored_lock=recovery_configuration(self.config,manifest,bundle,
            load_json(replacement.read_bytes()) if replacement.exists() else None)
        for name, digest in manifest['files'].items():
            if name not in ('database.dump','database.dump.stderr.log','filestore.tar.gz','filestore.tar.gz.stderr.log'):
                raise OperatorError('Unknown checkpoint member')
            if hashlib.sha256((checkpoint/name).read_bytes()).hexdigest() != digest:
                raise OperatorError('Coordinated checkpoint hash mismatch')
        running = _run(['docker','ps','-q','--filter','label=com.modular.operation='+operation]).decode().strip()
        if running:
            raise OperatorError('A maintenance child is still running; reconcile it before recovery')
        edge = self.observer._container('edge',stopped=True)
        if self.native._inspect(edge)['State']['Running']:
            raise OperatorError('Public traffic must remain stopped during recovery')
        database = self.observer._container('db')
        source = self.config['sites'][0]['database']
        authority = canonical_authority(load_json(_run(['docker','exec','-i',database,'psql','-X','-qAt','-U','postgres','-d',source,'-v','ON_ERROR_STOP=1'],input=AUTHORITY_SELECT.encode())))
        if authority['api_key_count'] or authority['has_dispatch_tables']:
            raise OperatorError('Jobs/outbox/API keys require the later effect/credential reconciliation profile')
        workers=snapshots(self.config)
        allowed_images={manifest['configuration']['image_id'],bundle['operation_lock'].get('staged_image',{}).get('target_image_id',self.config['image_id'])}
        if any(worker['running'] and worker['image_id'] not in allowed_images for worker in workers):
            raise OperatorError('Unexpected running worker requires independent reconciliation')
        # No dependence on a bootable/running application, even if native
        # maintenance left pending module states or the new worker crashed.
        observation = DockerObserver(manifest['configuration']).read(quiesced=True,missing_worker=True,uncertain_native=True)
        catalog=Catalog(self.native.catalog_root,self.native.validator,readonly=True).snapshot()
        runtime_inputs(observation['runtime'],catalog)
        if observation['runtime']['inventory_digest']!=restored_lock['core_inventory_digest']:
            raise OperatorError('Retained code inventory differs from checkpoint release')
        if any(item['runtime']!='native' for site in observation['sites'] for item in site['installations']):
            raise OperatorError('External runtime reconciliation is required before restore')
        fresh = 'mp_disposable_r0_r1_restore_'+operation.replace('-','')
        if not re.fullmatch('mp_disposable_r0_r1_[a-z0-9_]{1,100}',fresh) or len(fresh)>63:
            raise OperatorError('Invalid fresh disposable restore database')
        return {'schema_version':1,'action':'restore_to_fresh_database','operation_id':operation,
            'plan_hash':bundle['plan_hash'],'checkpoint_digest':data_digest(manifest),'failed_state_digest':data_digest(observation),
            'configuration':self.config,'base_configuration':manifest['configuration'],
            'restore_configuration':target,'restored_release_lock':restored_lock,'managed_workers':workers,
            'fresh_database':fresh,'authority':authority,'keep_traffic_closed':True,
            'operator_authorization_generation':self.store.policy['authorization_generation']}

    def prepare(self,operation):
        return RecoveryReviews(self.store).issue(self._restore_state(operation))

    def execute(self, decision, *, exact_hash, noninteractive=False):
        operation = decision['operation_id']
        bundle = self.store.bundle(operation)
        with OperationLocks(self.store.root/'locks',bundle['plan']['deployment_id'],bundle['plan']['site_ids']) as locks:
            RecoveryReviews(self.store).verify(decision,exact_hash=exact_hash,current_payload=self._restore_state(operation))
            if noninteractive and not self.store.policy['allow_noninteractive']:
                raise OperatorError('Noninteractive recovery is not enabled by OS operator policy')
            directory = protect_directory(self.store.root/'recoveries')/operation
            if directory.exists():
                raise OperatorError('Restore already attempted; inspect without repeating or deleting targets')
            directory = protect_directory(directory)
            issued = datetime.now(timezone.utc)
            _write_new(directory/'decision.json',{'decision':decision,'hash':exact_hash,'operator_id':current_identity(),
                'started_at':issued.isoformat(),'review_expires_at':decision['review']['expires_at']})
            self.store.record_restore(operation,locks,code='restore_authorized',details={'decision_hash':exact_hash,'fresh_database':decision['fresh_database']})
            database = self.observer._container('db')
            for worker in decision['managed_workers']:
                if worker['running']:
                    _run(['docker','stop','--time','30',worker['container_id']])
                    if self.native._inspect(worker['container_id'])['State']['ExitCode'] != 0:
                        raise OperatorError('Recovery worker drain failed')
            current_authority=canonical_authority(load_json(_run(['docker','exec','-i',database,'psql','-X','-qAt','-U','postgres','-d',self.config['sites'][0]['database'],'-v','ON_ERROR_STOP=1'],input=AUTHORITY_SELECT.encode())))
            if current_authority!=decision['authority']:
                raise OperatorError('Current authority changed while draining; inspect before restoring')
            fresh = decision['fresh_database']
            checkpoint = self.store.root/'checkpoints'/operation
            RecoveryReviews(self.store).check_reserved(decision,exact_hash=exact_hash)
            _run(['docker','exec',database,'createdb','-U','postgres','-O','modular',fresh])
            self.store.record_restore(operation,locks,code='restore_target_created',details={'fresh_database':fresh})
            _run(['docker','exec','-i',database,'pg_restore','-U','postgres','--no-owner','--role=modular','--exit-on-error','-d',fresh],input=(checkpoint/'database.dump').read_bytes())
            args, name = self.native._child(operation,'restore-filestore',writable=True,network=False)
            args.insert(2,'-i')
            self.native._private_command(args+['-c',EXTRACT_FILESTORE,self.config['sites'][0]['database'],fresh],
                directory/'filestore.log',input=(checkpoint/'filestore.tar.gz').read_bytes())
            _run(['docker','exec','-i',database,'psql','-X','-q','-U','postgres','-d',fresh,'-v','ON_ERROR_STOP=1','--single-transaction'],
                input=(authority_sql(decision['authority'])+restored_release_sql(decision['restore_configuration'],decision['restored_release_lock'],operation)).encode())
            # The restored checkpoint may resurrect effects absent in the failed
            # DB. Reject unsupported state before configuration/registry startup.
            self._supported_effects(fresh)
            # Copy the old exact config to the private recovery directory before
            # replacing only its DB target. No secrets enter public evidence.
            args,name = self.native._child(operation,'read-config',network=False)
            old_config = _run(args+['-c',"from pathlib import Path;print(Path('/run/secrets/odoo_config').read_text(),end='')"])
            with (directory/'previous-odoo.conf').open('xb') as stream:stream.write(old_config)
            parser = configparser.ConfigParser();parser.read_string(old_config.decode())
            if parser['options']['db_name'] != self.config['sites'][0]['database'] or parser['options'].getint('max_cron_threads') != 0:
                raise OperatorError('Unexpected configuration/dispatch target')
            parser['options']['db_name'] = fresh;parser['options']['dbfilter'] = '^'+fresh+'$'
            buffer = io.StringIO();parser.write(buffer)
            code = "import pathlib,sys; p=pathlib.Path('/config/odoo_config'); p.write_bytes(sys.stdin.buffer.read()); p.chmod(0o444)"
            args = ['docker','run','--rm','-i','--user','0:0','--network','none','--read-only','--cap-drop','ALL',
                '--mount','type=volume,source='+self.config['project']+'_appconfig,target=/config','--entrypoint','/venv/bin/python',self.config['image_id'],'-c',code]
            # The file is read-only. A new file under the protected parent is
            # atomically replaced, preserving the previous bytes privately.
            args[-1] = "import os,pathlib,sys; p=pathlib.Path('/config/odoo_config'); t=p.with_name('restore-config.tmp'); f=t.open('xb'); f.write(sys.stdin.buffer.read()); f.flush(); os.fsync(f.fileno()); f.close(); t.chmod(0o444); os.replace(t,p)"
            RecoveryReviews(self.store).check_reserved(decision,exact_hash=exact_hash)
            _run(args,input=buffer.getvalue().encode())
            target = copy.deepcopy(decision['restore_configuration']);target['sites'][0]['database'] = fresh
            RecoveryReviews(self.store).check_reserved(decision,exact_hash=exact_hash)
            # Hash/project restored metadata with retained code offline before
            # any ORM startup; never boot the failed new image to restore it.
            observer=DockerObserver(target)
            snapshot=Catalog(self.native.catalog_root,self.native.validator,readonly=True).snapshot()
            restored=observer.state(observer.read(quiesced=True,missing_worker=True),snapshot)['state']
            previous=load_json((checkpoint/'manifest.json').read_bytes())['previous_release']
            if (restored['release_lock']!=decision['restored_release_lock'] or restored['installations']!=previous['installations']
                    or restored['bindings']!=previous['bindings']):
                raise OperatorError('Restored release/installation/bindings differ from reviewed checkpoint')
            app=ensure(target,target['image_id'],operation,inventory_digest=restored['release_lock']['core_inventory_digest'],suffix='restore')
            target['worker_id']=app
            _write_new(directory/'worker-replacement.json',{'configuration':target,'container_id':app})
            temporary = self.native.target_path.with_name(self.native.target_path.name+'.restore-'+operation+'.tmp')
            _write_new(temporary,target);os.replace(temporary,self.native.target_path)
            _run(['docker','start',app])
            wait_ready(app)
            observer = DockerObserver(target)
            running=observer.state(observer.read(),snapshot)['state']
            if running!=restored:raise OperatorError('Restored worker observation differs from verified offline state')
            from .profile_channel import publish_profile
            if observer.read()['runtime'].get('published_release_protocol')==1:
                self.native._prepare_assets(operation, target, restored, observer.read(), directory,
                                            suffix='restored-assets')
                _write_new(directory/'profile-publication.json',publish_profile(observer,
                    Catalog(self.native.catalog_root,self.native.validator,readonly=True)))
            else:
                _write_new(directory/'profile-publication.json',{'state':'deferred_legacy_reader',
                    'reason':'Retained legacy image has no published-release reader; preserve its cache and use the independent CLI until a compatible release is approved.'})
            actual_authority = canonical_authority(load_json(_run(['docker','exec','-i',database,'psql','-X','-qAt','-U','postgres','-d',fresh,'-v','ON_ERROR_STOP=1'],input=AUTHORITY_SELECT.encode())))
            if actual_authority != decision['authority']:
                raise OperatorError('Restored authority differs from current reconciled snapshot')
            self.store.record_restore(operation,locks,code='restore_verified',details={'fresh_database':fresh,'decision_hash':exact_hash,
                'failed_database_retained':True,'traffic_resumed':False,'session_secret_rotated':True,'technical_credentials_revoked':True})
            _write_new(directory/'result.json',{'state':'restored_verified','configuration':target,'state_digest':data_digest(restored),'keep_traffic_closed':True})
            return {'state':'restored_verified','fresh_database':fresh,'failed_database_retained':True,'keep_traffic_closed':True,
                'operation_status':self.store.status(operation)}

    def _resume_state(self, operation):
        status = self.store.status(operation)
        path = self.store.root/'recoveries'/operation/'result.json'
        result = load_json(path.read_bytes())
        self.store._authorize_plan(self.store.bundle(operation)['plan'])
        if status['state']!='revoked' or status['phase']!='restore_verified' or status['traffic_resumed'] or result['configuration']!=self.config:
            raise OperatorError('Only a verified, still-closed restore can resume traffic')
        edge=self.observer._container('edge',stopped=True)
        if self.native._inspect(edge)['State']['Running']:
            raise OperatorError('Restored traffic is already open; reconcile before a resume decision')
        source=self.config['sites'][0]['database']
        effects=self._supported_effects(source)
        database=self.observer._container('db')
        authority=canonical_authority(load_json(_run(['docker','exec','-i',database,'psql','-X','-qAt','-U','postgres',
            '-d',source,'-v','ON_ERROR_STOP=1'],input=AUTHORITY_SELECT.encode())))
        observation = self.observer.read()
        return {'schema_version':1,'action':'resume_verified_restore','operation_id':operation,
            'configuration':self.config,'restored_observation_digest':data_digest(observation),'restore_result_digest':data_digest(result),
            'recovery_profile':'r1-no-dispatch-v1','effects':effects,'authority_digest':data_digest(authority)}

    def prepare_resume(self,operation):
        return RecoveryReviews(self.store).issue(self._resume_state(operation))

    def revoke_review(self,decision,*,exact_hash):
        self.store._authorize_plan(self.store.bundle(decision['operation_id'])['plan'],generation=False)
        RecoveryReviews(self.store).revoke(decision,exact_hash=exact_hash)
        return {'state':'review_revoked','operation_id':decision['operation_id'],'review_id':decision['review']['review_id']}

    def resume(self, decision, *, exact_hash, noninteractive=False):
        operation = decision['operation_id'];bundle = self.store.bundle(operation)
        with OperationLocks(self.store.root/'locks',bundle['plan']['deployment_id'],bundle['plan']['site_ids']) as locks:
            RecoveryReviews(self.store).verify(decision,exact_hash=exact_hash,current_payload=self._resume_state(operation))
            if noninteractive and not self.store.policy['allow_noninteractive']:
                raise OperatorError('Noninteractive recovery is not enabled')
            self.store._authorize_plan(bundle['plan'])
            app = self.observer._container('app')
            probe = "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8069/web/login',timeout=5); assert r.status==200"
            _run(['docker','exec',app,'/venv/bin/python','-c',probe])
            edge = self.observer._container('edge',stopped=True)
            locks.check()
            RecoveryReviews(self.store).check_reserved(decision,exact_hash=exact_hash)
            # Readiness can take time. Reobserve effects/authority/worker state
            # at the last closed-traffic boundary; expiry remains a start deadline.
            payload=copy.deepcopy(decision);payload.pop('review')
            if payload!=self._resume_state(operation):
                raise OperatorError('Recovery target, authority or effects changed before traffic resume')
            self.store.record_restore_resume(operation,locks,decision_hash=exact_hash)
            _run(['docker','start',edge])
            return {'state':'restored_traffic_resumed','operation_id':operation,'original_plan_state':'revoked',
                'fresh_database':self.config['sites'][0]['database']}
