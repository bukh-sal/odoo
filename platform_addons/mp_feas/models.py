from uuid import uuid4

from odoo import fields, models


class FeasibilityRecord(models.Model):
    _name = "mp.feas.record"
    _inherit = "mp.workspace.scoped"
    _description = "Disposable G1 workspace record"
    _mp_plugin_id = "org.example.feasibility"

    name = fields.Char(required=True)
    public_id = fields.Char(required=True, default=lambda self: str(uuid4()), readonly=True, index=True)
    amount = fields.Integer(default=0)
    peer_id = fields.Many2one("mp.feas.record", ondelete="set null")
    peer_ids = fields.Many2many("mp.feas.record", "mp_feas_peer_rel", "owner_id", "peer_id")
    _public_id_unique = models.Constraint("UNIQUE(public_id)", "Public object ID must be unique")
