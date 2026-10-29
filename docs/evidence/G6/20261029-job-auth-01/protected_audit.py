"""Reuse the existing read-only protected G5 audit without rerunning setup."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];source=ROOT/'docs/evidence/G5/20261029-http-security-02/audit.py';code=source.read_text()
old="dest=OUTPUT/'final-audit-native.json'";new="dest=ROOT/'docs/evidence/G6/20261029-job-auth-01/protected-audit.json'"
assert code.count(old)==1
scope={'__file__':str(source),'__name__':'job_protected_audit'}
exec(compile(code.replace(old,new),str(source),'exec'),scope);scope['main']()
