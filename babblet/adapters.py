"""Local model adapters. Network inference is restricted to loopback."""
import importlib.util
import os
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

import httpx
import numpy as np

from babblet.languages import CATALOG

_DLL_HANDLES = []


class Translator:
    def __init__(self, url='http://127.0.0.1:18081/v1', client=None):
        if urlparse(url).hostname not in {'127.0.0.1', 'localhost', '::1'}:
            raise ValueError('Translation inference must stay on loopback')
        self.url = url.rstrip('/')
        self.client = client
        key_file = Path('runtime/translation.key')
        self.headers = {'Authorization': 'Bearer ' + key_file.read_text().strip()} if key_file.exists() else {}

    async def translate(self, text, source, target):
        prompt = (f'Translate the following text into {CATALOG[target]["name"]}. '
                  'Note that you should only output the translated result '
                  f'without any additional explanation:\n{text}')
        payload = {'model': 'hymt2', 'messages': [{'role': 'user', 'content': prompt}],
                   'temperature': 0, 'max_tokens': 256, 'stream': False}
        try:
            if self.client is None:
                async with httpx.AsyncClient(timeout=18, trust_env=False) as client:
                    response = await client.post(self.url + '/chat/completions', json=payload, headers=self.headers)
            else:
                response = await self.client.post(self.url + '/chat/completions', json=payload, headers=self.headers)
            response.raise_for_status()
            choice = response.json()['choices'][0]
            if choice.get('finish_reason') == 'length':
                raise ValueError('Translation truncated')
            return choice['message']['content'].strip()
        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            raise ConnectionError('Local translation engine unavailable or invalid') from exc


class SpeechRecognizer:
    def __init__(self, path='models/whisper-turbo', device='cuda', model=None,guidance=None):
        self.device = device
        self.guidance=guidance
        if model is not None:
            self.model = model
            return
        if os.name == 'nt':
            spec = importlib.util.find_spec('torch')
            if spec and spec.origin:
                dll_dir = str(Path(spec.origin).parent / 'lib')
                os.environ['PATH'] = dll_dir + os.pathsep + os.environ['PATH']
                _DLL_HANDLES.append(os.add_dll_directory(dll_dir))
        from faster_whisper import WhisperModel
        self.model = WhisperModel(path, device=device,
            compute_type='int8_float16' if device == 'cuda' else 'int8',
            local_files_only=True)

    def transcribe(self, audio, language=None, refine=False):
        self.last_detection=None
        audio = np.asarray(audio, dtype=np.float32)
        if not len(audio) or not np.isfinite(audio).all():
            return []
        if float(np.sqrt(np.mean(audio ** 2))) < 0.001:
            return []
        detection=None
        probabilities=[]
        if language is None and self.guidance and self.guidance.expected:
            try:
                from faster_whisper.vad import VadOptions
                raw_code,raw_probability,probabilities=self.model.detect_language(
                    audio=audio,vad_filter=True,vad_parameters=VadOptions(min_silence_duration_ms=500))
            except ValueError:
                # The VAD path can produce no chunks for a non-speech input.
                return []
            detection=(raw_code,raw_probability)
            language=self.guidance.choose(probabilities)
        automatic=language is None
        segments, info = self.model.transcribe(audio, language=language,
            task='transcribe', beam_size=5 if refine else 1, vad_filter=True,
            condition_on_previous_text=refine,
            vad_parameters={'min_silence_duration_ms': 500},
            no_speech_threshold=0.6, compression_ratio_threshold=2.4)
        result=[{'text': s.text.strip(), 'language': info.language,
                 'start': s.start, 'end': s.end,'avg_logprob':float(s.avg_logprob),
                 'no_speech_prob':float(s.no_speech_prob),
                 'compression_ratio':float(getattr(s,'compression_ratio',float('nan')))} for s in segments
                if s.text.strip() and s.no_speech_prob < 0.8 and s.avg_logprob > -1.5]
        self.last_detection={'language':detection[0] if detection else info.language,
                             'probability':float(detection[1] if detection else getattr(info,'language_probability',0))}
        if not probabilities:
            probabilities=getattr(info,'all_language_probs',None) or []
        self.last_detection['hebrew_probability']=float(next((score for code,score in probabilities if code=='he'),
            self.last_detection['probability'] if self.last_detection['language']=='he' else 0))
        self.last_detection['expected']=list(self.guidance.expected) if self.guidance else []
        if refine and result and self.guidance:
            if detection is None and automatic:
                detection=(info.language,info.language_probability)
            if detection:
                self.guidance.observe(*detection,getattr(info,'duration_after_vad',len(audio)/16000),
                                      guided_language=info.language)
        return result


class Segmenter:
    """Energy endpointing for capture; Silero in ASR rejects non-speech.

    Caps each utterance and retains pre-roll. This is not speaker separation.
    """
    def __init__(self, sample_rate=16000, frame_ms=100, pause_ms=700,
                 max_seconds=6, threshold=0.008):
        self.pause_frames = max(1, pause_ms // frame_ms)
        self.max_samples = int(sample_rate * max_seconds)
        self.threshold = threshold
        self.preroll = deque(maxlen=max(1, 300 // frame_ms))
        self.frames = []
        self.quiet = 0
        self.samples = 0
        self.last_boundary = None
        self.continuing = False

    def push(self, frame):
        frame = np.array(frame, dtype=np.float32, copy=True)
        voiced = float(np.sqrt(np.mean(frame ** 2))) >= self.threshold
        if not self.frames:
            if not voiced and not self.continuing:
                self.preroll.append(frame)
                return None
            self.frames = list(self.preroll)
            self.preroll.clear()
            self.samples = sum(map(len, self.frames))
        self.frames.append(frame)
        self.samples += len(frame)
        self.quiet = 0 if voiced else self.quiet + 1
        if self.quiet >= self.pause_frames or self.samples >= self.max_samples:
            self.last_boundary = 'pause' if self.quiet >= self.pause_frames else 'limit'
            self.continuing = self.last_boundary == 'limit'
            result = np.concatenate(self.frames)
            self.frames = []
            self.samples = self.quiet = 0
            return result
        return None
