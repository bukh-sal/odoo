"""Private operator retirement archive; ordinary sessions cannot mutate it."""
from odoo import api, fields, models
from odoo.exceptions import AccessError


class RetirementArchive(models.Model):
    _name = 'mp.retirement.archive'
    _description = 'Retired foundation data'
    _log_access = False
    _rec_name = 'table_name'

    operation_id = fields.Char(required=True, readonly=True, index=True)
    recipe = fields.Char(required=True, readonly=True)
    source_image = fields.Char(required=True, readonly=True)
    source_inventory = fields.Char(required=True, readonly=True)
    table_name = fields.Char(required=True, readonly=True)
    row_count = fields.Integer(required=True, readonly=True)
    sha256 = fields.Char(required=True, readonly=True)
    payload = fields.Text(required=True, readonly=True)
    _operation_table_unique = models.Constraint('UNIQUE(operation_id, table_name)',
        'A retirement table is archived once per operation.')

    @api.model_create_multi
    def create(self, values):
        raise AccessError('Retirement archives are imported only by the independent operator')

    def write(self, values):
        raise AccessError('Retirement archives are immutable')

    def unlink(self):
        raise AccessError('Retirement archives are immutable')
