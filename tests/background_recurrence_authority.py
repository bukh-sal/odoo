"""PostgreSQL proof of the narrow recurrence credential-footprint prerequisite."""
from copy import deepcopy
import json
import os

import psycopg2

from modular_platform.recurrence_authority import review,validate,RecurrenceAuthorityError


SITE='00000000-0000-4000-8000-000000000001'
INSTALLATION='00000000-0000-4000-8000-000000000004'
SCHEMA="""
CREATE TABLE ir_config_parameter(key text,value text);
CREATE TABLE mp_service_credential(id int,principal_id int,workspace_id int,installation_public_id text,
    audience text,actions text,expires_at timestamp,state text,token_digest text);
CREATE TABLE mp_principal(id int,user_id int,kind text,state text);
CREATE TABLE res_users(id int,active bool);
CREATE TABLE mp_workspace(id int,state text);
CREATE TABLE mp_membership(principal_id int,workspace_id int,state text);
CREATE TABLE mp_plugin_installation(id int,public_id text,runtime text);
CREATE TABLE ir_model_data(res_id int,model text,module text,name text);
CREATE TABLE res_groups_users_rel(uid int,gid int);
CREATE TABLE mp_job_schedule(site_id text,actor_id int,workspace_id int,installation_id int,payload jsonb);
"""


def run(connection):
    with connection.cursor() as cr:
        cr.execute(SCHEMA)
        cr.execute('INSERT INTO ir_config_parameter VALUES (\'mp.site_id\',%s)',[SITE])
        cr.execute("INSERT INTO mp_principal VALUES(2,22,'service','active'); INSERT INTO res_users VALUES(22,true)")
        cr.execute("INSERT INTO mp_workspace VALUES(3,'active'); INSERT INTO mp_membership VALUES(2,3,'active')")
        cr.execute("INSERT INTO mp_plugin_installation VALUES(4,%s,'native')",[INSTALLATION])
        cr.execute("INSERT INTO mp_service_credential VALUES(7,2,3,%s,'mp-host-v1','write,read','2099-01-01','active','DO_NOT_EXPORT_TOKEN_DIGEST')",[INSTALLATION])
        payload=dict(context=dict(credential_id=7,authenticated_installation_id=INSTALLATION,allowed_actions=['read','write']))
        cr.execute('INSERT INTO mp_job_schedule VALUES(%s,2,3,4,%s::jsonb)',[SITE,json.dumps(payload)])
        cr.execute("INSERT INTO ir_model_data VALUES(99,'res.groups','base','group_system')")
    connection.commit()
    result={}
    with connection.cursor() as cr:
        policy=review(cr,SITE)
        assert validate(cr,SITE,policy)==dict(active_credentials=1,reviewed_credentials=1)
        assert 'DO_NOT_EXPORT' not in json.dumps(policy)
        result['scoped_native_credential_accepted_without_secret']=True
        def refused(label,sql,args=()):
            cr.execute('SAVEPOINT probe')
            cr.execute(sql,args)
            try:validate(cr,SITE,policy)
            except RecurrenceAuthorityError:result[label]=True
            else:raise AssertionError(label+' was accepted')
            finally:cr.execute('ROLLBACK TO SAVEPOINT probe')
        refused('global_administrator_mapping_refused','INSERT INTO res_groups_users_rel VALUES(22,99)')
        refused('administrator_user_id_refused','UPDATE mp_principal SET user_id=1; INSERT INTO res_users VALUES(1,true)')
        refused('external_installation_refused',"UPDATE mp_plugin_installation SET runtime='external_service'")
        refused('wider_actions_require_new_review',"UPDATE mp_service_credential SET actions='read,write,unlink'")
        refused('longer_credential_lifetime_requires_new_review',"UPDATE mp_service_credential SET expires_at='2099-02-01'")
        refused('credential_without_matching_schedule_refused',"INSERT INTO mp_service_credential SELECT 8,principal_id,workspace_id,installation_public_id,audience,actions,expires_at,state,'different' FROM mp_service_credential")
        refused('foreign_workspace_refused','UPDATE mp_service_credential SET workspace_id=8')
        refused('revoked_membership_refused',"UPDATE mp_membership SET state='revoked'")
        refused('foreign_site_refused',"UPDATE ir_config_parameter SET value='00000000-0000-4000-8000-000000000099'")
        duplicate=deepcopy(policy);duplicate['credentials']*=2
        try:validate(cr,SITE,duplicate)
        except RecurrenceAuthorityError:result['duplicate_policy_identity_refused']=True
        else:raise AssertionError('Duplicate reviewed identity accepted')
        cr.execute("UPDATE mp_service_credential SET token_digest='ROTATED_SECRET_DIGEST'")
        assert validate(cr,SITE,policy)['active_credentials']==1
        assert 'ROTATED_SECRET' not in json.dumps(review(cr,SITE))
        result['secret_rotation_preserves_reviewed_scope_without_export']=True
        cr.execute("UPDATE mp_service_credential SET state='revoked'")
        assert validate(cr,SITE,policy)==dict(active_credentials=0,reviewed_credentials=1)
        cr.execute("SELECT state FROM mp_service_credential WHERE id=7")
        assert cr.fetchone()==('revoked',)
        result['revoked_credential_remains_revoked']=True
        cr.execute("INSERT INTO mp_service_credential SELECT 8,principal_id,workspace_id,installation_public_id,audience,actions,expires_at,'active','new_secret' FROM mp_service_credential WHERE id=7")
        cr.execute("UPDATE mp_job_schedule SET payload=jsonb_set(payload,'{context,credential_id}','8')")
        try:validate(cr,SITE,policy)
        except RecurrenceAuthorityError:result['replacement_identity_requires_new_review']=True
        else:raise AssertionError('Replacement credential inherited old approval')
        replacement=review(cr,SITE)
        assert validate(cr,SITE,replacement)==dict(active_credentials=1,reviewed_credentials=1)
        assert replacement['credentials'][0]['credential_id']==8
        result['new_review_accepts_replacement_in_same_scope']=True
    connection.rollback()
    return result


if __name__=='__main__':
    database=os.environ['MP_BX_FIXTURE_DATABASE']
    assert database=='mp_bx_recurrence_authority'
    with psycopg2.connect(host='127.0.0.1',dbname=database,user='postgres',connect_timeout=5) as connection:
        print(json.dumps(dict(state='passed',scope='Private PostgreSQL authority guard only; producer and native lifecycle are not enabled',checks=run(connection)),sort_keys=True))
