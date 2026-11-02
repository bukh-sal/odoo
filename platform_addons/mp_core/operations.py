"""Untrusted application requests; privileged approval/journal stays OS-owned."""
from datetime import datetime, timezone
import copy
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from odoo import api, fields, http, models
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request
from odoo.addons.mp_identity.scopes import canonical_uuid
from modular_platform.contracts import ContractError, validate, validate_operations_view
from modular_platform.metadata_sql import METADATA_SELECT
from modular_platform.operation_views import prepared_view, request_status
from modular_platform.planning_cli import prepare_document
from modular_platform.plans import check_bundle
from modular_platform.projection import project_deployment
from modular_platform.resolution import dependent_closure, binding_matches_scope
from modular_platform.manager_planning import prepare_manager_native, prepare_manager_removal, manager_runtime, prepare_manager_external
from modular_platform.lifecycle_planning import prepare_current_feature
from modular_platform.lifecycle_impact import inspect_current_image, impact_view
from modular_platform.uninstall_planning import prepare_current_image_uninstall
from modular_platform.manager_views import (UPLOAD_LIMIT, artifact_summary, details_view,
    installed_view, validate_upload)

from .controllers import PublicError, bounded_body, principal, result, site_id


def stamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class ApplicationOperator(models.Model):
    _name='mp.application.operator'
    _description='Locally provisioned application operation requester'
    _rec_name='principal_id'
    principal_id=fields.Many2one('mp.principal',required=True,ondelete='restrict',index=True)
    state=fields.Selection([('active','Active'),('revoked','Revoked')],default='active',required=True)
    _principal_unique=models.Constraint('UNIQUE(principal_id)','One application operator role per principal')

    @api.constrains('principal_id')
    def _human_operator(self):
        if any(row.principal_id.kind!='human' for row in self):raise ValidationError('Application operators must be human principals')


class OperationProfile(models.Model):
    _name='mp.operation.profile'
    _description='Untrusted sanitized operator metadata mirror'
    _rec_name='site_public_id'
    site_public_id=fields.Char(required=True,index=True)
    payload=fields.Json(required=True)
    _site_unique=models.Constraint('UNIQUE(site_public_id)','One public profile per site')


class OperationRequest(models.Model):
    _name='mp.operation.request'
    _description='Untrusted operation nomination, never an OS approval'
    _rec_name='public_id'
    public_id=fields.Char(required=True,index=True,readonly=True)
    site_public_id=fields.Char(required=True,index=True,readonly=True)
    requested_by=fields.Many2one('mp.principal',required=True,ondelete='restrict',readonly=True)
    plan_hash=fields.Char(required=True,readonly=True)
    bundle=fields.Json(required=True,readonly=True)
    base_state=fields.Json(required=True,readonly=True)
    dimensions=fields.Json(default=list,readonly=True)
    requested=fields.Boolean(default=False,readonly=True)
    request_id=fields.Char(index=True,readonly=True)
    journal_mirror=fields.Json(readonly=True)
    _operation_unique=models.Constraint('UNIQUE(public_id)','Operation identity is unique')
    _request_unique=models.Constraint('UNIQUE(request_id)','Request identity is unique')

    @api.constrains('public_id','site_public_id','plan_hash','bundle','base_state')
    def _validate_request(self):
        for row in self:
            canonical_uuid(row.public_id);canonical_uuid(row.site_public_id)
            if len(json.dumps(row.bundle).encode())>2*1024*1024:raise ValidationError('Operation bundle size limit')
            check_bundle(row.bundle,row.base_state)
            if row.public_id!=row.bundle['plan']['operation_id'] or row.plan_hash!=row.bundle['plan_hash'] or row.site_public_id not in row.bundle['plan']['site_ids']:
                raise ValidationError('Request identity mismatch')

    def write(self, values):
        if {'public_id','site_public_id','requested_by','plan_hash','bundle','base_state','dimensions'} & values.keys():
            raise AccessError('Prepared request identity and plan are immutable')
        return super().write(values)


def operator(required=True):
    request.env.cr.execute('''SELECT p.id,p.public_id FROM mp_principal p
        JOIN res_users u ON u.id=p.user_id
        JOIN mp_application_operator o ON o.principal_id=p.id
        WHERE p.user_id=%s AND p.kind='human' AND p.state='active' AND u.active AND o.state='active' ''',[request.env.uid])
    actor=request.env.cr.fetchone()
    if required and not actor:raise AccessError('Application operator required')
    return actor


