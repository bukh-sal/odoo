"""Normalize existing extension-owned values; base content/IDs are retained."""
import json
import logging


def migrate(cr,version):
    if not version:return
    cr.execute('SELECT id,x_notes_labels FROM mp_example_note ORDER BY id')
    changed=0
    for ident,labels in cr.fetchall():
        if labels is None:labels=[]
        if not isinstance(labels,list) or any(not isinstance(label,str) for label in labels):raise ValueError('Unrecognized previous labels; restore/reconcile instead of dropping data')
        normalized=[]
        for label in labels:
            label=label.strip().casefold()
            if not label or len(label)>64:raise ValueError('Previous label cannot be normalized safely')
            if label not in normalized:normalized.append(label)
        if normalized!=labels:
            cr.execute("UPDATE mp_example_note SET x_notes_labels=%s::jsonb,revision=revision+1,write_date=timezone('UTC',now()),write_uid=1 WHERE id=%s",[json.dumps(normalized),ident]);changed+=1
    logging.getLogger(__name__).info('Labels extension migration normalized %s records; base content/IDs retained',changed)
