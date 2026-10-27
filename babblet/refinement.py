"""Keep cut chunks together, then revise from original audio at a speech pause."""
import asyncio
import uuid

import numpy as np
from babblet.activity import decode_audio


class SpeechSession:
    def __init__(self, recognizer, pipeline, max_seconds=24,activity=None):
        self.recognizer, self.pipeline = recognizer, pipeline
        self.max_samples = int(max_seconds*16000)
        self.audio = []
        self.samples = 0
        self.uid = None
        self.text = ''
        self.language = None
        self.start = 0
        self.end = 0
        self.recent = None
        self.recent_timer = None
        self.activity=activity

    def reset(self):
        if self.activity is not None:
            self.activity['asr_utterance_id']=None
        if self.recent_timer:
            self.recent_timer.cancel()
        self.recent_timer=None
        self.recent=None
        if self.uid and self.uid in self.pipeline.items:
            if self.pipeline.items[self.uid]['phase'] in ('draft','refining'):
                self.pipeline.set_phase(self.uid,'unrefined')
        self.audio.clear()
        self.samples = 0
        self.uid = None
        self.text = ''
        self.language = None
        self.end = 0

    async def process(self, audio, start, boundary):
        if self.samples and self.samples + len(audio) > self.max_samples:
            await self.finalize()
        if not self.audio:
            recent=self.recent
            self.recent=None
            if self.recent_timer:
                self.recent_timer.cancel()
                self.recent_timer=None
            if (recent and recent['uid'] in self.pipeline.items and
                    -.3<=start-recent['end']<=1.5 and
                    recent['samples']+len(audio)<=self.max_samples):
                self.start=recent['start'];self.uid=recent['uid']
                self.audio=[recent['audio']];self.samples=recent['samples']
                self.text=recent['text'];self.language=recent['language']
            else:
                self.start = start
                self.uid = uuid.uuid4().hex[:12]
        self.audio.append(audio)
        self.samples += len(audio)
        self.end=start+len(audio)/16000
        if self.activity is not None:
            self.activity['asr_utterance_id']=self.uid
            self.activity['speech_context']={'audio_seconds':round(self.samples/16000,2),
                'continuing_row':self.uid in self.pipeline.items}
        if boundary == 'pause':
            await self.finalize()
            return
        segments = await decode_audio(self.recognizer,audio,status=self.activity)
        if segments:
            self.language = self.language or segments[0]['language']
            self.text = ' '.join(filter(None,[self.text, ' '.join(s['text'] for s in segments)]))
            await self.pipeline.revise(self.uid,self.text,self.language,self.start,
                start+len(audio)/16000,phase='draft')

    async def finalize(self):
        if not self.audio:
            return
        self.pipeline.set_phase(self.uid,'refining')
        recent=None
        try:
            joined = np.concatenate(self.audio)
            segments = await decode_audio(self.recognizer,joined,refine=True,status=self.activity)
            if segments:
                text = ' '.join(s['text'] for s in segments)
                await self.pipeline.revise(self.uid,text,segments[0]['language'],self.start,
                    self.end,phase='final')
                recent={'uid':self.uid,'audio':joined,'samples':len(joined),
                    'start':self.start,'end':self.end,'text':text,'language':segments[0]['language']}
            else:
                self.pipeline.set_phase(self.uid,'unrefined')
        except Exception:
            self.pipeline.set_phase(self.uid,'unrefined')
            raise
        finally:
            self.reset()
            # A brief in-memory tail allows adjacent phrase fragments to recover
            # context without retaining audio across separate conversation turns.
            if recent:
                self.recent=recent
                def expire():
                    self.recent=None
                    self.recent_timer=None
                self.recent_timer=asyncio.get_running_loop().call_later(3,expire)
