"""Require the new SQL invariant without changing existing note identities/data."""
import hashlib
import json


def migrate(cr,version):
    if not version:return
    cr.execute("SELECT convalidated FROM pg_constraint WHERE conrelid='mp_example_note'::regclass AND conname='mp_example_note_revision_positive'")
    if cr.fetchone()!=(True,):raise ValueError('Positive note revision constraint was not validated')
    cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.example.notes.migration.0.2.3.pre'")
    previous=json.loads(cr.fetchone()[0])
    cr.execute("SELECT COALESCE(jsonb_agg(to_jsonb(n) ORDER BY id),'[]'::jsonb) FROM mp_example_note n")
    digest=hashlib.sha256(json.dumps(cr.fetchone()[0],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if previous!={'from_native_version':version,'rows_sha256':digest}:
        raise ValueError('Note data changed during revision constraint migration')
    cr.execute("""INSERT INTO ir_config_parameter(key,value,create_uid,write_uid,create_date,write_date)
        VALUES ('mp.example.notes.migration.0.2.3.post',%s,1,1,timezone('UTC',now()),timezone('UTC',now()))
        ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,write_date=EXCLUDED.write_date""",[json.dumps(previous,sort_keys=True)])
