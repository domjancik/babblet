"""Soft speech-language hints and short-lived acoustic detection suggestions."""
import time
import json
from pathlib import Path
from collections import Counter, deque

from babblet.languages import CATALOG

# The installed Whisper tokenizer supports this catalog intersection. Traditional
# Chinese is a writing variant of zh, and ug is unavailable in this Whisper build.
SPEECH_CATALOG={code:value for code,value in CATALOG.items() if code not in {'zh-Hant','ug'}}


def sync_policy_path(speech_path):
    return Path(speech_path).with_name('speech-sync.json') if speech_path is not None else None


def read_sync_policy(speech_path):
    path=sync_policy_path(speech_path)
    if path is None or not path.exists():
        return True
    value=json.loads(path.read_text(encoding='utf-8')).get('sync_with_display')
    if not isinstance(value,bool):
        raise ValueError('Speech sync policy must contain a boolean sync_with_display')
    return value


def load_speech_guidance(display_languages,speech_path=None,expected_override=None):
    expected=[]
    if speech_path is not None and Path(speech_path).exists():
        expected=json.loads(Path(speech_path).read_text(encoding='utf-8'))
    enabled=read_sync_policy(speech_path)
    if expected_override is not None:
        expected=expected_override
        enabled=False
    guidance=SpeechGuidance(expected,sync_with_display=enabled)
    guidance.sync_display(display_languages)
    guidance.startup_configured=True
    return guidance


def persist_speech_settings(speech_path,expected,enabled):
    if speech_path is None:
        return
    for path,value in [(Path(speech_path),list(expected)),
            (sync_policy_path(speech_path),{'sync_with_display':enabled})]:
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(value),encoding='utf-8')
        temporary.replace(path)


class SpeechGuidance:
    def __init__(self,expected=(),clock=time.monotonic,sync_with_display=True):
        self.clock=clock
        self.events=deque(maxlen=64)
        self.detected=None
        self.detected_at=0
        self.sync_with_display=bool(sync_with_display)
        self.set_expected(expected)

    def sync_display(self,languages):
        if self.sync_with_display:
            self.set_expected(code for code in languages if code in SPEECH_CATALOG)

    def set_expected(self,expected):
        expected=tuple(dict.fromkeys(expected))
        if len(expected)>6 or any(code not in SPEECH_CATALOG for code in expected):
            raise ValueError('Select up to six supported speaking languages, or none for automatic detection')
        self.expected=expected

    def choose(self,probabilities):
        ranked=sorted(probabilities,key=lambda pair:pair[1],reverse=True)
        if not ranked:
            return None
        best,probability=ranked[0]
        candidates=[(code,score) for code,score in ranked if code in self.expected and score>=.15]
        if candidates and candidates[0][1]*2>=probability:
            return candidates[0][0]
        return best

    def observe(self,code,probability,duration,guided_language=None):
        now=self.clock()
        self.detected={'code':code,'probability':round(float(probability),3),
                       'guided_language':guided_language or code}
        self.detected_at=now
        if code in SPEECH_CATALOG and probability>=.75 and duration>=1.5:
            self.events.append((now,code,float(probability)))

    def snapshot(self):
        now=self.clock()
        while self.events and now-self.events[0][0]>120:
            self.events.popleft()
        counts=Counter(code for _,code,_ in self.events)
        suggested=[]
        for code,hits in counts.most_common():
            if hits>=2 and code not in self.expected:
                suggested.append({'code':code,'name':SPEECH_CATALOG[code]['name'],'observations':hits})
        return {'expected':list(self.expected),'suggested':suggested[:3],
                'sync_with_display':self.sync_with_display,
                'detected':self.detected if now-self.detected_at<=120 else None}
