# Part of Odoo. See LICENSE and COPYRIGHT.
from odoo import fields, models


class MailMail(models.Model):
    _inherit = "mail.mail"
    fetchmail_server_id = fields.Many2one('fetchmail.server', "Inbound Mail Server", readonly=True, index='btree_not_null')
