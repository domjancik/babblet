import asyncio
import importlib.util

import numpy as np

from babblet.adapters import Segmenter
from babblet.core import Pipeline


def test_cutoff_followed_by_silence_emits_final_boundary():
    s = Segmenter(sample_rate=1000, frame_ms=100, pause_ms=300, max_seconds=1)
    for _ in range(10):
        clip = s.push(np.ones(100, dtype=np.float32)*0.1)
    assert clip is not None
    assert getattr(s, 'last_boundary', None) == 'limit'
    for _ in range(3):
        tail = s.push(np.zeros(100, dtype=np.float32))
    assert tail is not None
    assert s.last_boundary == 'pause'


def test_pause_redecodes_joined_audio_and_replaces_split_paragraph():
    assert importlib.util.find_spec('babblet.refinement'), 'Speech refinement must exist'
    from babblet.refinement import SpeechSession
    class Recognizer:
        def __init__(self):
            self.calls = []
        def transcribe(self, audio, language=None, refine=False):
            self.calls.append((len(audio), refine))
            text = 'We should meet at the entrance.' if refine else 'We should meet at'
            return [{'text':text,'language':'en','start':0,'end':len(audio)/16000}]
    class Translator:
        async def translate(self, text, *args):
            return text
    async def run():
        recognizer = Recognizer()
        pipeline = Pipeline(Translator())
        session = SpeechSession(recognizer,pipeline)
        await session.process(np.ones(16000,dtype=np.float32)*0.1,0,'limit')
        await pipeline.drain()
        first_id = pipeline.snapshot()['utterances'][0]['utterance_id']
        await session.process(np.ones(8000,dtype=np.float32)*0.1,1,'pause')
        await pipeline.drain()
        items = pipeline.snapshot()['utterances']
        assert len(items) == 1
        assert items[0]['utterance_id'] == first_id
        assert items[0]['source_text'] == 'We should meet at the entrance.'
        assert items[0]['phase'] == 'final'
        assert items[0]['translations']['he']['text'] == items[0]['source_text']
        assert (24000,True) in recognizer.calls
    asyncio.run(run())


def test_inflight_translation_cannot_overwrite_refined_text():
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        class Translator:
            async def translate(self,text,*args):
                if text == 'cut off':
                    entered.set()
                    await release.wait()
                return text
        pipeline = Pipeline(Translator())
        await pipeline.submit('a','cut off','en',0,1)
        task = asyncio.create_task(pipeline.drain())
        await entered.wait()
        assert hasattr(pipeline,'revise'), 'Revision support must exist'
        await pipeline.revise('a','complete sentence','en',0,2,phase='final')
        release.set()
        await task
        await pipeline.drain()
        item = pipeline.snapshot()['utterances'][0]
        assert item['translations']['he']['text'] == 'complete sentence'
    asyncio.run(run())


def test_refinement_error_preserves_draft_and_marks_it_unrefined():
    from babblet.refinement import SpeechSession
    class Recognizer:
        def transcribe(self,audio,language=None,refine=False):
            if refine:
                raise RuntimeError('GPU unavailable')
            return [{'text':'Keep this draft','language':'en','start':0,'end':1}]
    async def run():
        pipeline = Pipeline(None)
        session = SpeechSession(Recognizer(),pipeline)
        await session.process(np.ones(16000,dtype=np.float32),0,'limit')
        import pytest
        with pytest.raises(RuntimeError):
            await session.process(np.zeros(8000,dtype=np.float32),1,'pause')
        item=pipeline.snapshot()['utterances'][0]
        assert item['source_text']=='Keep this draft'
        assert item['phase']=='unrefined'
        assert session.samples==0
    asyncio.run(run())


def test_short_pause_fragments_rejoin_original_audio_and_same_row():
    from babblet.refinement import SpeechSession
    class Recognizer:
        def __init__(self): self.lengths=[]
        def transcribe(self,audio,language=None,refine=False):
            self.lengths.append(len(audio))
            return [{'text':'אז עכשיו' if len(audio)==16000 else 'אז עכשיו ראיתי משהו',
                     'language':'he','start':0,'end':len(audio)/16000}]
    async def run():
        recognizer=Recognizer();pipeline=Pipeline(None)
        session=SpeechSession(recognizer,pipeline)
        await session.process(np.ones(16000,dtype=np.float32),0,'pause')
        uid=next(iter(pipeline.items))
        await session.process(np.ones(16000,dtype=np.float32),1.4,'pause')
        assert recognizer.lengths==[16000,32000]
        assert list(pipeline.items)==[uid]
        assert pipeline.items[uid]['source_text']=='אז עכשיו ראיתי משהו'
        assert pipeline.items[uid]['revision']==2
        session.reset()
    asyncio.run(run())


def test_long_pause_or_capture_reset_starts_a_new_row():
    from babblet.refinement import SpeechSession
    class Recognizer:
        def transcribe(self,audio,*args):
            return [{'text':'שלום','language':'he','start':0,'end':1}]
    async def run():
        pipeline=Pipeline(None);session=SpeechSession(Recognizer(),pipeline)
        await session.process(np.ones(16000,dtype=np.float32),0,'pause')
        await session.process(np.ones(16000,dtype=np.float32),5,'pause')
        assert len(pipeline.items)==2
        session.reset()
        await session.process(np.ones(16000,dtype=np.float32),6.2,'pause')
        assert len(pipeline.items)==3
        session.reset()
    asyncio.run(run())
