from odoo import api, fields, models


class FixtureExtension(models.Model):
    _inherit = 'mp.r0.fixture'

    label = fields.Char()
    label_length = fields.Integer(compute='_compute_label_length', store=True)

    @api.depends('label')
    def _compute_label_length(self):
        for record in self:
            record.label_length = len(record.label or '')
