"""Operator-only reviewed worker authority publication; never imported by HTTP.

Reuse the independent store's OS policy and process locks. Only the resulting
projection is mounted read-only into trusted application/job processes. Keys,
review records and Docker authority do not originate in artifacts or app queues.
"""
import copy
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import time
from uuid import UUID,uuid4
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from .contracts import load_json,validate
from .operator_os import OperatorError,ProcessLock,protect_directory,verify_private_directory,_not_link
from .operator_store import _write_new
from .plans import data_digest


def _uuid(value):
    if str(UUID(value))!=value:raise OperatorError('Canonical worker target required')


def _new_bytes(path,value):
    _not_link(path)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(value);stream.flush();os.fsync(stream.fileno())


def _atomic(path,value):
    _not_link(path)
    temporary=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    _new_bytes(temporary,(json.dumps(value,sort_keys=True,indent=2)+'\n').encode())
    os.replace(temporary,path)


def _private_ip(address):
    ip=ipaddress.IPv4Address(address)
    if str(ip)!=address or ip.is_global or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
        raise OperatorError('Observed internal worker address required')
    return address


def _keypair(private,public):
    if not isinstance(private,bytes) or not isinstance(public,bytes) or max(len(private),len(public))>16384:
        raise OperatorError('Bounded provisioned keypair required')
    key=serialization.load_pem_private_key(private,password=None);verification=serialization.load_pem_public_key(public)
    if not isinstance(key,rsa.RSAPrivateKey) or key.key_size<2048 or not isinstance(verification,rsa.RSAPublicKey) or key.public_key().public_numbers()!=verification.public_numbers():
        raise OperatorError('Matching RSA2048+ keypair required')


