import json
from odoo.addons.mp_core.registry import Method,register
from modular_platform.contracts import CONTRACTS
_board=json.loads((CONTRACTS/'boards.schema.json').read_text())['$defs']['board']
class BoardsService:
    methods={name:Method('mp.example.canvas.board','_mp_service_'+name,name+'_input','boards.schema.json','org.example.canvas:canvas.'+('read' if name=='get' else 'write'),name=='save','read' if name=='get' else 'write',_board) for name in ['get','save']}
register('org.example.canvas.boards','1.0','org.example.canvas',BoardsService.methods)