def profile_metadata():
    record=request.env['mp.operation.profile'].sudo().search([('site_public_id','=',site_id())],limit=1)
    if not record:raise PublicError('DEPENDENCY_UNAVAILABLE')
    profile=record.payload
    required={'schema_version','configuration','runtime','catalog','observed_at'}
    if not isinstance(profile,dict) or not required<=profile.keys() or not profile.keys()<=required|{'staged_release','external_state'} or profile['schema_version']!=1:
        raise ContractError('Invalid sanitized profile')
    if site_id() not in profile['configuration']['site_ids']:raise AccessError('Profile site mismatch')
    # A cache from another code release cannot silently prepare operations here.
    inventory=Path('/opt/modular/distribution-inventory.json').read_bytes()
    if 'sha256:'+hashlib.sha256(inventory).hexdigest()!=profile['runtime']['inventory_digest']:
        raise PublicError('DEPENDENCY_UNAVAILABLE')
    request.env.cr.execute(METADATA_SELECT);metadata=request.env.cr.fetchone()[0]
    return profile,metadata


def profile_document():
    profile,metadata=profile_metadata()
    if any(item['state']!='installed' for item in metadata['native_modules']):raise PublicError('DEPENDENCY_UNAVAILABLE')
    observation={'runtime':profile['runtime'],'image_id':profile['configuration']['image_id'],'sites':[metadata]}
    if 'external_state' in profile:observation['external_state']=profile['external_state']
    document=project_deployment(profile['configuration'],observation,profile['catalog'])
    return document,profile,metadata


def native_impact(profile, requested):
    import psycopg2
    from odoo.sql_db import connection_info_for
    from modular_platform.projection import runtime_inputs
    _, dsn = connection_info_for(request.env.cr.dbname)
    connection = psycopg2.connect(**{**dsn, 'connect_timeout':10})
    connection.set_session(isolation_level='REPEATABLE READ', readonly=True)
    try:
        with connection:
            with connection.cursor() as cursor: cursor.execute("SET LOCAL statement_timeout='5s'")
            selected, _, _ = runtime_inputs(profile['runtime'], profile['catalog'])
            return inspect_current_image(connection, root='/opt/modular', inventory_digest=profile['runtime']['inventory_digest'],
                                         descriptors=selected, site_id=site_id(), requested=requested)
    finally: connection.close()


def own_request(operation_id, actor):
    canonical_uuid(operation_id)
    row=request.env['mp.operation.request'].sudo().search([('public_id','=',operation_id),('site_public_id','=',site_id()),('requested_by','=',actor[0])],limit=1)
    if not row:raise PublicError('NOT_FOUND')
    return row


