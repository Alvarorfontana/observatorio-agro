"""Adaptador WorldPop API v2: geometría -> tarea asíncrona -> total poblacional."""
import json
import os
import re
from urllib.request import Request,urlopen

BASE='https://api.worldpop.org/v2'


class UpstreamError(RuntimeError):
    pass


def call(path, payload=None):
    headers={'Accept':'application/json','User-Agent':'DOTS-Population/1.0'}
    if os.environ.get('WORLDPOP_API_KEY'): headers['X-API-Key']=os.environ['WORLDPOP_API_KEY']
    body=None
    if payload is not None:
        headers['Content-Type']='application/json';body=json.dumps(payload).encode()
    try:
        req=Request(BASE+path,data=body,headers=headers)
        with urlopen(req,timeout=25) as response:
            raw=response.read(2*1024*1024+1)
        if len(raw)>2*1024*1024: raise ValueError('too large')
        result=json.loads(raw)
        if not isinstance(result,dict): raise ValueError('invalid response')
        return result
    except Exception:
        raise UpstreamError('WorldPop no respondió correctamente. Reintentá más tarde.') from None


def submit(geometry,year,transport=call):
    result=transport('/population',{'geojson':geometry,'year':year,'resolution':'100m'})
    task=result.get('task_id')
    if not isinstance(task,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',task):
        raise UpstreamError('WorldPop no devolvió un identificador de tarea válido.')
    return task


def poll(task,transport=call):
    if not isinstance(task,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',task):
        raise UpstreamError('Identificador de tarea inválido.')
    result=transport('/tasks/'+task)
    status=result.get('status')
    if status in ('pending','processing','running','started','queued'):
        return {'status':'pending'}
    if status in ('failure','failed','error'):
        raise UpstreamError('WorldPop no pudo completar el cálculo para esta zona.')
    if status!='success':
        raise UpstreamError('Estado de WorldPop no reconocido.')
    value=result.get('result',{}).get('total_population')
    import math
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
        raise UpstreamError('WorldPop no devolvió una estimación poblacional válida.')
    return {'status':'complete','population':float(value)}
