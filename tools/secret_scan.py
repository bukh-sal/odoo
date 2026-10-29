"""Redacted release audit primitives; no values/lines are emitted in findings.

Known generated credentials supplement structural detection. Ripgrep is used
for the full byte search; precise candidate locations are inspected locally.
This tool never imports scanned code or extracts archive-selected paths.
"""
import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import re
import subprocess


RULES={
    'private-key-marker':rb'-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----',
    'credential-literal':rb'''(?i)\b(?:password|passwd|db_password|admin_passwd|api_key|client_secret|access_token|refresh_token|csrf_token)\b["']?\s*[:=]\s*["'][^"'\r\n]{8,512}["']''',
    'credential-url':rb'''(?i)(?:https?|postgres(?:ql)?|redis|amqp)://[^\s/@:"']{1,128}:[^\s/@"']{8,256}@''',
    'cloud-token':rb'\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[0-9A-Za-z]{20,255}|sk-(?:proj-)?[0-9A-Za-z_-]{24,255})\b',
    'session-cookie-literal':rb'''(?i)\bsession_id\s*[=:]\s*["']?[0-9a-f]{32,128}\b''',
    'HTML-session-token':rb'''(?i)name=["'](?:csrf_token|session_id)["'][^>\r\n]{0,200}\bvalue=["'][^"'\r\n]{16,512}["']''',
}


def is_credential_file(name,data):
    """Only small one-line operator files, never password UI/source modules."""
    name=name.lower()
    eligible=(not Path(name).suffix and (name.endswith('-password') or name=='password' or name.startswith('password-') or name in ('service-token','bearer-token'))) or name in ('password.txt','bootstrap-password.txt')
    value=data.strip()
    return eligible and 16<=len(value)<=256 and b'\n' not in value and b'\r' not in value


@dataclass
class Scanner:
    key:bytes
    values:dict

    def __post_init__(self):
        self.patterns={}
        for label,value in self.values.items():
            if not isinstance(value,bytes) or len(value)<16:raise ValueError('Explicit known credential bytes, minimum16, required')
            raw_parts=[value] if b'\n' not in value else [v for v in value.splitlines() if len(v)>=32 and not v.startswith(b'-----')]
            for raw in raw_parts:
                variants={raw,base64.b64encode(raw),raw.hex().encode()}
                # Detect a scalar inside base64-encoded JSON at all alignments.
                for offset in (0,1,2):
                    encoded=base64.b64encode(b' '*offset+raw);inner=encoded[4:-4]
                    if len(inner)>=24:variants.add(inner)
                try:
                    text=raw.decode('utf8');variants|={text.encode('utf-16le'),text.encode('utf-16be')}
                except UnicodeError:pass
                for variant in variants:self.patterns.setdefault(variant,set()).add(label)
        self.known=re.compile(b'|'.join(re.escape(v) for v in sorted(self.patterns,key=len,reverse=True))) if self.patterns else None
        self.generic={name:re.compile(value) for name,value in RULES.items()}
        self.overlap=max([2048,*map(len,self.patterns)])

    def fingerprint(self,value):return hmac.new(self.key,value,hashlib.sha256).hexdigest()[:24]

    def redact_location(self,value):
        for raw in self.patterns:
            try:text=raw.decode('utf8')
            except UnicodeError:continue
            if len(text)>=16 and text in value:value=value.replace(text,'<redacted>')
        return value

    def inspect_bytes(self,data,location,*,offset=0):
        findings=[];location=self.redact_location(location)
        if self.known:
            for match in self.known.finditer(data):
                findings.append(dict(location=location,offset=offset+match.start(),rule='known-generated-secret',secret_sources=sorted(self.patterns[match.group()]),fingerprint=self.fingerprint(match.group())))
        for name,pattern in self.generic.items():
            for match in pattern.finditer(data):findings.append(dict(location=location,offset=offset+match.start(),rule=name,fingerprint=self.fingerprint(match.group())))
        return findings

    def inspect_file(self,path,location=None):
        findings=[];tail=b'';position=0
        with Path(path).open('rb') as stream:
            while chunk:=stream.read(4*1024*1024):
                findings+=self.inspect_bytes(tail+chunk,location or str(path),offset=position-len(tail));position+=len(chunk);tail=(tail+chunk)[-self.overlap:]
        unique={(f['offset'],f['rule'],f['fingerprint']):f for f in findings}
        return list(unique.values())

    def write_patterns(self,path):
        # Hex escapes represent NULs in UTF16 values without embedding NULs in
        # a pattern file or relying on decoding/BOM heuristics. No multiline
        # known values are needed: complete private-key body lines are covered.
        known=b'|'.join(b''.join(('\\x%02x'%byte).encode() for byte in value) for value in self.patterns)
        value=(known+b'\n' if known else b'')+b'\n'.join(RULES.values())+b'\n'
        with Path(path).open('xb') as stream:stream.write(value)

    def candidates(self,paths,pattern_file):
        """Bound Windows command length; ripgrep returns names, never values."""
        result=[];batch=[];length=0
        def run(names):
            if not names:return
            args=['rg','--text','--no-unicode','--encoding','none','--files-with-matches','--null','--no-messages','--regex-size-limit','100M','-f',str(pattern_file),'--',*names]
            completed=subprocess.run(args,capture_output=True,timeout=120)
            if completed.returncode not in (0,1):raise RuntimeError('Byte scan failed; inspect private diagnostics without echoing patterns')
            result.extend(n.decode('utf8') for n in completed.stdout.split(b'\0') if n)
        for path in paths:
            name=str(path)
            if length+len(name)+3>18000:run(batch);batch=[];length=0
            batch.append(name);length+=len(name)+3
        run(batch);return result

    def scan_paths(self,paths,pattern_file,*,root=None):
        findings=[]
        for path in self.candidates(paths,pattern_file):
            label=Path(path).relative_to(root).as_posix() if root else str(path)
            findings.extend(self.inspect_file(path,label))
        return findings


def save_report(path,report):
    # Deliberately no raw match, source-line or captured request/body field.
    if any('value'==k or 'match'==k or 'line'==k for f in report.get('findings',[]) for k in f):raise ValueError('Raw finding fields forbidden')
    with Path(path).open('x',encoding='utf8') as stream:stream.write(json.dumps(report,indent=2)+'\n')
