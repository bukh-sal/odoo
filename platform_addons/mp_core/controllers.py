"""Workspace/session metadata and registered major-1 JSON gateway."""
import json
import time
from uuid import uuid4
from datetime import datetime, timedelta
import hashlib
import rfc8785
import psycopg2
import logging
import traceback
from pathlib import Path

from odoo import http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.addons.mp_identity.scopes import current_scope
from modular_platform.contracts import ContractError, validate, load_json, ERROR_STATUS, validate_binding, FORMAT_CHECKER
from modular_platform.contracts import CONTRACTS

from .registry import SERVICES

_logger=logging.getLogger(__name__)


class PublicError(Exception):
    def __init__(self,code,details=None): self.code=code;self.details=details or {}


def bounded_body(schema):
    if request.httprequest.mimetype!='application/json' or (request.httprequest.content_length or 0)>65536:raise ContractError('Bounded JSON required')
    if not request.validate_csrf(request.httprequest.headers.get('X-CSRFToken')):raise AccessError('CSRF required')
    # The pinned wrapper exposes get_data, not stream. Native @route limits are
    # applied before parameter/body extraction, including chunked input.
    raw=request.httprequest.get_data()
    if len(raw)>65536:raise ContractError('Bounded JSON required')
    return validate(schema,load_json(raw))


def audit(decision,ident):
    # Narrow append-only metadata write after the dispatcher has decided. Never
    # log bodies, credentials, arbitrary header values or the backing user's DB.
    scope=getattr(request,'_mp_authoritative_scope',None)
    actor=scope.principal_public_id if scope else None
    if actor is None and request.session.uid:
        request.env.cr.execute("SELECT public_id FROM mp_principal WHERE user_id=%s",[request.session.uid])
        row=request.env.cr.fetchone();actor=row[0] if row else None
    metadata={'authenticated_installation_id':None,'consumer_installation_id':getattr(request,'_mp_consumer_id',None),'provider_installation_id':getattr(request,'_mp_provider_id',None),'attribution_mismatch':getattr(request,'_mp_attribution_mismatch',False)}
    request.env.cr.execute("""INSERT INTO mp_audit_event
        (actor_id,workspace_public_id,plugin_id,action,target_id,decision,request_id,metadata,create_date)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,timezone('UTC',now()))""",[actor,scope.workspace_public_id if scope else None,getattr(request,'_mp_provider_plugin',None),request.httprequest.path[:200],getattr(request,'_mp_target_id',None),decision,ident,json.dumps(metadata)])


def advertised_capabilities(plugin,manifest,scope):
    roles=json.loads((CONTRACTS/'role-permissions.json').read_text())['plugin_permissions']
    if plugin in roles:
        names=roles[plugin].get(scope.role,[])
        return [name if ':' in name else plugin+':'+name for name in names]
    return [plugin+':'+name for name in manifest['permissions']['defines'] if scope.role!='viewer' or name.endswith('.read')]


def workspace_administrator():
    scope=current_scope(request.env)
    if scope.principal_kind!='human' or scope.role!='administrator':raise AccessError('Workspace administrator required')
    # Serializes policy changes. A concurrent committed policy-generation change
    # triggers the native repeatable-read whole-request retry, not stale authority.
    request.env.cr.execute('SELECT id FROM mp_workspace WHERE id=%s FOR UPDATE',[scope.workspace_id])
    scope=current_scope(request.env)
    if scope.principal_kind!='human' or scope.role!='administrator':raise AccessError('Workspace administrator required')
    return scope


def site_id():
    # Fixed site configuration, not chosen by a client, and not a secret.
    request.env.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.site_id'")
    row=request.env.cr.fetchone()
    if not row:raise PublicError('DEPENDENCY_UNAVAILABLE')
    return row[0]


def principal():
    request.env.cr.execute("SELECT public_id,name FROM mp_principal WHERE user_id=%s AND state='active'",[request.env.uid])
    row=request.env.cr.fetchone()
    if not row:raise PublicError('FORBIDDEN')
    return row


