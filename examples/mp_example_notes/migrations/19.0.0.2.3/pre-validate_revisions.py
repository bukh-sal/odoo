"""Validate previous CAS state and retain a digest before adding its SQL guard."""
import hashlib
import json


def migrate(cr,version):
    if not version:return
    cr.execute('SELECT count(*) FROM mp_example_note WHERE revision IS NULL OR revision<=0')
    if cr.fetchone()[0]:
        raise ValueError('Invalid previous note revision; reconcile instead of rewriting user data')
    cr.execute("SELECT COALESCE(jsonb_agg(to_jsonb(n) ORDER BY id),'[]'::jsonb) FROM mp_example_note n")
    digest=hashlib.sha256(json.dumps(cr.fetchone()[0],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    value=json.dumps({'from_native_version':version,'rows_sha256':digest},sort_keys=True)
    cr.execute("""INSERT INTO ir_config_parameter(key,value,create_uid,write_uid,create_date,write_date)
        VALUES ('mp.example.notes.migration.0.2.3.pre',%s,1,1,timezone('UTC',now()),timezone('UTC',now()))
        ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,write_date=EXCLUDED.write_date""",[value])
