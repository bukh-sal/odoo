import hashlib
import json
import os
from pathlib import Path
import re
import time

import rfc8785
from odoo import http
from odoo.http import request
from odoo.addons.mp_core.controllers import CoreGateway
from odoo.addons.mp_identity.scopes import current_scope


class CommitResponseFault(CoreGateway):
    @http.route()
    def call(self,service,method):
        response=super().call(service,method)
        if os.environ.get('MP_R1_FAULT_FILE')!='/run/mp-fault/arm.json' or response.status_code!=200:return response
        arm=json.loads(Path('/run/mp-fault/arm.json').read_text())
        if not re.fullmatch(r'[0-9a-f]{32}',arm['nonce']):raise RuntimeError('Invalid disposable fault nonce')
        mode=arm.get('fault','exit_after_commit')
        if mode not in ['exit_after_commit','delay_after_commit']:raise RuntimeError('Unsupported disposable fault')
        scope=current_scope(request.env);body=request.get_json_data()
        matching_key=body.get('idempotency_key')==arm.get('key') if arm.get('key') else mode=='delay_after_commit' and service=='org.example.canvas.boards' and method=='save' and arm.get('key_prefix')=='board-' and str(body.get('idempotency_key','')).startswith('board-')
        if (request.env.cr.dbname.startswith('mp_disposable_r0_r1_') and
            request.env.cr.dbname==arm['database'] and scope.principal_public_id==arm['principal_id'] and
            scope.workspace_public_id==arm['workspace_id'] and service==arm['service'] and method==arm['method'] and
            matching_key and hashlib.sha256(rfc8785.dumps(body['input'])).hexdigest()==arm['input_sha256']):
            # Native retrying commits the database/outcome before running these
            # callbacks and returning the HTTP response. The process exits here;
            # no manual commit, public arming endpoint or production model hook.
            def exit_after_commit():
                marker='/tmp/mp-r1-fault-'+arm['nonce']
                try:fd=os.open(marker,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                except FileExistsError:return
                os.close(fd)
                if mode=='delay_after_commit':
                    os.write(2,('MP_R1_POSTCOMMIT_DELAY_START pid='+str(os.getpid())+' nonce='+arm['nonce']+'\n').encode())
                    time.sleep(8)
                    os.write(2,('MP_R1_POSTCOMMIT_DELAY_END pid='+str(os.getpid())+' nonce='+arm['nonce']+'\n').encode())
                    return
                os.write(2,('MP_R1_POSTCOMMIT_EXIT pid='+str(os.getpid())+' nonce='+arm['nonce']+'\n').encode())
                os._exit(86)
            request.env.cr.postcommit.add(exit_after_commit)
        return response