class Operations(http.Controller):
    @http.route('/api/v1/operations/installed',type='http',auth='public',methods=['GET'])
    def installed(self,offset='0',**kwargs):
        def run():
            operator();profile,metadata=profile_metadata()
            return installed_view(profile,metadata,now=stamp(),offset=offset)
        return result(run)

    @http.route('/api/v1/operations/details',type='http',auth='public',methods=['GET'])
    def details(self,digest=None,**kwargs):
        def run():
            operator();profile,metadata=profile_metadata()
            value=details_view(profile,digest,now=stamp())
            if value is None:raise PublicError('NOT_FOUND')
            return value
        return result(run)

    @http.route('/api/v1/operations/validate-upload',type='http',auth='public',methods=['POST'],csrf=False,max_content_length=UPLOAD_LIMIT)
    def upload(self):
        def run():
            operator()
            if not request.validate_csrf(request.httprequest.headers.get('X-CSRFToken')):raise AccessError('CSRF required')
            if request.httprequest.mimetype!='application/octet-stream' or (request.httprequest.content_length or 0)>UPLOAD_LIMIT:
                raise ContractError('Bounded binary archive required')
            # The native HTTP wrapper enforces the route bound before get_data,
            # including chunked bodies. No caller filename/path is used.
            raw=request.httprequest.get_data()
            profile,metadata=profile_metadata()
            return validate_upload(raw,request.httprequest.headers.get('X-MP-Artifact-Digest'),profile,now=stamp())
        return result(run)

    @http.route('/api/v1/operations/context',type='http',auth='public',methods=['GET'])
    def context(self):
        def run():
            value={'schema_version':1,'kind':'context','can_request':bool(operator(False)),
                   'site_id':site_id(),'control_authority':'independent_local_os'}
            if value['can_request']:
                request.env.cr.execute('SELECT public_id,name,state FROM mp_workspace ORDER BY public_id')
                value['workspaces']=[{'workspace_id':ident,'name':name,'state':state} for ident,name,state in request.env.cr.fetchall()]
            return validate_operations_view(value)
        return result(run)

    @http.route('/api/v1/operations/catalog',type='http',auth='public',methods=['GET'])
    def catalog(self,offset='0',**kwargs):
        def run():
            operator();document,profile,metadata=profile_document()
            if not str(offset).isdigit() or not 0<=int(offset)<=10000:raise ContractError('Invalid catalog offset')
            items=sorted(profile['catalog'],key=lambda item:(item['manifest']['plugin']['id'],item['manifest']['plugin']['version']))
            page=[]
            for artifact in items[int(offset):int(offset)+20]:
                page.append(artifact_summary(artifact))
            from modular_platform.plans import data_digest
            return validate_operations_view({'schema_version':1,'kind':'catalog','snapshot_digest':data_digest(items),
                'observed_at':profile['observed_at'],'stale':_stale(profile['observed_at']), 'items':page,
                'next_offset':int(offset)+20 if len(items)>int(offset)+20 else None})
        return result(run)

    @http.route('/api/v1/operations/prepare',type='http',auth='public',methods=['POST'],csrf=False,max_content_length=65536)
    def prepare(self):
        def run():
            actor=operator();nomination=bounded_body('operations-request')
            if nomination['operation']!='prepare' or nomination['site_id']!=site_id():raise AccessError('Current site preparation required')
            request.env.cr.execute("SELECT count(*) FROM mp_operation_request WHERE requested_by=%s AND create_date>=timezone('UTC',now())-interval '1 minute'",[actor[0]])
            if request.env.cr.fetchone()[0]>=10:raise PublicError('RATE_LIMITED')
            document,profile,metadata=profile_document()
            if manager_runtime(document,profile['catalog'],nomination)=='external_service':
                bundle=prepare_manager_external(document,[metadata],profile['catalog'],profile.get('external_state'),
                    nomination,operation_id=str(uuid4()),created_at=stamp())
                return _save_prepared(bundle,document,actor,profile)
            if nomination['operation_type'] in ('install','upgrade'):
                bundle=prepare_manager_native(document,[metadata],profile['catalog'],profile['runtime'],profile.get('staged_release'),
                    nomination,operation_id=str(uuid4()),created_at=stamp())
                return _save_prepared(bundle,document,actor,profile)
            if nomination['operation_type']=='remove':
                bundle=prepare_manager_removal(document,[metadata],profile['catalog'],profile['runtime'],profile.get('staged_release'),
                    nomination,operation_id=str(uuid4()),created_at=stamp())
                return _save_prepared(bundle,document,actor,profile)
            if nomination['operation_type']=='uninstall':
                if nomination['workspace_ids']:raise ContractError('Native uninstall is site-wide; workspace subsets are invalid')
                entry=next((r for r in document['state']['release_lock']['plugins'] if r['plugin_id']==nomination['plugin_id']),None)
                if not entry or entry['runtime']!='native':raise PublicError('NOT_FOUND')
                impact=native_impact(profile,[entry['native_addon']])
                if not nomination['cascade'] and len(impact['plugins'])!=1:raise ContractError('Explicit dependent cascade required for native uninstall')
                targets=[dict(installation_id=p['installation_id'],site_id=site_id(),workspace_id=workspace,
                              plugin_id=p['plugin_id'],action='uninstall') for p in impact['plugins'] for workspace in p['workspace_ids']]
                bundle=prepare_current_image_uninstall(document,[metadata],profile['catalog'],impact=impact,targets=targets,
                                                       operation_id=str(uuid4()),created_at=stamp())
                return _save_prepared(bundle,document,actor,profile)
            if nomination['operation_type'] not in ('suspend','enable'):raise PublicError('DEPENDENCY_UNAVAILABLE')
            plugin=nomination['plugin_id'];wanted=set(nomination['workspace_ids']);targets=[]
            for workspace in sorted(wanted):
                installations=[item for item in document['state']['installations'] if item['site_id']==site_id() and item['workspace_id']==workspace]
                selected=next((item for item in installations if item['plugin_id']==plugin),None)
                if not selected:raise PublicError('NOT_FOUND')
                chosen={plugin}
                manifests={item['manifest']['plugin']['id']:item for item in profile['catalog']
                           if any(entry['plugin_id']==item['manifest']['plugin']['id'] and entry['digest']==item['digest'] for entry in document['state']['release_lock']['plugins'])}
                if nomination['operation_type']=='suspend':
                    candidates=[]
                    for installation in installations:
                        if installation['feature_state']!='enabled' and installation['plugin_id']!=plugin:continue
                        descriptor=copy.deepcopy(manifests[installation['plugin_id']])
                        descriptor['required_providers']=[item['provider'] for item in document['state']['release_lock']['service_selection'] if item['consumer']==installation['plugin_id'] and not item['optional'] and binding_matches_scope(item,site_id(),workspace)]
                        candidates.append(descriptor)
                    chosen=set(dependent_closure(candidates,[plugin],cascade=nomination['cascade']))
                elif nomination['cascade']:
                    while True:
                        added={dependency for ident in chosen for dependency in manifests[ident]['manifest']['dependencies']['plugins']}
                        added.update(item['provider'] for item in document['state']['release_lock']['service_selection'] if item['consumer'] in chosen and not item['optional'] and binding_matches_scope(item,site_id(),workspace))
                        if added<=chosen:break
                        chosen.update(added)
                for ident in sorted(chosen):
                    installation=next((item for item in installations if item['plugin_id']==ident),None)
                    if not installation:raise PublicError('DEPENDENCY_UNAVAILABLE')
                    targets.append({key:installation[key] for key in ('installation_id','site_id','workspace_id','plugin_id')}|{'action':nomination['operation_type']})
            bundle=prepare_current_feature(document,[metadata],profile['catalog'],targets=targets,
                operation_type=nomination['operation_type'],operation_id=str(uuid4()),created_at=stamp())
            return _save_prepared(bundle,document,actor,profile)
        return result(run)

    @http.route('/api/v1/operations/request',type='http',auth='public',methods=['POST'],csrf=False,max_content_length=65536)
    def submit(self):
        def run():
            actor=operator();value=bounded_body('operations-request')
            if value['operation']!='request':raise ContractError('Exact request nomination required')
            row=own_request(value['operation_id'],actor)
            request.env.cr.execute('SELECT id FROM mp_operation_request WHERE id=%s FOR UPDATE',[row.id]);row.invalidate_recordset()
            if row.plan_hash!=value['plan_hash'] or row.requested and row.request_id!=value['request_id']:raise PublicError('CONFLICT')
            if not row.requested:row.write({'requested':True,'request_id':value['request_id']})
            return _status(row,actor)
        return result(run)

    @http.route('/api/v1/operations/status/<string:operation_id>',type='http',auth='public',methods=['GET'])
    def status(self,operation_id):
        return result(lambda:_status(own_request(operation_id,operator()),operator()))

    @http.route('/api/v1/operations/bundle/<string:operation_id>',type='http',auth='public',methods=['GET'])
    def bundle(self,operation_id):
        def run():
            row=own_request(operation_id,operator());check_bundle(row.bundle,row.base_state)
            return row.bundle
        return result(run)

    @http.route('/api/v1/operations/impact/<string:operation_id>',type='http',auth='public',methods=['GET'])
    def impact(self,operation_id):
        def run():
            row=own_request(operation_id,operator());check_bundle(row.bundle,row.base_state)
            impact=row.bundle['operation_lock'].get('native_uninstall_impact')
            if impact is None or row.bundle['plan']['operation_type']!='uninstall':raise PublicError('NOT_FOUND')
            return impact_view(impact,operation_id=row.public_id,plan_hash=row.plan_hash,observed_at=row.bundle['plan']['created_at'])
        return result(run)


