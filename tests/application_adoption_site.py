"""Owned AP-02/03 disposable native application sites; never the retained pilot."""
import argparse
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'release'),str(ROOT/'packages/platform_sdk')]
from aurora_tasks_site import TasksSite,load,write


class AdoptionSite(TasksSite):
    def __init__(self,args):
        if not re.fullmatch(r'ap0[23]-[a-z0-9-]{1,45}',args.run):raise ValueError('Explicit disposable adoption identity required')
        self.args=args;self.local=ROOT/'.local/application-adoption'/args.run;self.private=self.local/'operator'

    def command(self,label,args,**kwargs):
        args=list(args)
        if args[:2]==['docker','run'] and '--name' in args and '--rm' not in args and '-d' not in args:args.insert(2,'--rm')
        return super().command(label,args,**kwargs)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('actions',nargs='+',choices=['prepare','initialize','install','verify_install','status','retire','verify_retirement'])
    p.add_argument('--run',required=True);p.add_argument('--port',type=int,required=True)
    p.add_argument('--candidate',type=Path,default=Path('.local/operator/builds/20261108-at04-core49-02.json'))
    a=p.parse_args();site=AdoptionSite(a)
    for phase in a.actions:getattr(site,phase)()
