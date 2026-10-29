"""Real process contention across deployment/site locks, including disjoint work."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from uuid import UUID

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import OperationLocks,LockBusy,protect_directory

WORKER="""import json,os,pathlib,sys
sys.path.insert(0,sys.argv[1])
from modular_platform.operator_os import OperationLocks,LockBusy
directory,deployment,sites,result=sys.argv[2:]
assert sys.stdin.buffer.read(1)==b'G'
def report(value):
 p=pathlib.Path(result);t=p.with_suffix('.tmp');t.write_text(json.dumps(dict(value,pid=os.getpid())),encoding='utf8');os.replace(t,p)
try:
 with OperationLocks(directory,deployment,json.loads(sites)) as locks:
  report(dict(state='acquired',owners=locks.check()))
  assert sys.stdin.buffer.read(1)==b'R'
  locks.check()
except LockBusy:
 report(dict(state='busy'))
"""


class OperatorConcurrency(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=protect_directory(Path(self.temp.name)/'locks');self.children=[]
        self.addCleanup(self.finish_children)

    def finish_children(self):
        for child in self.children:
            if child.poll() is None:child.kill()
            child.communicate(timeout=15)

    def child(self,deployment,sites):
        result=Path(self.temp.name)/('result'+str(len(self.children))+'.json')
        env=dict(os.environ)
        if os.name=='nt':env['PYTHONPATH']=str(Path(sys.executable).parents[1]/'Lib/site-packages')
        executable=sys._base_executable if os.name=='nt' else sys.executable
        child=subprocess.Popen([executable,'-c',WORKER,str(ROOT/'packages/platform_sdk'),str(self.directory),deployment,json.dumps(sites),str(result)],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.children.append(child);return child,result

    def observe(self,child,result):
        deadline=time.monotonic()+30
        while not result.exists():
            if child.poll() is not None:
                _,error=child.communicate();self.fail('Lock child exited before observation: '+error.decode(errors='replace'))
            if time.monotonic()>deadline:self.fail('Lock child observation deadline exceeded')
            time.sleep(.03)
        value=json.loads(result.read_text(encoding='utf8'));self.assertEqual(value['pid'],child.pid);return value

    def start(self,child):child.stdin.write(b'G');child.stdin.flush()

    def release(self,child):
        _,error=child.communicate(input=b'R',timeout=30);self.assertEqual(child.returncode,0,error.decode(errors='replace'))

    def test_same_deployment_different_sites_rejects_competing_process(self):
        with OperationLocks(self.directory,uid(1),[uid(10)]):
            child,result=self.child(uid(1),[uid(11)]);self.start(child)
            self.assertEqual(self.observe(child,result)['state'],'busy');self.release(child)

    def test_shared_site_rejects_other_deployment_and_releases_partial_lock(self):
        with OperationLocks(self.directory,uid(1),[uid(10)]):
            child,result=self.child(uid(2),[uid(10)]);self.start(child)
            self.assertEqual(self.observe(child,result)['state'],'busy');self.release(child)
            with OperationLocks(self.directory,uid(2),[uid(11)]) as available:self.assertEqual(len(available.check()),2)

    def test_disjoint_deployment_and_site_can_progress_independently(self):
        with OperationLocks(self.directory,uid(1),[uid(10)]):
            child,result=self.child(uid(2),[uid(11)]);self.start(child)
            self.assertEqual(self.observe(child,result)['state'],'acquired');self.release(child)

    def test_simultaneous_contenders_have_exactly_one_live_owner(self):
        first,a=self.child(uid(1),[uid(10)]);second,b=self.child(uid(1),[uid(10)])
        self.start(first);self.start(second)
        values=[self.observe(first,a),self.observe(second,b)]
        self.assertEqual(sorted(v['state'] for v in values),['acquired','busy'])
        with self.assertRaises(LockBusy):
            with OperationLocks(self.directory,uid(1),[uid(10)]):self.fail('Live winner lost exclusivity')
        self.release(first);self.release(second)
        with OperationLocks(self.directory,uid(1),[uid(10)]) as later:self.assertEqual(len(later.check()),2)


def uid(value):return str(UUID(int=value))


if __name__=='__main__':unittest.main()