def _stale(observed_at, seconds=900):
    return (datetime.now(timezone.utc)-datetime.fromisoformat(observed_at.replace('Z','+00:00'))).total_seconds()>seconds


def _save_prepared(bundle,document,actor,profile):
    dimensions=[]
    for target in bundle['operation_lock']['targets']:
        existing=next((item for item in document['state']['installations'] if item['installation_id']==target['installation_id'] and item['workspace_id']==target['workspace_id']),None)
        dimensions.append({'plugin_id':target['plugin_id'],'installation_id':target['installation_id'],'workspace_id':target['workspace_id'],
            'artifact_state':'verified','release_state':'planned' if 'staged_image' in bundle['operation_lock'] else 'active',
            'database_state':existing['state'] if existing else 'not_installed','feature_state':existing['feature_state'] if existing else None,'service_state':None})
    request.env['mp.operation.request'].sudo().create({'public_id':bundle['plan']['operation_id'],'site_public_id':site_id(),
        'requested_by':actor[0],'plan_hash':bundle['plan_hash'],'bundle':bundle,'base_state':document['state'],'dimensions':dimensions})
    return prepared_view(bundle,observed_at=profile['observed_at'],stale=_stale(profile['observed_at']))


def _status(row,actor):
    if row.journal_mirror:
        value=copy.deepcopy(row.journal_mirror)
        if value['operation_id']!=row.public_id or value['plan_hash']!=row.plan_hash or value['requested_by']!=actor[1]:raise ContractError('Mirror identity mismatch')
        value['stale']=_stale(value['observed_at'],30)
        return validate_operations_view(value)
    return request_status(row.bundle,actor=actor[1],dimensions=row.dimensions,observed_at=stamp(),requested=row.requested)
