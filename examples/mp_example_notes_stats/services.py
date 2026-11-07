from odoo.addons.mp_core.registry import Method,register
from .contracts import OUTPUT

class AnalysisService:
    # The two frozen document input definitions have exactly the required
    # Note identity/revision shapes. No shared contract change is necessary.
    methods={
        'analyze':Method('mp.example.notes.stats','_mp_service_analyze','delete_input','documents.schema.json','org.example.notes_stats:analysis.run',True,'read',OUTPUT),
        'status':Method('mp.example.notes.stats','_mp_service_analysis_status','get_input','documents.schema.json','org.example.notes_stats:analysis.run',False,'read',OUTPUT),
    }

register('org.example.notes_stats.jobs','1.0','org.example.notes_stats',AnalysisService.methods)
