"""Small tablet presentation and SSH-tunnel-only network gateway.

No model inference, recording, inspector data or arbitrary proxy routes are
exposed by this service. Only its six current display rows are retained.
"""
import argparse
import copy
import hmac
import json
import secrets
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field,StrictBool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from babblet.languages import CATALOG,validate_targets
from babblet.speech_languages import SpeechGuidance


class TabletPresentation:
    def __init__(self,count=6):
        self.count=count
        self.session=uuid.uuid4().hex
        self.sequence=0
        self.slots=[None]*count

    def publish(self,item):
        if item.get('phase') not in ('final','unrefined') or item.get('display_only'):
            return
        index=item['display_index']
        slot=(index-1)%self.count
        current=self.slots[slot]
        if current and (current['display_index']>index or
                (current['display_index']==index and current['revision']>item['revision'])):
            return
        # Copy only the bounded presentation fields; never share mutable pipeline
        # dictionaries with the browser's discard/prefix-trimming lifecycle.
        value={key:copy.deepcopy(item[key]) for key in (
            'utterance_id','display_index','revision','source_text','source_language','translations','phase')}
        if current!=value:
            self.slots[slot]=value
            self.sequence+=1

    def snapshot(self,languages):
        return copy.deepcopy({'session':self.session,'sequence':self.sequence,
            'slot_count':self.count,'selected_languages':list(languages),'slots':self.slots})

    def retire(self,uid):
        for row in self.slots:
            if row and row['utterance_id']==uid:
                for result in row['translations'].values():
                    if result['status']=='pending':
                        result['status']='skipped'
                        self.sequence+=1


class Selection(BaseModel):
    mode: str
    languages: list[str] | None=Field(default=None,max_length=6)
    enabled: StrictBool | None=None


class LocalSource:
    def __init__(self,base_url='http://127.0.0.1:8090'):
        if base_url!='http://127.0.0.1:8090':
            raise ValueError('Tablet source must be the local Babblet service')
        self.base_url=base_url

    async def snapshot(self):
        async with httpx.AsyncClient(timeout=3,trust_env=False) as client:
            result=await client.get(self.base_url+'/api/tablet')
            result.raise_for_status()
            return result.json()

    async def select(self,mode,languages):
        route='/api/languages' if mode=='display' else '/api/speech-languages'
        async with httpx.AsyncClient(timeout=5,trust_env=False) as client:
            result=await client.post(self.base_url+route,headers={'Origin':self.base_url},
                json={'languages':languages})
            result.raise_for_status()
            return result.json()

    async def set_sync(self,enabled):
        async with httpx.AsyncClient(timeout=5,trust_env=False) as client:
            result=await client.post(self.base_url+'/api/speech-languages',
                headers={'Origin':self.base_url},json={'sync_with_display':enabled})
            result.raise_for_status()
            return result.json()


def create_bridge(token,source=None):
    if not isinstance(token,str) or len(token)<32:
        raise ValueError('Use a randomly generated tablet token of at least 32 characters')
    source=source or LocalSource()
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])

    @app.middleware('http')
    async def private_tablet_only(request:Request,call_next):
        # Native QML requests need no browser origin. Reject cross-site browser
        # requests even if a future web client accidentally leaks its token.
        if request.headers.get('origin'):
            return JSONResponse({'error':'Native tablet connection required'},status_code=403)
        supplied=request.headers.get('authorization','')
        if not hmac.compare_digest(supplied.encode(),('Bearer '+token).encode()):
            return JSONResponse({'error':'Tablet authentication required'},status_code=401)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response

    @app.get('/v1/display')
    async def display():
        try:
            return await source.snapshot()
        except (httpx.HTTPError,ValueError):
            raise HTTPException(503,'Main computer is reconnecting')

    @app.post('/v1/languages')
    async def languages(selection:Selection):
        try:
            if selection.mode=='display':
                if selection.languages is None:
                    raise ValueError('Choose display languages')
                validate_targets(selection.languages)
            elif selection.mode=='speech':
                if selection.languages is None:
                    raise ValueError('Choose speech languages')
                SpeechGuidance(selection.languages)
            elif selection.mode=='sync':
                if selection.enabled is None:
                    raise ValueError('Choose whether language sync is enabled')
            else:
                raise ValueError('Choose display or speech languages')
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc
        try:
            if selection.mode=='sync':
                return await source.set_sync(selection.enabled)
            return await source.select(selection.mode,selection.languages)
        except (httpx.HTTPError,ValueError):
            raise HTTPException(503,'Language settings could not be saved')

    return app


def read_token(path):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_urlsafe(32),encoding='ascii')
    token=path.read_text(encoding='ascii').strip()
    if len(token)<32:
        raise ValueError('Tablet token must contain at least 32 characters')
    return token


def main():
    parser=argparse.ArgumentParser(description='Babblet tablet gateway, loopback only; use an SSH reverse tunnel')
    parser.add_argument('--port',type=int,default=8092)
    parser.add_argument('--token-file',default='runtime/tablet.key')
    args=parser.parse_args()
    import uvicorn
    uvicorn.run(create_bridge(read_token(args.token_file)),host='127.0.0.1',port=args.port,
                log_level='warning',access_log=False)


if __name__=='__main__':
    main()
