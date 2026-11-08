"""Complete stage choices without rewriting existing stage/task identities."""


def migrate(cr,version):
    for name,sequence,done in [('To do',10,False),('Done',20,True)]:
        cr.execute("""INSERT INTO mp_aurora_task_stage(name,list_id,sequence,done,
            create_uid,write_uid,create_date,write_date)
            SELECT %s,l.id,%s,%s,1,1,timezone('UTC',now()),timezone('UTC',now()) FROM mp_aurora_task_list l
            WHERE NOT EXISTS(SELECT 1 FROM mp_aurora_task_stage s WHERE s.list_id=l.id AND s.done=%s)""",
            [name,sequence,done,done])