class DockerWorkerObservation:
    """Read only the exact operator-configured local Compose reference runtime."""
    def __init__(self, policy):
        if set(policy)!={'project','service','network','public_config_volume','image','destination'}:
            raise OperatorError('Exact operator worker runtime policy required')
        for key in ['project','service','network','public_config_volume']:
            if not isinstance(policy[key],str) or not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]{0,120}',policy[key]):
                raise OperatorError('Structured worker runtime name required')
        if policy['destination']!='http://document-stats:8080' or policy['service']!='document-stats':
            raise OperatorError('Only the explicit local reference destination is supported')
        if not re.fullmatch(r'[a-z0-9][a-z0-9/_.-]*@sha256:[0-9a-f]{64}',policy['image']):
            raise OperatorError('Immutable operator image reference required')
        self.policy=copy.deepcopy(policy)

    @staticmethod
    def _command(args):
        # No Compose mutation, pull, shell interpolation, DNS or remote URL.
        result=subprocess.run(['docker',*args],capture_output=True,timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if result.returncode or len(result.stdout)>1048576:raise OperatorError('Worker observation failed')
        return result.stdout

    def __call__(self,endpoint,public_digest,key_id):
        p=self.policy;digest=p['image'].split('@')[1]
        if endpoint['destination']!=p['destination'] or endpoint['expected_image_digest']!=digest:
            raise OperatorError('Endpoint differs from operator runtime policy')
        ids=self._command(['ps','--no-trunc','-q','--filter','label=com.docker.compose.project='+p['project'],
            '--filter','label=com.docker.compose.service='+p['service']]).decode().split()
        if len(ids)!=1 or not re.fullmatch('[0-9a-f]{64}',ids[0]):raise OperatorError('One exact running worker required')
        ident=ids[0]
        def inspect():
            rows=load_json(self._command(['inspect',ident]))
            if not isinstance(rows,list) or len(rows)!=1:raise OperatorError('Exact worker inspection required')
            return rows[0]
        row=inspect();config=row['Config'];host=row['HostConfig'];state=row['State']
        if (row['Id']!=ident or not state['Running'] or state.get('Health',{}).get('Status')!='healthy'
                or row['Image']!=digest or config['Image']!=p['image'] or config['User']!='10002:10002'
                or config['Entrypoint']!=['/venv/bin/python','-m','services.document_stats.server']
                or config['Cmd']!=['--config','/run/worker/config.json','--host','0.0.0.0','--port','8080']
                or not host['ReadonlyRootfs'] or host['Privileged'] or 'ALL' not in host['CapDrop']
                or host.get('PortBindings') or host.get('NetworkMode') in {'host','none'}):
            raise OperatorError('Worker differs from approved hardened runtime')
        mounts=row['Mounts']
        if len(mounts)!=1 or (mounts[0]['Type'],mounts[0]['Name'],mounts[0]['Destination'],mounts[0]['RW'])!=('volume',p['public_config_volume'],'/run/worker',False):
            raise OperatorError('Worker must mount only its read-only public configuration')
        image=load_json(self._command(['image','inspect',digest]))[0]
        if image['Id']!=digest or p['image'] not in (image.get('RepoDigests') or []):raise OperatorError('Actual immutable worker image differs')
        network=load_json(self._command(['network','inspect',p['network']]))[0]
        networks=row['NetworkSettings']['Networks']
        if not network['Internal'] or set(networks)!={p['network']} or networks[p['network']]['NetworkID']!=network['Id']:
            raise OperatorError('Exact internal worker network required')
        address=_private_ip(networks[p['network']]['IPAddress'])
        if 'document-stats' not in (networks[p['network']].get('Aliases') or []):raise OperatorError('Fixed worker alias required')
        script="import json,hashlib,pathlib;c=json.loads(pathlib.Path('/run/worker/config.json').read_text());print(json.dumps(dict(config=c,public_digest=hashlib.sha256(pathlib.Path('/run/worker/public.pem').read_bytes()).hexdigest())))"
        actual=load_json(self._command(['exec',ident,'/venv/bin/python','-c',script]))
        expected={k:endpoint[k] for k in ['site_id','workspace_id','installation_id']}
        expected.update(public_key_file='/run/worker/public.pem',key_id=key_id,endpoint_generation=endpoint['generation'])
        if actual!={'config':expected,'public_digest':public_digest}:raise OperatorError('Actual worker public key/scope/generation differs')
        after=inspect()
        if (after['State']['StartedAt'],after['RestartCount'],after['Image'],after['NetworkSettings']['Networks'])!=(state['StartedAt'],row['RestartCount'],row['Image'],networks):
            raise OperatorError('Worker changed during observation')
        return dict(runtime_policy=p,container_id=ident,image_digest=digest,network_id=network['Id'],addresses=[address],
            started_at=state['StartedAt'],restart_count=row['RestartCount'],public_digest=public_digest,key_id=key_id,
            scope=expected)


class WorkerAuthorityPublisher:
    """Explicit exact-hash approval with fresh independent observations.

The OS owner may call this directly, just like the independent lifecycle CLI.
Application identities receive neither this store nor its Docker capability.
Publication is an atomic file replacement. A crash after replacement is resolved
by inspecting its durable intent and current projection, never by replaying it.
"""
    def __init__(self,store,deployment_id,site_id,*,sink=None):
        _uuid(deployment_id);_uuid(site_id)
        self.store,self.deployment_id,self.site_id=store,deployment_id,site_id
        self._authorize()
        self.root=protect_directory(store.root/'worker-publications'/deployment_id/site_id)
        self.projection=protect_directory(self.root/'projection')
        self.keys=protect_directory(self.projection/'keys')
        self.records=protect_directory(self.root/'records')
        self.locks=protect_directory(self.root/'locks')
        self.sink=sink

    def _authorize(self):
        policy=self.store._policy()
        if self.site_id not in policy['deployments'].get(self.deployment_id,[]):raise OperatorError('Worker target outside independent operator allowlist')
        return policy

    def _document(self):
        path=self.projection/'authority.json';_not_link(path)
        if not path.exists():return dict(schema_version=1,deployment_id=self.deployment_id,site_id=self.site_id,generation=0,endpoints=[])
        if path.stat().st_size>1048576:raise OperatorError('Worker authority size limit')
        value=load_json(path.read_bytes())
        if set(value)!={'schema_version','deployment_id','site_id','generation','endpoints'} or value['schema_version']!=1 or (value['deployment_id'],value['site_id'])!=(self.deployment_id,self.site_id):
            raise OperatorError('Current worker authority target differs')
        if type(value['generation']) is not int or not 1<=value['generation']<9007199254740991 or not isinstance(value['endpoints'],list) or len(value['endpoints'])>256:
            raise OperatorError('Invalid current publication generation/entries')
        return value

    def provision_keypair(self,private_reference,public_reference,private,public):
        self._authorize()
        for ref in [private_reference,public_reference]:
            if not re.fullmatch('[a-z][a-z0-9_]{0,63}',ref):raise OperatorError('Fixed immutable key reference required')
        if private_reference==public_reference:raise OperatorError('Distinct key references required')
        _keypair(private,public)
        with ProcessLock(self.locks,'publication'):
            for ref,raw in [(private_reference,private),(public_reference,public)]:
                path=self.keys/(ref+'.pem')
                if path.exists():
                    if path.read_bytes()!=raw:raise OperatorError('Immutable key reference already provisioned differently')
                else:_new_bytes(path,raw)

    def _key_digest(self,endpoint):
        path=self.keys/(endpoint['public_key_ref']+'.pem');_not_link(path)
        if not path.is_file() or path.stat().st_size>16384:raise OperatorError('Provisioned public key required')
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _candidate(self,endpoint,key_id,observer):
        validate('endpoint',endpoint)
        if endpoint['site_id']!=self.site_id or endpoint['api_version']!='1.0' or endpoint['allowed_methods']!=['analyze']:
            raise OperatorError('Fixed scoped reference method required')
        if not isinstance(key_id,str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}',key_id):raise OperatorError('Fixed worker key identity required')
        current=self._document();identity=lambda e:tuple(e[k] for k in ['installation_id','workspace_id','endpoint_config'])
        old=[e for e in current['endpoints'] if identity(e['descriptor'])==identity(endpoint)]
        if len(old)>1 or endpoint['generation']!=(old[0]['descriptor']['generation']+1 if old else 1):raise OperatorError('Next endpoint generation required')
        if endpoint['state']=='enabled':
            public_digest=self._key_digest(endpoint)
            # Validate actual provisioned issuer using the unchanged reader on
            # a temporary candidate only at publish, before becoming current.
            observation=observer(endpoint,public_digest,key_id)
            addresses=observation['addresses']
            if not isinstance(addresses,list) or not 1<=len(addresses)<=8 or len(set(addresses))!=len(addresses):raise OperatorError('Bounded observed addresses required')
            for address in addresses:_private_ip(address)
        else:
            if len(old)!=1:raise OperatorError('Only an existing endpoint may be suspended/revoked')
            observation=None;public_digest=None;addresses=old[0]['addresses']
        entry=dict(descriptor=copy.deepcopy(endpoint),addresses=addresses,key_id=key_id)
        entries=[e for e in current['endpoints'] if identity(e['descriptor'])!=identity(endpoint)]+[entry]
        if len(entries)>256:raise OperatorError('Worker endpoint limit')
        document=dict(current,generation=current['generation']+1,endpoints=entries)
        return dict(base_digest=data_digest(current),document=document,observation=observation,public_digest=public_digest)

    def prepare(self,endpoint,key_id,observer):
        policy=self._authorize()
        with ProcessLock(self.locks,'publication'):
            candidate=self._candidate(endpoint,key_id,observer)
            plan=dict(schema_version=1,operation_id=str(uuid4()),deployment_id=self.deployment_id,site_id=self.site_id,
                authorization_generation=policy['authorization_generation'],policy_version=policy['policy_version'],
                projection=copy.deepcopy(self.sink.descriptor) if self.sink else dict(kind='operator-filesystem-v1'),
                created_at=int(time.time()),**candidate)
            _write_new(self.records/(plan['operation_id']+'.plan.json'),plan)
            return dict(plan=plan,plan_hash=data_digest(plan))

    def _material(self,document):
        material={}
        for entry in document['endpoints']:
            endpoint=entry['descriptor'];validate('endpoint',endpoint)
            for key in ['issuer_key_ref','public_key_ref']:
                ref=endpoint[key];source=self.keys/(ref+'.pem');_not_link(source)
                if not source.is_file() or source.stat().st_size>16384:
                    if endpoint['state']=='enabled':raise OperatorError('Existing enabled runtime key material missing')
                    continue
                material[ref+'.pem']=source.read_text()
            if endpoint['state']=='enabled':
                _keypair(*(material[endpoint[k]+'.pem'].encode() for k in ['issuer_key_ref','public_key_ref']))
        return material

    def prepare_bootstrap(self):
        policy=self._authorize()
        if not self.sink:raise OperatorError('Explicit replacement authority projection required')
        with ProcessLock(self.locks,'publication'):
            document=self._document()
            if document['generation']<1:raise OperatorError('Bootstrap requires current independently published authority')
            material=self._material(document)
            plan=dict(schema_version=1,kind='bootstrap',operation_id=str(uuid4()),deployment_id=self.deployment_id,site_id=self.site_id,
                authorization_generation=policy['authorization_generation'],policy_version=policy['policy_version'],created_at=int(time.time()),
                document=document,projection=copy.deepcopy(self.sink.descriptor),volume=self.sink.observe_empty(),
                key_digests={k:hashlib.sha256(v.encode()).hexdigest() for k,v in material.items()})
            _write_new(self.records/(plan['operation_id']+'.plan.json'),plan)
            return dict(plan=plan,plan_hash=data_digest(plan))

    def publish_bootstrap(self,review,*,exact_hash,noninteractive=False):
        policy=self._authorize();plan=review['plan'];_uuid(plan['operation_id'])
        if noninteractive and not policy['allow_noninteractive']:raise OperatorError('Explicit noninteractive operator policy required')
        if review['plan_hash']!=exact_hash or data_digest(plan)!=exact_hash:raise OperatorError('Exact reviewed bootstrap hash required')
        path=self.records/(plan['operation_id']+'.plan.json');_not_link(path)
        if load_json(path.read_bytes())!=plan or plan.get('kind')!='bootstrap':raise OperatorError('Independent bootstrap plan differs')
        if not 0<=int(time.time())-plan['created_at']<=min(policy['maximum_start_lifetime'],900):raise OperatorError('Bootstrap review expired')
        if (plan['authorization_generation'],plan['policy_version'])!=(policy['authorization_generation'],policy['policy_version']):raise OperatorError('Operator authority changed')
        with ProcessLock(self.locks,'publication'):
            intent=self.records/(plan['operation_id']+'.intent.json')
            if intent.exists():raise OperatorError('Bootstrap already attempted; inspect actual projection without replay')
            if not self.sink or self.sink.descriptor!=plan['projection'] or self._document()!=plan['document']:
                raise OperatorError('Current independent authority or projection changed')
            if self.sink.observe_empty()!=plan['volume']:raise OperatorError('Replacement volume changed after review')
            material=self._material(plan['document'])
            if {k:hashlib.sha256(v.encode()).hexdigest() for k,v in material.items()}!=plan['key_digests']:raise OperatorError('Current key material changed after review')
            _write_new(intent,dict(plan_hash=exact_hash,operator=policy['owner_identity'],state='bootstrap_started'))
            self.sink.bootstrap(plan['document'],material,plan['operation_id'])
            _write_new(self.records/(plan['operation_id']+'.result.json'),dict(plan_hash=exact_hash,state='bootstrapped',generation=plan['document']['generation']))
            return dict(operation_id=plan['operation_id'],generation=plan['document']['generation'],state='bootstrapped')

    def publish(self,review,*,exact_hash,observer,noninteractive=False):
        policy=self._authorize()
        if noninteractive and not policy['allow_noninteractive']:raise OperatorError('Explicit noninteractive operator policy required')
        if not isinstance(review,dict) or set(review)!={'plan','plan_hash'} or review['plan_hash']!=exact_hash or data_digest(review['plan'])!=exact_hash:
            raise OperatorError('Exact reviewed worker publication hash required')
        plan=review['plan'];_uuid(plan['operation_id'])
        path=self.records/(plan['operation_id']+'.plan.json');_not_link(path)
        if load_json(path.read_bytes())!=plan:raise OperatorError('Independent prepared worker plan differs')
        if not 0<=int(time.time())-plan['created_at']<=min(policy['maximum_start_lifetime'],900):raise OperatorError('Worker publication review expired')
        if (plan['authorization_generation'],plan['policy_version'])!=(policy['authorization_generation'],policy['policy_version']):raise OperatorError('Operator authority changed')
        if plan['projection']!=(self.sink.descriptor if self.sink else dict(kind='operator-filesystem-v1')):raise OperatorError('Runtime projection target changed')
        with ProcessLock(self.locks,'publication'):
            intent=self.records/(plan['operation_id']+'.intent.json')
            if intent.exists():raise OperatorError('Worker publication already attempted; inspect intent/projection before continuing')
            if data_digest(self._document())!=plan['base_digest']:raise OperatorError('Worker authority changed after review')
            entry=plan['document']['endpoints'][-1];endpoint=entry['descriptor']
            fresh=self._candidate(endpoint,entry['key_id'],observer)
            if any(fresh[k]!=plan[k] for k in fresh):raise OperatorError('Actual worker changed after review')
            if endpoint['state']=='enabled':
                material=[]
                for ref in [endpoint['issuer_key_ref'],endpoint['public_key_ref']]:
                    source=self.keys/(ref+'.pem');_not_link(source)
                    if not source.is_file() or source.stat().st_size>16384:raise OperatorError('Provisioned scoped issuer required')
                    material.append(source.read_bytes())
                _keypair(*material)
            _write_new(intent,dict(plan_hash=exact_hash,operator=policy['owner_identity'],state='publication_started'))
            if self.sink:
                self.sink(self._document(),plan['document'],self._material(plan['document']),plan['operation_id'])
            _atomic(self.projection/'authority.json',plan['document'])
            _write_new(self.records/(plan['operation_id']+'.result.json'),dict(plan_hash=exact_hash,state='published',generation=plan['document']['generation']))
            return dict(operation_id=plan['operation_id'],generation=plan['document']['generation'],state=endpoint['state'])