def result(handler, version='1.0'):
    ident=str(uuid4())
    try:
        if not request.session.uid:raise PublicError('UNAUTHENTICATED')
        data=handler()
        envelope={'data':data,'api_version':version,'request_id':ident}
        validate('service-response',envelope)
        audit('allowed',ident)
        return request.make_json_response(envelope,headers=[('Cache-Control','no-store')])
    except (PublicError,AccessError,MissingError,ValidationError,ContractError,ValueError,TypeError) as error:
        request.env.cr.rollback()
        code=error.code if isinstance(error,PublicError) else 'FORBIDDEN' if isinstance(error,AccessError) else 'NOT_FOUND' if isinstance(error,MissingError) else 'VALIDATION_FAILED'
        details=error.details if isinstance(error,PublicError) else {}
        audit('denied',ident)
        return request.make_json_response({'error':{'code':code,'message':code.replace('_',' ').capitalize(),'request_id':ident,'retryable':code in {'DEPENDENCY_UNAVAILABLE','RATE_LIMITED'},'details':details}},status=ERROR_STATUS[code],headers=[('Cache-Control','no-store')])
    except (psycopg2.errors.SerializationFailure,psycopg2.errors.DeadlockDetected):
        # Preserve the substrate's whole-request retry; never swallow a failed
        # transaction then return a fabricated successful/idempotent result.
        raise
    except Exception as error:
        request.env.cr.rollback()
        # Operator diagnostics retain frame locations and exception class only;
        # no exception repr/message, local variables, SQL or request content.
        frames=[{'file':Path(frame.filename).name,'line':frame.lineno,'function':frame.name} for frame in traceback.extract_tb(error.__traceback__)[-12:]]
        _logger.error('Platform request failed request_id=%s exception_type=%s frames=%s',ident,type(error).__name__,json.dumps(frames))
        audit('denied',ident)
        return request.make_json_response({'error':{'code':'INTERNAL_ERROR','message':'Internal error','request_id':ident,'retryable':False,'details':{}}},status=500,headers=[('Cache-Control','no-store')])


