"""Local presentation, language selection and ephemeral page lifecycle API."""
from pathlib import Path
import json
import time
from urllib.parse import urlparse
from typing import Annotated

from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field,StrictBool
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from babblet.languages import CATALOG, validate_targets
from babblet.speech_languages import (SpeechGuidance,SPEECH_CATALOG,load_speech_guidance,
    read_sync_policy,persist_speech_settings,sync_policy_path)
from babblet.audio_level import meter_snapshot
from babblet.activity import activity_snapshot,pending_activity_snapshot


class LanguageSelection(BaseModel):
    languages: list[str] = Field(min_length=1,max_length=6)


class SpeechSelection(BaseModel):
    languages: list[str] | None = Field(default=None,max_length=6)
    sync_with_display: StrictBool | None = None


class PageReceipt(BaseModel):
    utterance_id: str = Field(min_length=1,max_length=100)
    revision: int = Field(ge=1)
    consumed: dict[str,Annotated[int,Field(ge=0,le=100000)]] | None = Field(default=None,min_length=1,max_length=7)


class PageRollover(BaseModel):
    utterances: list[PageReceipt] = Field(min_length=1,max_length=100)


def create_app(pipeline, status=None, selection_path=None,guidance=None,speech_path=None):
    if guidance is None:
        guidance=load_speech_guidance(pipeline.targets,speech_path)
    elif not getattr(guidance,'startup_configured',False):
        policy_path=sync_policy_path(speech_path)
        if policy_path is not None and policy_path.exists():
            guidance.sync_with_display=read_sync_policy(speech_path)
        guidance.sync_display(pipeline.targets)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware,
        allowed_hosts=['127.0.0.1', 'localhost', '[::1]', 'testserver'])
    static = Path(__file__).parent / 'static'
    app.mount('/flags',StaticFiles(directory=static/'flags',check_dir=False),name='flags')
    app.mount('/art',StaticFiles(directory=static/'art',check_dir=False),name='art')

    @app.middleware('http')
    async def local_only(request: Request, call_next):
        origin = request.headers.get('origin')
        if origin and urlparse(origin).netloc != request.headers.get('host'):
            return JSONResponse({'error': 'Foreign origin'}, status_code=403)
        response = await call_next(request)
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'")
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.get('/')
    def index():
        return FileResponse(static / 'index.html')

    @app.get('/app.js')
    def script():
        return FileResponse(static / 'app.js', media_type='application/javascript')

    @app.get('/style.css')
    def style():
        return FileResponse(static / 'style.css', media_type='text/css')

    @app.get('/paper.mjs')
    def paper():
        return FileResponse(static/'paper.mjs',media_type='application/javascript')

    @app.get('/api/snapshot')
    async def snapshot():
        trace=(status or {}).get('recognition_trace')
        if trace and time.time()-trace.get('updated_at',0)>60:
            trace.clear()
        result = pipeline.snapshot()
        result['input'] = status or {}
        result['speech'] = guidance.snapshot()
        result['pending_activity']=pending_activity_snapshot(pipeline,status)
        result['translation_activity']=pipeline.active_translation
        return result

    @app.get('/api/languages')
    async def languages():
        return {'available':list(CATALOG.values()),'selected':list(pipeline.targets)}

    @app.get('/api/tablet')
    async def tablet():
        result=pipeline.tablet.snapshot(pipeline.targets)
        result['languages']=list(CATALOG.values())
        result['speech_languages']=list(SPEECH_CATALOG.values())
        result['expected_languages']=list(guidance.expected)
        result['sync_with_display']=guidance.sync_with_display
        result['pending_activity']=pending_activity_snapshot(pipeline,status)
        result['translation_activity']={key:pipeline.active_translation.get(key) for key in ('target','utterance_id')} if pipeline.active_translation else None
        return result

    @app.get('/api/speech-languages')
    async def speech_languages():
        return {'available':list(SPEECH_CATALOG.values()),**guidance.snapshot()}

    @app.post('/api/speech-languages')
    async def select_speech(selection: SpeechSelection,request: Request):
        origin=request.headers.get('origin')
        if not origin or urlparse(origin).netloc!=request.headers.get('host'):
            raise HTTPException(403,'Same-origin request required')
        try:
            if selection.languages is None and selection.sync_with_display is None:
                raise ValueError('Choose languages or a sync policy')
            if selection.languages is not None:
                SpeechGuidance(selection.languages)
            enabled=selection.sync_with_display
            if enabled is None:
                enabled=False
            if enabled:
                expected=[code for code in pipeline.targets if code in SPEECH_CATALOG]
            else:
                expected=selection.languages if selection.languages is not None else guidance.expected
            validated=SpeechGuidance(expected).expected
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc
        persist_speech_settings(speech_path,validated,enabled)
        guidance.sync_with_display=enabled
        guidance.set_expected(validated)
        pipeline.sequence+=1
        return guidance.snapshot()

    @app.post('/api/rollover')
    async def rollover(receipt: PageRollover,request: Request):
        origin = request.headers.get('origin')
        if not origin or urlparse(origin).netloc != request.headers.get('host'):
            raise HTTPException(403,'Same-origin request required')
        return {'discarded':pipeline.discard([item.model_dump() for item in receipt.utterances])}

    @app.post('/api/languages')
    async def select_languages(selection: LanguageSelection,request: Request):
        origin = request.headers.get('origin')
        if not origin or urlparse(origin).netloc != request.headers.get('host'):
            raise HTTPException(403,'Same-origin request required')
        try:
            targets = validate_targets(selection.languages)
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc
        if selection_path is not None:
            path = Path(selection_path)
            path.parent.mkdir(parents=True,exist_ok=True)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(list(targets)),encoding='utf-8')
            temporary.replace(path)
        await pipeline.set_targets(targets)
        if guidance.sync_with_display:
            guidance.sync_display(targets)
            persist_speech_settings(speech_path,guidance.expected,True)
        return {'selected':list(pipeline.targets)}

    @app.get('/healthz')
    async def health():
        return {'pipeline': pipeline.snapshot()['health'], 'input': status or {}}

    @app.get('/api/audio-level')
    async def audio_level():
        return meter_snapshot(status)

    @app.get('/api/processing')
    async def processing():
        return activity_snapshot(pipeline,status)

    return app
