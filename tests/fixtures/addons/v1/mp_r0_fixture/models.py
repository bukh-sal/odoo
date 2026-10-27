from odoo import fields, models


class Fixture(models.Model):
    _name = 'mp.r0.fixture'
    _description = 'Disposable foundation lifecycle fixture'

    name = fields.Char(required=True)
    revision = fields.Integer(default=1, required=True)
