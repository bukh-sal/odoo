"""Trusted native shared-table extension; suspension never unloads its fields."""
import json
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.mp_identity.scopes import current_scope
from odoo.addons.mp_example_notes.models import Note as BaseNote
from odoo.addons.mp_core.dispatch import call_bound


class Labels(models.Model):
    _inherit='mp.example.note'
    x_notes_labels=fields.Json(default=list,copy=True)

    def _labels_available(self):
        scope=current_scope(self.env)
        self.env.cr.execute("""SELECT 1 FROM mp_workspace_plugin f JOIN mp_plugin_installation i ON i.id=f.installation_id
            WHERE f.workspace_id=%s AND i.plugin_id='org.example.notes_labels' AND i.state='installed' AND f.availability='enabled'""",[scope.workspace_id])
        return bool(self.env.cr.fetchone())

    def _labels_guard(self,action='read'):
        scope=self._mp_guard(action)
        if not self._labels_available():raise AccessError('Labels feature unavailable')
        return scope

    @staticmethod
    def _clean_labels(value):
        if not isinstance(value,list) or len(value)>30 or any(not isinstance(label,str) or not label.strip() or len(label)>64 for label in value):raise ValidationError('Invalid labels')
        result=[label.strip() for label in value]
        if len(set(result))!=len(result):raise ValidationError('Labels must be unique')
        return result

    def read(self,fields=None,load='_classic_read'):
        if fields is None or 'x_notes_labels' in fields:self._labels_guard()
        return super().read(fields,load=load)

    @api.model
    def _has_field_access(self,field,operation):
        # Supported native field-access seam also filters automatic prefetch.
        # Guarding fetch's candidate list denied base fields merely because
        # native prefetch included this extension's stored field.
        if field.name=='x_notes_labels' and not self.env.su:
            scope=current_scope(self.env,required=False)
            if not scope or not self._labels_available():return False
            if operation=='write' and (scope.role=='viewer' or scope.allowed_actions is not None and 'write' not in scope.allowed_actions):return False
        return super()._has_field_access(field,operation)

    @api.model_create_multi
    def create(self,values_list):
        clean=[];labels=[]
        for value in values_list:
            value=dict(value);present='x_notes_labels' in value
            if present:self._labels_guard('create')
            labels.append(self._clean_labels(value.pop('x_notes_labels')) if present else None);clean.append(value)
        records=super().create(clean)
        for record,value in zip(records,labels):
            if value is not None:super(BaseNote,record).write({'x_notes_labels':value})
        return records

    def write(self,values):
        values=dict(values)
        if 'x_notes_labels' not in values:return super().write(values)
        self._labels_guard('write');labels=self._clean_labels(values.pop('x_notes_labels'))
        # Supported trusted-native extension adapter: base write owns its CAS
        # and revision increment. Then cooperative native ORM writes only this
        # extension's validated field; same transaction, same actor and guards.
        result=super().write(values)
        super(BaseNote,self).write({'x_notes_labels':labels})
        return result

    def _dto(self):
        value=super()._dto()
        if self._labels_available():value['labels']=self._clean_labels(self.x_notes_labels or [])
        return value

    @api.model
    def _mp_service_set_labels(self,values):
        self._labels_guard('write')
        base=call_bound(self.env,'documents','get',{'note_id':values['note_id']})
        record=self._expected({'note_id':base['id'],'expected_revision':values['expected_revision']},'write')
        record.with_context(expected_revision=values['expected_revision']).write({'x_notes_labels':values['labels']})
        return record._dto()