class CoreGateway(http.Controller):
    @http.route('/api/v1/session',type='http',auth='public',methods=['GET'])
    def session(self):
        def run():
            actor,name=principal()
            return {'principal_id':actor,'display_name':name,'site_id':site_id(),'csrf_token':request.csrf_token()}
        return result(run)

    @http.route('/api/v1/workspaces',type='http',auth='public',methods=['GET'])
    def workspaces(self):
        return result(lambda:[{'id':row.public_id,'name':row.name} for row in request.env['mp.workspace'].search([('state','=','active')])])

    @http.route('/api/v1/context',type='http',auth='public',methods=['GET'])
    def context(self,plugin_id=None,**kwargs):
        def run():
            scope=current_scope(request.env);actor,name=principal()
            request.env.cr.execute("SELECT public_id,manifest FROM mp_plugin_installation WHERE plugin_id=%s AND state='installed'",[plugin_id])
            install=request.env.cr.fetchone()
            if not install:raise PublicError('NOT_FOUND')
            request.env.cr.execute("SELECT availability FROM mp_workspace_plugin WHERE workspace_id=%s AND plugin_id=%s",[scope.workspace_id,plugin_id])
            row=request.env.cr.fetchone()
            if not row or row[0]!='enabled':raise PublicError('PLUGIN_SUSPENDED')
            caps=advertised_capabilities(plugin_id,install[1],scope)
            space=request.env['mp.workspace'].browse(scope.workspace_id)
            context={'ui_api_major':1,'principal_id':actor,'display_name':name,'site_id':site_id(),'workspace_id':scope.workspace_public_id,'plugin_id':plugin_id,'installation_id':install[0],'locale':space.default_locale,'direction':'rtl' if space.default_locale=='ar' else 'ltr','timezone':space.timezone,'generation':1,'policy_generation':scope.policy_generation,'capabilities':caps}
            validate('host-context',context)
            request.env.cr.execute("SELECT descriptor FROM mp_service_binding WHERE consumer_id=(SELECT id FROM mp_plugin_installation WHERE plugin_id=%s) AND workspace_id=%s AND state='active'",[plugin_id,scope.workspace_id])
            bindings=[row[0] for row in request.env.cr.fetchall()]
            return {'context':context,'bindings':bindings,'pages':install[1]['ui']['pages'],'csrf_token':request.csrf_token()}
        return result(run)

    @http.route('/api/v1/services/<string:service>/<string:method>',type='http',auth='public',methods=['POST'],csrf=False,max_content_length=65536)
    def call(self,service,method):
        def run():
            started=time.monotonic()
            try: budget=int(request.httprequest.headers.get('X-MP-Deadline-Ms','10000'))
            except ValueError:raise ContractError('Invalid deadline')
            if not 0<=budget<=30000:raise ContractError('Invalid deadline')
            if budget==0:raise PublicError('DEADLINE_EXCEEDED',{'outcome':'not_started'})
            body=bounded_body('service-request')
            scope=current_scope(request.env)
            binding_id=request.httprequest.headers.get('X-MP-Binding')
            # Binding IDs are routing references. Current actor/model permission
            # is always checked regardless of attributed consumer/plugin.
            request.env.cr.execute("""SELECT b.descriptor,c.manifest,c.state,p.manifest,p.state
              FROM mp_service_binding b JOIN mp_plugin_installation c ON c.id=b.consumer_id
              JOIN mp_plugin_installation p ON p.public_id=b.descriptor->>'provider_installation_id'
             WHERE b.public_id=%s AND b.workspace_id=%s AND b.state='active'""",[binding_id,scope.workspace_id])
            row=request.env.cr.fetchone()
            if not row:raise PublicError('DEPENDENCY_UNAVAILABLE')
            binding,consumer,cstate,provider,pstate=row
            request._mp_consumer_id=binding['consumer_installation_id'];request._mp_provider_id=binding['provider_installation_id'];request._mp_provider_plugin=provider['plugin']['id']
            label=request.httprequest.headers.get('X-MP-Consumer')
            request._mp_attribution_mismatch=bool(label and label!=binding['consumer_installation_id'])
            if cstate!='installed' or pstate!='installed':raise PublicError('PLUGIN_SUSPENDED')
            requirement=next((r for r in consumer['services']['requires'] if r['alias']==binding['alias']),None)
            declaration=next((p for p in provider['services']['provides'] if p['id']==service and p['api_version']==body['api_version']),None)
            if not requirement or not declaration:raise PublicError('DEPENDENCY_UNAVAILABLE')
            validate_binding(binding,requirement,{**declaration,'plugin_id':provider['plugin']['id'],'installation_id':binding['provider_installation_id']})
            if binding['site_id']!=site_id() or binding['service_id']!=service or binding['api_version']!=body['api_version']:raise PublicError('CONFLICT')
            spec=SERVICES.get((service,body['api_version'],provider['plugin']['id']),{}).get(method)
            if spec is None or method not in declaration['methods']:raise PublicError('NOT_FOUND')
            model=request.env[spec.model]
            model._mp_guard(spec.action)
            from jsonschema import Draft202012Validator
            from modular_platform.contracts import CONTRACTS
            schema=json.loads((CONTRACTS/spec.schema_file).read_text())['$defs'][spec.input_schema]
            if not Draft202012Validator(schema,format_checker=FORMAT_CHECKER).is_valid(body['input']):raise ContractError('Invalid method input')
            # Integration capabilities narrow supported paths. A forged browser
            # consumer cannot widen the actor action check above.
            if consumer['plugin']['id']!=provider['plugin']['id']:
                permission=spec.permission
                request.env.cr.execute("SELECT 1 FROM mp_plugin_grant g JOIN mp_plugin_installation i ON i.id=g.installation_id WHERE i.public_id=%s AND g.workspace_id=%s AND g.capability=%s AND g.state='approved'",[binding['consumer_installation_id'],scope.workspace_id,permission])
                if not request.env.cr.fetchone():raise AccessError('Integration grant required')
            # Both consumer availability and provider model guard apply. Merely
            # attributing a different consumer never supplies actor permission.
            request.env.cr.execute("SELECT availability FROM mp_workspace_plugin WHERE workspace_id=%s AND plugin_id=%s",[scope.workspace_id,consumer['plugin']['id']])
            available=request.env.cr.fetchone()
            if not available or available[0]!='enabled':raise PublicError('PLUGIN_SUSPENDED')
            outcome_id=None
            if spec.mutation and body.get('idempotency_key'):
                digest=hashlib.sha256(rfc8785.dumps(body['input'])).hexdigest()
                scope_key=[scope.principal_public_id,site_id(),scope.workspace_id,service,binding['contract_major'],binding['provider_installation_id'],method,body['idempotency_key']]
                # Narrow deduplication metadata write, after identity, binding,
                # current actor/model action, feature and integration authority.
                request.env.cr.execute("""INSERT INTO mp_service_outcome
                    (actor_id,site_id,workspace_id,service_id,contract_major,provider_id,method,key,input_digest,binding_id,binding_generation,api_version,state,expires_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'in_progress',%s)
                    ON CONFLICT (actor_id,site_id,workspace_id,service_id,contract_major,provider_id,method,key) DO NOTHING RETURNING id""",scope_key+[digest,binding_id,binding['generation'],body['api_version'],datetime.utcnow()+timedelta(hours=24)])
                inserted=request.env.cr.fetchone()
                if not inserted:
                    request.env.cr.execute("""SELECT input_digest,binding_id,binding_generation,api_version,state,result,expires_at FROM mp_service_outcome
                       WHERE actor_id=%s AND site_id=%s AND workspace_id=%s AND service_id=%s AND contract_major=%s AND provider_id=%s AND method=%s AND key=%s FOR UPDATE""",scope_key)
                    old=request.env.cr.fetchone()
                    if not old or tuple(old[:4])!=(digest,binding_id,binding['generation'],body['api_version']) or old[6]<=datetime.utcnow():raise PublicError('CONFLICT',{'outcome':'unknown'})
                    if old[4]!='completed':raise PublicError('CONFLICT',{'outcome':'unknown'})
                    # Guard re-executed above; no saved result without current auth.
                    return old[5]
                outcome_id=inserted[0]
            if (time.monotonic()-started)*1000>=budget:raise PublicError('DEADLINE_EXCEEDED',{'outcome':'not_started'})
            value=getattr(model,spec.handler)(body['input'])
            if not Draft202012Validator(spec.output_schema,format_checker=FORMAT_CHECKER).is_valid(value):raise PublicError('INTERNAL_ERROR')
            if outcome_id:
                request.env.cr.execute("UPDATE mp_service_outcome SET state='completed',result=%s::jsonb WHERE id=%s",[json.dumps(value),outcome_id])
            # The database effect and outcome record commit with the same native
            # HTTP transaction. No manual commit or external effect in handlers.
            return value
        return result(run)

    @http.route('/api/v1/workspace/members',type='http',auth='public',methods=['GET','POST'],csrf=False,max_content_length=65536)
    def members(self):
        def run():
            scope=workspace_administrator()
            if request.httprequest.method=='GET':
                request.env.cr.execute("""SELECT p.public_id,p.name,p.kind,m.role,m.state FROM mp_membership m
                    JOIN mp_principal p ON p.id=m.principal_id WHERE m.workspace_id=%s AND m.state='active'
                    ORDER BY p.name,p.public_id LIMIT 1001""",[scope.workspace_id])
                rows=[dict(zip(['principal_id','display_name','kind','role','state'],r)) for r in request.env.cr.fetchall()]
                if len(rows)>1000:raise PublicError('RATE_LIMITED')
                from jsonschema import Draft202012Validator
                schema=json.loads((CONTRACTS/'workspace-membership.schema.json').read_text())
                if not Draft202012Validator({'$defs':schema['$defs'],'$ref':'#/$defs/member_list'}).is_valid(rows):raise PublicError('INTERNAL_ERROR')
                return rows
            values=bounded_body('workspace-membership')
            request.env.cr.execute("SELECT id,kind FROM mp_principal WHERE public_id=%s AND state='active'",[values['principal_id']])
            target=request.env.cr.fetchone()
            if not target:raise MissingError('Resource unavailable')
            request._mp_target_id=values['principal_id']
            if target[1]=='service' and values.get('role')=='administrator':raise ContractError('Technical principals cannot administer workspaces')
            # Reviewed elevation: the live human workspace-admin decision above
            # authorizes only this sanitized metadata row in this workspace.
            model=request.env['mp.membership'].sudo()
            row=model.search([('workspace_id','=',scope.workspace_id),('principal_id','=',target[0])],limit=1)
            removing=values['operation']=='remove'
            if row and row.state=='active' and row.role=='administrator' and (removing or values.get('role')!='administrator'):
                request.env.cr.execute("""SELECT count(*) FROM mp_membership m JOIN mp_principal p ON p.id=m.principal_id
                    WHERE m.workspace_id=%s AND m.state='active' AND m.role='administrator' AND p.kind='human' AND p.state='active'""",[scope.workspace_id])
                if request.env.cr.fetchone()[0]<=1:raise PublicError('CONFLICT',{'outcome':'not_started'})
            if removing:
                if not row or row.state!='active':raise MissingError('Resource unavailable')
                row.write({'state':'revoked'})
            else:
                if values['operation']=='update' and (not row or row.state!='active'):raise MissingError('Resource unavailable')
                if not row or row.state!='active':
                    request.env.cr.execute("SELECT count(*) FROM mp_membership WHERE workspace_id=%s AND state='active'",[scope.workspace_id])
                    if request.env.cr.fetchone()[0]>=1000:raise PublicError('RATE_LIMITED')
                if row:row.write({'role':values['role'],'state':'active'})
                else:model.create({'principal_id':target[0],'workspace_id':scope.workspace_id,'role':values['role']})
            return {'principal_id':values['principal_id'],'changed':True}
        return result(run)

    @http.route('/api/v1/workspace/settings',type='http',auth='public',methods=['GET','POST'],csrf=False,max_content_length=65536)
    def workspace_settings(self):
        def run():
            scope=workspace_administrator()
            if request.httprequest.method=='POST':
                values=bounded_body('workspace-settings')
                if 'name' in values:
                    values['name']=values['name'].strip()
                    if not values['name']:raise PublicError('VALIDATION_FAILED',{'field':'name'})
                if 'timezone' in values:
                    import pytz
                    try:pytz.timezone(values['timezone'])
                    except pytz.UnknownTimeZoneError:raise PublicError('VALIDATION_FAILED',{'field':'timezone'}) from None
                # Reviewed elevation after human administrator + exact scope
                # decision. Schema cannot select another target or privileged field.
                request.env['mp.workspace'].sudo().browse(scope.workspace_id).write(values)
                request._mp_target_id=scope.workspace_public_id
                return {'workspace_id':scope.workspace_public_id,'changed':True}
            row=request.env['mp.workspace'].browse(scope.workspace_id)
            data={'workspace_id':row.public_id,'name':row.name,'slug':row.slug,'default_locale':row.default_locale,'timezone':row.timezone,'policy_generation':row.policy_generation}
            from jsonschema import Draft202012Validator
            schema=json.loads((CONTRACTS/'workspace-settings.schema.json').read_text())['$defs']['settings']
            if not Draft202012Validator(schema).is_valid(data):raise PublicError('INTERNAL_ERROR')
            return data
        return result(run)
