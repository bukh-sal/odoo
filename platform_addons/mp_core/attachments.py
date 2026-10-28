"""R1 Notes/Canvas profile excludes attachments; legacy paths cannot add them."""
from odoo import api, models
from odoo.exceptions import AccessError


class Attachment(models.Model):
    _inherit='ir.attachment'

    def _mp_managed(self,name):
        return bool(name and name in self.env and getattr(self.env[name],'_mp_scoped',False))

    @api.model_create_multi
    def create(self,values_list):
        if any(self._mp_managed(v.get('res_model')) for v in values_list):
            raise AccessError('Attachments are not supported for workspace models in this R1 profile')
        return super().create(values_list)

    def write(self,values):
        if self._mp_managed(values.get('res_model')) or any(self._mp_managed(r.res_model) for r in self):
            raise AccessError('Attachments are not supported for workspace models in this R1 profile')
        return super().write(values)

    def _check_access(self,operation):
        # Defense in depth for operator-imported/old fixtures: public/token
        # attachment metadata never substitutes for workspace/model authority.
        # Metadata-only ownership preflight must not fetch attachment fields via
        # ORM here (fetch recursively invokes this access hook). No contents or
        # metadata are returned to callers; native ACL checks still run below.
        ids=[ident for ident in self.ids if isinstance(ident,int)]
        self.env.cr.execute('SELECT res_model,res_id FROM ir_attachment WHERE id=ANY(%s)',[ids])
        for model,ident in self.env.cr.fetchall():
            if self._mp_managed(model):
                self.env[model].browse(ident)._mp_guard('read' if operation=='read' else 'write')
                raise AccessError('Workspace attachments are unavailable in this R1 profile')
        return super()._check_access(operation)
