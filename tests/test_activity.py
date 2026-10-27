import asyncio
import importlib.util

import numpy as np
import pytest

from babblet.core import Pipeline
from babblet.refinement import SpeechSession


def activity_reader():
    assert importlib.util.find_spec('babblet.activity'), 'Processing activity must exist'
    from babblet.activity import activity_snapshot
    return activity_snapshot


def test_translation_activity_is_visible_while_generation_is_inflight_and_clears():
    read=activity_reader()
    async def run():
        entered,release=asyncio.Event(),asyncio.Event()
        class Translator:
            async def translate(self,*args):
                entered.set()
                await release.wait()
                return 'Hello.'
        p=Pipeline(Translator(),targets=['en'])
        await p.submit('a','Bonjour.','fr',0,1)
        task=asyncio.create_task(p.drain())
        await entered.wait()
        state=read(p,{'state':'listening'})
        assert state['active']
        assert state['stages'][0]['key']=='translating'
        assert 'English' in state['label']
        release.set()
        await task
        assert not read(p,{'state':'listening'})['active']
        assert read(p,{'state':'listening'})['label']=='Listening'
    asyncio.run(run())


def test_refinement_status_covers_decode_before_any_text_exists_and_clears_on_error():
    activity={}
    class Recognizer:
        def transcribe(self,*args):
            assert activity.get('asr_phase')=='refining'
            assert activity.get('asr_started') is not None
            raise RuntimeError('Test failure')
    async def run():
        session=SpeechSession(Recognizer(),Pipeline(None),activity=activity)
        with pytest.raises(RuntimeError):
            await session.process(np.ones(16000,dtype=np.float32),0,'pause')
        assert activity['asr_phase']=='idle'
        assert activity['asr_started'] is None
    asyncio.run(run())


def test_parallel_refinement_and_translation_and_backlog_are_reported():
    read=activity_reader()
    p=Pipeline(None)
    p.active_translation={'target':'en','started':10}
    state=read(p,{'state':'listening','asr_phase':'refining','asr_started':9,'audio_queued':2},now=12)
    assert {item['key'] for item in state['stages']}=={'refining','translating'}
    assert state['queued']==2
    assert state['elapsed_seconds']==3


def test_activity_endpoint_has_no_transcript_text():
    from fastapi.testclient import TestClient
    from babblet.web import create_app
    client=TestClient(create_app(Pipeline(None),{'state':'listening','receiving_speech':True}))
    response=client.get('/api/processing')
    assert response.status_code==200
    data=response.json()
    assert data['active'] and data['label']=='Receiving speech'
    assert 'utterances' not in data


def test_pending_row_activity_starts_during_capture_and_follows_decode_uid():
    from babblet.activity import pending_activity_snapshot
    p=Pipeline(None)
    capture=pending_activity_snapshot(p,{'state':'listening','receiving_speech':True})
    assert capture['active'] and capture['label']=='Listening…'
    assert capture['display_index']==1
    state={'state':'listening','asr_phase':'refining','asr_utterance_id':'a',
           'recognition_trace':{'phase':'decoding_hebrew'}}
    decode=pending_activity_snapshot(p,state)
    assert decode['utterance_id']=='a' and decode['label']=='Checking Hebrew…'
    assert not pending_activity_snapshot(p,{'state':'listening'})['active']
    p.active_translation={'target':'he','started':1}
    assert not pending_activity_snapshot(p,{'state':'listening'})['active']
