from uuid import uuid4
import json
from jsonschema import Draft202012Validator
from odoo import api,fields,models
from odoo.exceptions import AccessError,ValidationError,MissingError
from odoo.addons.mp_core.controllers import PublicError
from modular_platform.contracts import CONTRACTS

_board=json.loads((CONTRACTS/'boards.schema.json').read_text())['$defs']['board']


class Board(models.Model):
    _name='mp.example.canvas.board'
    _description='Workspace Canvas board'
    _inherit=['mp.workspace.scoped']
    _mp_plugin_id='org.example.canvas'
    public_id=fields.Char(default=lambda self:str(uuid4()),required=True,index=True,readonly=True)
    name=fields.Char(required=True,size=100)
    revision=fields.Integer(required=True,default=1,readonly=True)
    cards=fields.Json(default=list,required=True)
    _uuid_unique=models.Constraint('UNIQUE(public_id)','Board ID must be unique')
    _workspace_board=models.Constraint('UNIQUE(workspace_id)','One reference board per workspace')

    @api.constrains('public_id','name','revision','cards')
    def _validate_board(self):
        for board in self:
            if not Draft202012Validator(_board).is_valid(board._dto()) or not board.name.strip():raise ValidationError('Invalid board')
            if len({card['id'] for card in board.cards})!=len(board.cards):raise ValidationError('Duplicate card ID')
            for card in board.cards:
                if card['note_id'] and not self.env['mp.example.note'].search_count([('public_id','=',card['note_id'])]):raise MissingError('Referenced note unavailable')

    @api.model_create_multi
    def create(self,values_list):
        if any(set(value)-{'name','cards','workspace_id'} for value in values_list):raise AccessError('Invalid board creation fields')
        return super().create(values_list)

    def write(self,values):
        self._mp_guard('write')
        if set(values)-{'name','cards'}:raise AccessError('Invalid board update fields')
        self.env.cr.execute('SELECT id FROM mp_example_canvas_board WHERE id=ANY(%s) ORDER BY id FOR UPDATE',[self.ids]);self.invalidate_recordset(['revision'])
        for board in self:
            if board.revision!=self.env.context.get('expected_revision'):raise PublicError('CONFLICT',{'field':'revision','outcome':'not_started'})
            super(Board,board).write({**values,'revision':board.revision+1})
        return True

    def _dto(self):
        self.ensure_one();self._mp_guard('read')
        return {'id':self.public_id,'name':self.name,'revision':self.revision,'cards':self.cards or []}

    @api.model
    def _mp_service_get(self,values):
        board=self.search([('public_id','=',values['board_id'])] if values.get('board_id') else [],limit=1)
        if not board:raise MissingError('Board unavailable')
        return board._dto()

    @api.model
    def _mp_service_save(self,values):
        self._mp_guard('write');board=self.search([('public_id','=',values['board_id'])],limit=1)
        if not board:raise MissingError('Board unavailable')
        board.with_context(expected_revision=values['expected_revision']).write({'name':values['name'],'cards':values['cards']})
        return board._dto()
