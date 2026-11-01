"""Reviewed continuation of an exact restored target before its first fence.

No creation, dump replay, extraction or authentication overlay occurs here.
Other partial phases remain refused. This is private OS operator authority.
"""
import copy
import hashlib
import json
from pathlib import Path
import tarfile
from uuid import uuid4

from .catalog import Catalog
from .contracts import load_json
from .deployment import _run
from .operator_os import OperatorError,OperationLocks,protect_directory
from .operator_store import _write_new
from .plans import data_digest
from .recovery_reviews import RecoveryReviews


def canonical_dump_digest(raw):
    # pg_dump's random psql restrict token and comments are not database state.
    lines=[line for line in raw.splitlines() if not line.startswith((b'--',b'\\restrict ',b'\\unrestrict '))]
    return 'sha256:'+hashlib.sha256(b'\n'.join(lines)).hexdigest()


FILE_OBSERVATION="""import hashlib,json,pathlib,sys
root=pathlib.Path('/var/lib/modular/filestore')/sys.argv[1]
assert root.is_dir() and not root.is_symlink()
files={}
for p in sorted(root.rglob('*')):
 assert not p.is_symlink()
 if p.is_file():files[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
 elif not p.is_dir():raise ValueError('Unexpected filestore object')
print(json.dumps(files))
"""


