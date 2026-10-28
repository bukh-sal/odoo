import json
from odoo.addons.mp_core.registry import Method,register
from modular_platform.contracts import CONTRACTS
_note=json.loads((CONTRACTS/'documents.schema.json').read_text())['$defs']['note']
class LabelsService:
    methods={'set_labels':Method('mp.example.note','_mp_service_set_labels','labels_input','documents.schema.json','org.example.notes_labels:labels.write',True,'write',_note)}
register('org.example.notes_labels.labels','1.0','org.example.notes_labels',LabelsService.methods)
