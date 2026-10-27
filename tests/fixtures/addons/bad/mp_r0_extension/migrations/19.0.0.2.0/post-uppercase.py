from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for record in env['mp.r0.fixture'].search([]):
        record.label = (record.label or '').upper()
