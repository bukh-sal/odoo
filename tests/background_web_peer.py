"""Runs inside a disposable Linux edge-network client, with no database mount."""
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from http.cookies import SimpleCookie
import json
import math
from statistics import median
import sys
from threading import Barrier
import time


def summary(samples):
    return dict(count=len(samples),median_ms=round(median(samples),3),
                p95_ms=round(sorted(samples)[math.ceil(len(samples)*.95)-1],3),
                max_ms=round(max(samples),3))


class Session:
    def __init__(self,settings):
        self.settings=settings
        self.connection=HTTPConnection('edge',8069,timeout=30)
        self.cookie=None
        self.token=None
        value=self.json('/web/session/authenticate',dict(db=settings['database'],login=settings['login'],
                         password=settings['password']))
        assert value['result']['uid']==settings['uid']
        self.token=self.json('/api/v1/client-release')['data']['token']

    def json(self,path,params=None):
        headers={'Host':self.settings['host']}
        if self.cookie:headers['Cookie']=self.cookie
        if self.token:headers['X-MP-Client-Release']=self.token
        if params is not None:
            headers.update({'Content-Type':'application/json','X-MP-Workspace':self.settings['workspace']})
        self.connection.request('POST' if params is not None else 'GET',path,
            body=json.dumps(dict(jsonrpc='2.0',method='call',id=1,params=params)) if params is not None else None,
            headers=headers)
        with self.connection.getresponse() as response:
            cookie=response.getheader('Set-Cookie')
            if cookie:
                parsed=SimpleCookie(cookie)
                if 'session_id' in parsed:self.cookie='session_id='+parsed['session_id'].value
            assert response.status==200,response.status
            return json.loads(response.read())

    def read(self,case):
        if case=='list':
            method='web_search_read'
            args=[]
            kwargs=dict(domain=[],offset=0,limit=80,specification={name:{} for name in ('title','revision','write_date')})
        else:
            method='web_read'
            args=[[self.settings['note']]]
            kwargs=dict(specification={name:{} for name in ('title','body','revision')})
        value=self.json('/web/dataset/call_kw/mp.example.note.'+method,
            dict(model='mp.example.note',method=method,args=args,kwargs=kwargs))['result']
        if case=='list':
            assert len(value['records'])==80 and all(row['title'].startswith('BG benchmark ') for row in value['records'])
        else:
            row,=value
            assert row['id']==self.settings['note'] and len(row['body'])==9600


def emit(**fields):
    print(json.dumps(fields,sort_keys=True),flush=True)


def main():
    settings=json.loads(sys.stdin.readline())
    clients=[]
    for _ in range(20):
        clients.append(Session(settings))
        # Respect the normal edge login budget.
        time.sleep(.12)
    emit(state='ready',sessions=len(clients))
    sockets=None
    with ThreadPoolExecutor(max_workers=20) as pool:
        for line in sys.stdin:
            command=line.strip()
            if command=='warm':
                for client in clients:client.connection.close()
                for case in ('list','detail'):
                    list(pool.map(lambda client:client.read(case),clients))
                    time.sleep(1.20)
                sockets=[client.connection.sock for client in clients]
                assert all(sockets)
                emit(state='warm')
            elif command=='measure':
                assert sockets
                values={'list':[],'detail':[]}
                rounds=[]
                for _ in range(10):
                    for case in values:
                        barrier=Barrier(20)
                        def timed(client):
                            barrier.wait(timeout=12)
                            start=time.perf_counter()
                            client.read(case)
                            return (time.perf_counter()-start)*1000
                        measured=list(pool.map(timed,clients))
                        values[case].extend(measured)
                        rounds.append({'case':case,**summary(measured)})
                        time.sleep(1.20)
                reused=sum(client.connection.sock is sock for client,sock in zip(clients,sockets,strict=True))
                for client in clients:client.connection.close()
                sockets=None
                emit(state='measured',reused=reused,cases={k:summary(v) for k,v in values.items()},rounds=rounds)
            elif command=='quit':
                break
            else:
                raise ValueError('Unknown qualification command')


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        # Do not print credentials, cookies, request or response payloads.
        emit(state='failed',error=type(error).__name__)
        sys.exit(1)
