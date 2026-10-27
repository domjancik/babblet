"""Explicitly enabled local rolling debug recordings, never uploaded."""
import json
import time
import uuid
from pathlib import Path

import soundfile as sf


class DebugRecorder:
    def __init__(self,directory,limit=20):
        self.directory=Path(directory)
        self.limit=max(1,int(limit))
        self.enabled=True
        self.latest=None

    def save(self,audio,trace):
        if not self.enabled:
            return None
        self.directory.mkdir(parents=True,exist_ok=True)
        name=f'clip-{time.time_ns()}-{uuid.uuid4().hex[:6]}'
        path=self.directory/f'{name}.wav'
        sf.write(path,audio,16000,subtype='FLOAT')
        self.annotate(path,trace)
        self.latest=path.name
        for old in sorted(self.directory.glob('clip-*.wav'))[:-self.limit]:
            old.unlink(missing_ok=True)
            old.with_suffix('.json').unlink(missing_ok=True)
        return path

    def annotate(self,path,trace):
        if path is not None:
            Path(path).with_suffix('.json').write_text(json.dumps({
                'recorded_at':time.time(),'sample_rate':16000,'trace':trace},
                ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


class RecordingRecognizer:
    def __init__(self,recognizer,recorder,status):
        self.recognizer=recognizer
        self.recorder=recorder
        self.status=status

    def __getattr__(self,name):
        return getattr(self.recognizer,name)

    def transcribe(self,audio,language=None,refine=False):
        path=None
        try:
            if refine and self.recorder.enabled:
                path=self.recorder.save(audio,{'phase':'decoding'})
                self.status['debug_recording'].update(latest=self.recorder.latest,
                    saved=self.status['debug_recording'].get('saved',0)+1)
        except Exception as exc:
            self.status['debug_recording']['error']=type(exc).__name__
        try:
            return self.recognizer.transcribe(audio,language,refine)
        finally:
            if path:
                try:
                    self.recorder.annotate(path,getattr(self.recognizer,'trace',{}))
                except Exception as exc:
                    self.status['debug_recording']['error']=type(exc).__name__

    def close(self):
        close=getattr(self.recognizer,'close',None)
        if close:
            close()
