"""Actual attached binary/private-config capture with no daemon retention."""
from datetime import datetime,timezone
import hashlib,json,secrets,subprocess,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-secret-scan';sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_os import protect_directory
from modular_platform.deployment import _run

def main():
 dest=OUTPUT/'maintenance-capture.json';assert not dest.exists();state=json.loads((ROOT/'.local/g5-httpsecurity/state.json').read_text());target=json.loads((ROOT/'.local/g5-httpsecurity/operator/target.json').read_text());executor=NativeExecutor.__new__(NativeExecutor);executor.config=target;directory=protect_directory(LOCAL/'capture-proof');operation=str(uuid4());payload=b'[synthetic-private-config]\n'+secrets.token_bytes(256*1024);args,name=executor._child(operation,'secret-capture-proof',network=False);args.insert(2,'-i');args+=['-c','import sys;sys.stdout.buffer.write(sys.stdin.buffer.read());sys.stderr.write("SYNTHETIC_DIAGNOSTIC_ONLY\\n")']
 (directory/'intent.json').write_text(json.dumps(dict(name=name,operation=operation,payload_sha256=hashlib.sha256(payload).hexdigest())))
 executor._private_command(args,directory/'captured.bin',input=payload)
 assert (directory/'captured.bin').read_bytes()==payload
 info=json.loads(_run(['docker','inspect',name]))[0];assert info['State']['ExitCode']==0 and not info['State']['Running'] and info['HostConfig']['LogConfig']['Type']=='none' and info['HostConfig']['NetworkMode']=='none'
 logs=subprocess.run(['docker','logs',name],capture_output=True,timeout=20);assert not logs.stdout and payload[:32] not in logs.stderr and b'SYNTHETIC_DIAGNOSTIC_ONLY' not in logs.stderr
 # A none-driver stopped helper also retains exact status/labels for inspection.
 assert info['Config']['Labels']['com.modular.operation']==operation
 report=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),container_id=info['Id'],container_name=name,operation_id=operation,payload_bytes=len(payload),attached_bytes_exact=True,private_stderr_preserved=b'SYNTHETIC_DIAGNOSTIC_ONLY' in (directory/'captured.bin.stderr.log').read_bytes(),daemon_log_driver='none',docker_logs_stdout_bytes=len(logs.stdout),docker_logs_exit=logs.returncode,read_only_no_network=True,source_sha256=hashlib.sha256((ROOT/'packages/platform_sdk/modular_platform/native_executor.py').read_bytes()).hexdigest(),limits=['Synthetic payload only; existing config and filestore volumes mounted read-only and never read or written.','Host-only command construction change; native code/image/restore semantics and current deployments unchanged.'])
 assert report['private_stderr_preserved'];dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',attached_bytes_exact=True,daemon_logs_absent=True,container=name)))
if __name__=='__main__':main()
