"""Read the independently published, read-only application worker authority.

The privileged publisher owns this directory. JSON shape validation does not
constitute approval or image attestation; deployment must establish ownership,
read-only mounts and the independently reviewed publication. Never use a path
from an artifact, HTTP request, app queue or stored job payload.
"""
import copy
import hashlib
from dataclasses import dataclass
import ipaddress
import os
from pathlib import Path
import re
from uuid import UUID
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from .contracts import load_json, validate
from .operator_os import _not_link


class AuthorityUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class WorkerAuthoritySnapshot:
    publication_generation: int
    endpoint: dict
    egress: dict
    key_id: str
    public_key_digest: str


class PublishedWorkerAuthority:
    def __init__(self, root, *, deployment_id, site_id):
        self.root=Path(root)
        if not self.root.is_absolute():raise AuthorityUnavailable('Absolute host-owned authority directory required')
        for value in [deployment_id,site_id]:
            if str(UUID(value))!=value:raise AuthorityUnavailable('Canonical authority target required')
        self.deployment_id,self.site_id=deployment_id,site_id

    def _read(self, path, limit):
        try:
            _not_link(path)
            with path.open('rb') as stream:
                if os.fstat(stream.fileno()).st_size>limit:raise AuthorityUnavailable('Authority size limit')
                value=stream.read(limit+1)
            if len(value)>limit:raise AuthorityUnavailable('Authority size limit')
            return value
        except (OSError,ValueError):raise AuthorityUnavailable('Host worker authority unavailable') from None

    def select(self, *, installation_id, workspace_id, endpoint_config):
        try:
            document=load_json(self._read(self.root/'authority.json',1048576))
            if not isinstance(document,dict) or set(document)!={'schema_version','deployment_id','site_id','generation','endpoints'}:
                raise ValueError()
            if type(document['schema_version']) is not int or document['schema_version']!=1 or (document['deployment_id'],document['site_id'])!=(self.deployment_id,self.site_id):raise ValueError()
            generation=document['generation']
            if type(generation) is not int or not 1<=generation<=9007199254740991:raise ValueError()
            entries=document['endpoints']
            if not isinstance(entries,list) or len(entries)>256:raise ValueError()
            selected=[];seen=set()
            for entry in entries:
                if not isinstance(entry,dict) or set(entry)!={'descriptor','addresses','key_id'}:raise ValueError()
                endpoint=entry['descriptor'];validate('endpoint',endpoint)
                if endpoint['site_id']!=self.site_id:raise ValueError()
                identity=(endpoint['installation_id'],endpoint['workspace_id'],endpoint['endpoint_config'])
                if identity in seen:raise ValueError()
                seen.add(identity)
                if not isinstance(entry['key_id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',entry['key_id']):raise ValueError()
                addresses=entry['addresses']
                if not isinstance(addresses,list) or not 1<=len(addresses)<=8 or len(set(addresses))!=len(addresses):raise ValueError()
                for address in addresses:
                    ip=ipaddress.IPv4Address(address)
                    if str(ip)!=address or ip.is_global or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:raise ValueError()
                if identity==(installation_id,workspace_id,endpoint_config):selected.append(entry)
            if len(selected)!=1:raise ValueError()
            entry=selected[0];endpoint=entry['descriptor']
            if endpoint['state']!='enabled':raise ValueError()
            policy={key:endpoint[key] for key in ['destination','expected_image_digest','generation','site_id','workspace_id','installation_id']}
            policy['addresses']=entry['addresses']
            verification=self._read(self.root/'keys'/(endpoint['public_key_ref']+'.pem'),16384)
            return WorkerAuthoritySnapshot(generation,copy.deepcopy(endpoint),{endpoint_config:copy.deepcopy(policy)},entry['key_id'],hashlib.sha256(verification).hexdigest())
        except (ValueError,TypeError,KeyError):raise AuthorityUnavailable('Current approved worker endpoint unavailable') from None

    def _current(self, snapshot):
        endpoint=snapshot.endpoint
        return self.select(**{key:endpoint[key] for key in ['installation_id','workspace_id','endpoint_config']})

    def issuer(self, snapshot, reference):
        try:
            if self._current(snapshot)!=snapshot or reference!=snapshot.endpoint['issuer_key_ref']:raise ValueError()
            # Frozen endpoint validation restricts references to simple names.
            private=self._read(self.root/'keys'/(reference+'.pem'),16384)
            public=self._read(self.root/'keys'/(snapshot.endpoint['public_key_ref']+'.pem'),16384)
            key=serialization.load_pem_private_key(private,password=None)
            verification=serialization.load_pem_public_key(public)
            if not isinstance(key,rsa.RSAPrivateKey) or key.key_size<2048 or not isinstance(verification,rsa.RSAPublicKey) or key.public_key().public_numbers()!=verification.public_numbers():raise ValueError()
            if self._current(snapshot)!=snapshot:raise ValueError()
            return snapshot.key_id,private
        except (ValueError,TypeError,KeyError):raise AuthorityUnavailable('Current scoped worker issuer unavailable') from None
