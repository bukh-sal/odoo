from odoo import api, fields, models


class FixtureExtension(models.Model):
    _inherit = 'mp.r0.fixture'

    label = fields.Char()
