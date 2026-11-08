"""Native app availability supplements, never replaces, the native ACL/rules."""
from odoo import api,models
from odoo.addons.mp_core import native_jobs

PLUGIN='dev.aurora.tasks'
ADDON='mp_aurora_tasks'


class AuroraAccess(models.AbstractModel):
    _name='mp.aurora.access'
    _description='Aurora application availability'

    def _aurora_guard(self,operation='read'):
        if not self.env.su:
            native_jobs.require_application(self.env,PLUGIN,ADDON,lock=operation!='read')

    def check_access(self,operation):
        self._aurora_guard(operation)
        return super().check_access(operation)

    @api.model
    def _has_field_access(self,field,operation):
        if self._ids and operation=='read':self._aurora_guard()
        return super()._has_field_access(field,operation)

    @api.model
    def _search(self,domain,offset=0,limit=None,order=None,*,active_test=True,bypass_access=False):
        self._aurora_guard()
        return super()._search(domain,offset=offset,limit=limit,order=order,active_test=active_test,bypass_access=bypass_access)

    @api.readonly
    def web_read(self,specification):
        self._aurora_guard()
        return super().web_read(specification)

    @api.private
    def fetch(self,field_names=None):
        self._aurora_guard()
        return super().fetch(field_names)

    @api.model_create_multi
    def create(self,values):
        self._aurora_guard('create')
        return super().create(values)

    def write(self,values):
        self._aurora_guard('write')
        return super().write(values)

    def unlink(self):
        self._aurora_guard('unlink')
        return super().unlink()
