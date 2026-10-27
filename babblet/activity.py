"""Content-free processing activity for the live display."""
import asyncio
import time

from babblet.languages import CATALOG


def pending_activity_snapshot(pipeline,status=None):
    """Stable, content-free cue for an utterance not ready to display yet."""
    status=status or {}
    phase=status.get('asr_phase')
    uid=status.get('asr_utterance_id') if phase in ('transcribing','refining') else None
    if phase in ('transcribing','refining'):
        label='Transcribing…' if phase=='transcribing' else 'Refining speech…'
        if status.get('recognition_trace',{}).get('phase')=='decoding_hebrew':
            label='Checking Hebrew…'
    elif status.get('audio_queued',0):
        label='Speech queued…'
    elif status.get('state')=='listening' and status.get('receiving_speech'):
        label='Listening…'
    else:
        return {'active':False}
    item=pipeline.items.get(uid) if uid else None
    return {'active':True,'label':label,'utterance_id':uid,
            'display_index':item['display_index'] if item else pipeline.display_index+1}


async def decode_audio(recognizer,audio,language=None,refine=False,status=None):
    if status is not None:
        status.update(asr_phase='refining' if refine else 'transcribing',asr_started=time.monotonic())
    try:
        if refine:
            return await asyncio.to_thread(recognizer.transcribe,audio,language,True)
        return await asyncio.to_thread(recognizer.transcribe,audio,language)
    finally:
        if status is not None:
            status.update(asr_phase='idle',asr_started=None)
            if refine and hasattr(recognizer,'last_comparison'):
                status['recognition']=dict(recognizer.last_comparison)


def activity_snapshot(pipeline,status=None,now=None):
    status=status or {}
    now=time.monotonic() if now is None else now
    stages=[]
    phase=status.get('asr_phase')
    if phase in ('transcribing','refining'):
        stages.append({'key':phase,'label':'Refining speech' if phase=='refining' else 'Transcribing',
                       'elapsed_seconds':round(max(0,now-(status.get('asr_started') or now)),1)})
    translation=pipeline.active_translation
    if translation:
        language=CATALOG.get(translation['target'],{}).get('name',translation['target'])
        stages.append({'key':'translating','label':f'Translating {language}',
                       'elapsed_seconds':round(max(0,now-translation['started']),1)})
    queued=pipeline.pending+status.get('audio_queued',0)
    if stages:
        label=' · '.join(stage['label'] for stage in stages)
    elif queued:
        label='Processing queued speech'
    elif status.get('state')=='listening' and status.get('receiving_speech'):
        label='Receiving speech'
    else:
        label={'listening':'Listening','reconnecting':'Reconnecting microphone','loading':'Loading models',
               'starting':'Starting microphone','transcribing':'Transcribing'}.get(status.get('state'),'Ready')
    return {'active':bool(stages or queued or label=='Receiving speech'),'label':label,'stages':stages,
            'queued':queued,'elapsed_seconds':max((s['elapsed_seconds'] for s in stages),default=0)}