class RestoreContinuation:
    def __init__(self,recovery):
        self.recovery=recovery;self.native=recovery.native;self.store=recovery.store

    def state(self,operation):
        r=self.recovery;proposal=r._restore_state(operation)
        directory=self.store.root/'recoveries'/operation
        # Deliberately support only the observed boundary. Existing records and
        # targets cannot be deleted, replaced or guessed from an elapsed lease.
        if set(p.name for p in directory.iterdir())!={'decision.json','filestore.log','filestore.log.stderr.log','dispatch-fence'}:
            raise OperatorError('Partial restore is outside the verified pre-fence continuation boundary')
        old_path=directory/'decision.json';self.store._regular(old_path)
        original=load_json(old_path.read_bytes());old=copy.deepcopy(original['decision']);old.pop('review')
        RecoveryReviews(self.store).check_reserved(original['decision'],exact_hash=original['hash'])
        if old!=proposal or self.store.status(operation)['phase']!='restore_target_created':
            raise OperatorError('Original restore/source authority changed; continuation denied')
        if any(w['running'] for w in proposal['managed_workers']):
            raise OperatorError('All managed workers must remain stopped before continuation')
        fence=directory/'dispatch-fence'
        if set(p.name for p in fence.iterdir())!={'fence-request.json','fence.stdout','fence.stdout.stderr.log'}:
            raise OperatorError('Restored fence may already have run; inspect instead of repeating')
        records={}
        for path in [directory/'filestore.log',directory/'filestore.log.stderr.log',*fence.iterdir()]:
            self.store._regular(path);records[path.relative_to(directory).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
        request=load_json((fence/'fence-request.json').read_bytes())
        manifest=load_json((self.store.root/'checkpoints'/operation/'manifest.json').read_bytes())
        profile=manifest.get('dispatch_profile')
        if (not isinstance(profile,dict) or (fence/'fence.stdout').stat().st_size
                or request['action']!='fence' or request['operation_id']!=operation
                or request['database']!=proposal['fresh_database']
                or request['site_id']!=r.config['sites'][0]['site_id']
                or request['release_digest']!=data_digest(proposal['restored_release_lock'])
                or request['control_release']!=profile['control']['release_digest']
                or request['image_id']!=proposal['restore_configuration']['image_id']):
            raise OperatorError('Exact uncommitted restored dispatch-fence attempt required')
        fresh=proposal['fresh_database'];database=r.observer._container('db')
        clients=_run(['docker','exec','-i',database,'psql','-X','-qAt','-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1'],
            input=("SELECT count(*) FROM pg_stat_activity WHERE datname IN ('"+fresh+"','"+r.config['sites'][0]['database']+"') AND usename<>'postgres';").encode())
        if clients.strip()!=b'0':raise OperatorError('Database clients prevent closed restored-target continuation')
        target=copy.deepcopy(proposal['restore_configuration']);target['sites'][0]['database']=fresh
        helper=r._dispatch_helper(manifest=manifest);observed=helper.require_profile(helper.inspect_current(configuration=target),closed=True)
        ignored={'release_digest','state_digest'}
        if profile['profile']=='r1-reference-stateless-dispatch-v1':
            same=helper.same_restored_dispatch(observed,profile,manifest.get('reference_policy'),checkpoint=True)
            if not same or not isinstance(request.get('reference'),dict):raise OperatorError('Exact private checkpoint reference fence request required')
            # A failed pre-fence attempt must have selected the checkpoint
            # registrations. Current OS publication is independently reread.
            if {k:v for k,v in request['reference'].items() if k!='publication_digest'}!={k:v for k,v in manifest['reference_policy'].items() if k!='publication_digest'}:
                raise OperatorError('Reference fence request changed checkpoint scope')
        else:same={k:v for k,v in observed.items() if k not in ignored}=={k:v for k,v in profile.items() if k not in ignored}
        if not same:
            raise OperatorError('Restored queues differ from the untouched coordinated checkpoint')
        authority,private=r._authority(fresh);current,current_private=r._authority(r.config['sites'][0]['database'])
        if authority!=proposal['authority'] or current!=authority or private!=current_private:
            raise OperatorError('Current native authority overlay differs; continuation denied')
        reader=r._recovery_observer(target,manifest=manifest);catalog=Catalog(self.native.catalog_root,self.native.validator,readonly=True).snapshot()
        state=reader.state(reader.read(quiesced=True,missing_worker=True),catalog)['state'];previous=manifest['previous_release']
        if state['release_lock']!=proposal['restored_release_lock'] or any(state[k]!=previous[k] for k in ['installations','bindings']):
            raise OperatorError('Restored release/metadata differs from reviewed checkpoint')
        args,_=self.native._child(operation,'continuation-observe-'+uuid4().hex,network=False,image_id=target['image_id'])
        files=load_json(_run(args+['-c',FILE_OBSERVATION,fresh]))
        checkpoint=self.store.root/'checkpoints'/operation;expected={};prefix='filestore/'+r.config['sites'][0]['database']+'/'
        with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
            for member in archive:
                if member.isfile() and member.name.startswith(prefix):
                    name=member.name[len(prefix):]
                    if name in expected:raise OperatorError('Duplicate checkpoint filestore member')
                    expected[name]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
        if files!=expected or load_json((directory/'filestore.log').read_bytes()).get('filestore_restored') is not True:
            raise OperatorError('Restored filestore differs from coordinated checkpoint')
        raw=_run(['docker','exec',database,'pg_dump','-U','postgres','--no-owner','--no-privileges',fresh])
        sources=['restore_executor.py','restore_continuation.py','dispatch_operator.py','dispatch_lifecycle.py','dispatch_jobs_maintenance.py']
        if profile['profile']=='r1-reference-stateless-dispatch-v1':sources+=['reference_recovery.py','reference_dispatch.py','worker_operator.py','worker_publication.py']
        proposal['continuation']=dict(phase='restored_before_first_dispatch_fence',original_decision_digest=data_digest(original),
            diagnostics=records,restored_database_digest=canonical_dump_digest(raw),restored_state_digest=data_digest(state),
            dispatch=observed,filestore_digest=data_digest(files),filestore_files=len(files),
            source_sha256={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in sources},
            replay_database_dump=False,reextract_filestore=False,reapply_native_auth=False)
        return proposal

    def execute(self,decision,*,exact_hash,noninteractive=False):
        operation=decision['operation_id'];bundle=self.store.bundle(operation);r=self.recovery
        with OperationLocks(self.store.root/'locks',bundle['plan']['deployment_id'],bundle['plan']['site_ids']) as locks:
            reviews=RecoveryReviews(self.store);reviews.verify(decision,exact_hash=exact_hash,current_payload=self.state(operation))
            if noninteractive and not self.store.policy['allow_noninteractive']:
                raise OperatorError('Noninteractive recovery is not enabled')
            directory=self.store.root/'recoveries'/operation
            attempt=protect_directory(directory/'continuations')/decision['review']['review_id']
            if attempt.exists():raise OperatorError('Continuation already attempted; inspect instead of repeating')
            attempt=protect_directory(attempt);_write_new(attempt/'decision.json',decision)
            self.store.record_restore(operation,locks,code='restore_authorized',details={'decision_hash':exact_hash,
                'fresh_database':decision['fresh_database'],'continuation':'restored_before_first_dispatch_fence'})
            current,private=r._authority(r.config['sites'][0]['database'])
            if current!=decision['authority']:raise OperatorError('Current authority changed before continuation')
            reviews.check_reserved(decision,exact_hash=exact_hash)
            checkpoint=self.store.root/'checkpoints'/operation
            return r._complete_restore(decision,exact_hash=exact_hash,locks=locks,directory=directory,checkpoint=checkpoint,
                manifest=load_json((checkpoint/'manifest.json').read_bytes()),fresh=decision['fresh_database'],
                private_native_auth=private,dispatch_directory=attempt)
