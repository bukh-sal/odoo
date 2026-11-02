"""Data-only manager observations; never an independent approval or catalog."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import tempfile

from packaging.specifiers import SpecifierSet

from .artifacts import ArchiveLimits, ArtifactValidator, TrustPolicy, ArtifactError
from .contracts import ContractError, native_version, package_version, validate
from .plans import data_digest

UPLOAD_LIMIT=ArchiveLimits().compressed

def observed(profile,now):
    age=(datetime.fromisoformat(now.replace('Z','+00:00'))-datetime.fromisoformat(profile['observed_at'].replace('Z','+00:00'))).total_seconds()
    return {'schema_version':1,'observed_at':now,'profile_observed_at':profile['observed_at'],
            'stale':age>900 or age<0,'control_authority':'independent_local_os'}

def page_offset(value):
    if not isinstance(value,str) or not value.isascii() or not value.isdigit() or not 0<=int(value)<=10000:
        raise ContractError('Invalid manager page offset')
    return int(value)

def artifact_summary(descriptor):
    manifest=descriptor['manifest'];info=manifest['plugin'];trust=descriptor['trust']
    return {'plugin_id':info['id'],'version':info['version'],'artifact_digest':descriptor['digest'],
            'name':info['name'],'description':info['description'],'publisher':info['publisher'],'license':info['license'],
            'runtime':manifest['runtime']['kind'],'trust_model':trust['model'],'signature_verified':False,
            'warnings':trust['warnings'],'policy_generation':trust['policy_generation']}

def exact_artifact(profile,digest):
    if not isinstance(digest,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',digest):
        raise ContractError('Exact artifact digest required')
    matches=[item for item in profile['catalog'] if item['digest']==digest]
    if len(matches)>1:raise ContractError('Ambiguous catalog artifact')
    return matches[0] if matches else None

def details_view(profile,digest,*,now):
    artifact=exact_artifact(profile,digest)
    if artifact is None:return None
    provenance=artifact['provenance'];upstream=provenance.get('upstream_commit')
    if not isinstance(upstream,str) or not 1<=len(upstream)<=200:upstream=None
    return validate('manager-view',observed(profile,now)|{'kind':'plugin_details','artifact':artifact_summary(artifact),
        'manifest':artifact['manifest'],'native_trusted_code':artifact['manifest']['runtime']['kind']=='native',
        'feature_suspension_unloads_code':False,'provenance':{'builder':provenance['builder'],
        'source_files_count':len(provenance['source_files']),'source_inventory_digest':data_digest(provenance['source_files']),
        'provenance_digest':data_digest(provenance),'upstream_commit':upstream,'publisher_identity_verified':False}})

def _external_health(row,metadata,external_state,workspaces=None):
    if row['metadata_state']=='removed':
        return {'state':'unknown','reason':'Metadata is unregistered; the external runtime remains separately managed.'}
    if row['metadata_state']!='installed':
        return {'state':'unknown','reason':'Installed metadata must be verified before reporting external service health.'}
    if external_state is None:
        return {'state':'unknown','reason':'No published external service observation is available.'}
    from .projection import external_observation
    external=external_observation(external_state)
    if workspaces is None:
        workspaces=[f['workspace_id'] for f in metadata['features'] if f['installation_id']==row['installation_id']]
    expected=row['manifest']['external_service']['expected_image'].split('@')[1]
    for workspace in workspaces:
        endpoints=[e for e in external['endpoints'] if e['site_id']==metadata['site_id'] and e['workspace_id']==workspace and e['installation_id']==row['installation_id']]
        health=external['service_health'].get(row['installation_id']+':'+workspace,{})
        if (len(endpoints)!=1 or endpoints[0]['state']!='enabled' or endpoints[0]['expected_image_digest']!=expected
                or health.get('state')!='healthy' or health.get('expected_image_digest')!=expected):
            return {'state':'degraded','reason':'Published endpoint approval, image or service health needs attention; the runtime is separately managed.'}
    return {'state':'healthy' if workspaces else 'unknown','reason':'Published scoped endpoint and service health observed; workspace availability is separate.'}


def _dependencies(row,manifest,metadata,external_state=None):
    installations={item['plugin_id']:item for item in metadata['installations'] if item['metadata_state']!='removed'}
    modules={item['addon']:item for item in metadata['native_modules']};features=metadata['features'];issues=[]
    def available(provider,workspace):
        enabled=any(f['installation_id']==provider['installation_id'] and f['workspace_id']==workspace and f['feature_state']=='enabled' for f in features)
        if provider['runtime']=='external_service':
            return provider['metadata_state']=='installed' and enabled and _external_health(provider,metadata,external_state,[workspace])['state']=='healthy'
        native=modules.get(provider['manifest']['runtime'].get('addon_name'))
        return (provider['metadata_state']=='installed' and native is not None and native['state']=='installed'
                and native['version']==native_version(provider['version'])
                and any(f['installation_id']==provider['installation_id'] and f['workspace_id']==workspace and f['feature_state']=='enabled' for f in features))
    enabled=[f['workspace_id'] for f in features if f['installation_id']==row['installation_id'] and f['feature_state']=='enabled']
    for plugin,spec in manifest['dependencies']['plugins'].items():
        provider=installations.get(plugin)
        if provider is None or package_version(provider['version']) not in SpecifierSet(spec):
            issues.append('Required plugin '+plugin+' does not satisfy '+spec)
        elif any(not available(provider,workspace) for workspace in enabled):
            issues.append('Required plugin '+plugin+' is unavailable in an enabled workspace')
    for requirement in manifest['services']['requires']:
        if requirement.get('optional',False):continue
        for workspace in enabled:
            bindings=[b for b in metadata['bindings'] if b['state']=='active' and b['descriptor']['consumer_installation_id']==row['installation_id']
                      and b['descriptor']['workspace_id']==workspace and b['descriptor']['alias']==requirement['alias']]
            if len(bindings)!=1:
                issues.append('Required binding '+requirement['alias']+' is unavailable in workspace '+workspace);continue
            binding=bindings[0]['descriptor'];provider=installations.get(binding['provider_plugin_id'])
            if (provider is None or provider['installation_id']!=binding['provider_installation_id'] or not available(provider,workspace)
                    or binding['service_id']!=requirement['id'] or binding['contract_major']!=requirement['contract_major']
                    or package_version(binding['api_version']+'.0') not in SpecifierSet(requirement['version'])):
                issues.append('Required provider '+requirement['alias']+' is incompatible or unavailable in workspace '+workspace)
    return {'state':'unavailable' if issues else 'satisfied','issues':sorted(set(issues))}

def installed_view(profile,metadata,*,now,offset='0'):
    offset=page_offset(offset);rows=sorted(metadata['installations'],key=lambda row:(row['plugin_id'],row['installation_id']));items=[]
    modules={row['addon']:row for row in metadata['native_modules']}
    for row in rows[offset:offset+20]:
        descriptor=exact_artifact(profile,row['digest']);manifest=row['manifest'];module=modules.get(manifest['runtime'].get('addon_name'))
        consistent=(descriptor is not None and descriptor['manifest']==manifest and descriptor['version']==row['version'])
        state='not_installed' if module is None else 'installed' if module['state']=='installed' else 'recovery_required'
        if row['runtime']=='external_service':state='not_installed' if row['metadata_state']=='removed' else 'installed'
        retained=row['runtime']=='native' and row['metadata_state']=='removed' and module is None
        if module is not None and module['version']!=native_version(row['version']):state='failed'
        if not consistent and not retained:state='failed'
        dependencies={'state':'unknown','issues':[]} if retained else _dependencies(row,manifest,metadata,profile.get('external_state')) if consistent else {'state':'unknown','issues':['Installed metadata does not match a current curated artifact']}
        degraded=(state in ('failed','recovery_required') or dependencies['state']=='unavailable'
                  or (row['metadata_state']=='removed')!=(state=='not_installed'))
        if retained:
            degraded=any(f['feature_state']!='suspended' for f in metadata['features'] if f['installation_id']==row['installation_id']) or any(
                g['state']=='approved' for g in metadata.get('grants',[]) if g['installation_id']==row['installation_id']) or any(
                row['installation_id'] in (b['descriptor']['consumer_installation_id'],b['descriptor']['provider_installation_id']) for b in metadata['bindings'])
        health={'state':'degraded' if degraded else 'unknown','reason':'Installation or required dependency needs attention.' if degraded else 'Native database installation is absent; retained metadata grants no availability.' if retained else 'Registry observed; plugin-specific health has not been probed.'}
        if row['runtime']=='external_service' and not degraded:health=_external_health(row,metadata,profile.get('external_state'))
        items.append({'installation_id':row['installation_id'],'plugin_id':row['plugin_id'],'version':row['version'],
            'artifact_digest':row['digest'],'runtime':row['runtime'],'metadata_state':row['metadata_state'],'database_state':state,
            'native_version':module['version'] if module else None,'features':[{'workspace_id':f['workspace_id'],'availability':f['feature_state']}
            for f in metadata['features'] if f['installation_id']==row['installation_id']],
            'health':health,
            'dependencies':dependencies,'artifact':artifact_summary(descriptor) if descriptor else None})
    return validate('manager-view',observed(profile,now)|{'kind':'installed','items':items,'next_offset':offset+20 if len(rows)>offset+20 else None})

def validate_upload(raw,expected_digest,profile,*,now,parent=None):
    """Acquire only into private temporary staging; caller owns no trusted store."""
    if not isinstance(raw,bytes) or not 1<=len(raw)<=UPLOAD_LIMIT:raise ContractError('Upload compressed size limit')
    if not isinstance(expected_digest,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',expected_digest):raise ContractError('Exact upload digest required')
    digest='sha256:'+hashlib.sha256(raw).hexdigest()
    value=observed(profile,now)|{'kind':'upload_validation','artifact_digest':digest,'size':len(raw),'result':'invalid',
        'validation_scope':'archive_rejected','artifact':None,'error_code':'DIGEST_MISMATCH','retained':False,'executed':False}
    if digest!=expected_digest:return validate('manager-view',value)
    artifact=exact_artifact(profile,digest)
    if artifact is None:
        return validate('manager-view',value|{'result':'not_curated','validation_scope':'trust_gate','error_code':'NOT_CURATED'})
    trust=artifact['trust'];development=trust['model']=='unsigned-development'
    validator=ArtifactValidator(TrustPolicy('development' if development else 'curated',frozenset([digest]),development,trust['policy_generation']))
    try:
        with tempfile.TemporaryDirectory(prefix='mp-upload-',dir=parent) as temporary:
            path=Path(temporary)/'incoming.mplug';path.write_bytes(raw)
            private,verified=validator.stage(path,temporary,expected_digest=digest)
            with private:
                value.update(result='verified',validation_scope='archive_and_inventory',artifact=artifact_summary(verified.descriptor()),error_code=None)
    except ArtifactError:
        value.update(result='invalid',error_code='INVALID_ARCHIVE')
    return validate('manager-view',value)
