import asyncio
import importlib.util
from types import SimpleNamespace

import numpy as np
import pytest


def guidance_type():
    assert importlib.util.find_spec('babblet.speech_languages'), 'Speech guidance must exist'
    from babblet.speech_languages import SpeechGuidance
    return SpeechGuidance


def test_expected_languages_bias_ambiguous_detection_but_allow_clear_outsider():
    guide=guidance_type()(['he','ru'])
    assert guide.choose([('en',.45),('he',.35),('ru',.2)])=='he'
    assert guide.choose([('fr',.96),('he',.03),('ru',.01)])=='fr'
    assert guide.choose([('en',.1),('he',.08),('ru',.07)])=='en'
    guide.set_expected([])
    assert guide.choose([('en',.45),('he',.35)])=='en'


def test_suggestions_require_repeated_confident_speech_and_expire():
    now=[0.0]
    guide=guidance_type()(['en'],clock=lambda:now[0])
    guide.observe('fr',.95,3)
    assert guide.snapshot()['suggested']==[]
    guide.observe('fr',.4,3)
    guide.observe('fr',.95,.3)
    assert guide.snapshot()['suggested']==[]
    guide.observe('fr',.92,3)
    assert guide.snapshot()['suggested'][0]['code']=='fr'
    guide.set_expected(['en','fr'])
    assert guide.snapshot()['suggested']==[]
    guide.set_expected(['en'])
    now[0]=121
    assert guide.snapshot()['suggested']==[]


def test_guidance_filters_unsupported_speech_aliases():
    Guide=guidance_type()
    with pytest.raises(ValueError): Guide(['zh-Hant'])
    with pytest.raises(ValueError): Guide(['ug'])
    assert Guide([]).snapshot()['expected']==[]


def test_recognizer_passes_preferred_language_and_observes_raw_detection():
    from babblet.adapters import SpeechRecognizer
    guide=guidance_type()(['he'])
    class Model:
        def __init__(self): self.language=None
        def detect_language(self,**kwargs):
            assert hasattr(kwargs['vad_parameters'],'threshold'), 'Native language detection requires a VadOptions instance'
            return 'en',.45,[('en',.45),('he',.4),('ru',.15)]
        def transcribe(self,audio,**kwargs):
            self.language=kwargs['language']
            segment=SimpleNamespace(text='שלום עולם',start=0,end=2,no_speech_prob=.01,avg_logprob=-.1)
            info=SimpleNamespace(language=self.language,language_probability=1,duration_after_vad=2,all_language_probs=None)
            return iter([segment]),info
    model=Model()
    recognizer=SpeechRecognizer(model=model,guidance=guide)
    result=recognizer.transcribe(np.ones(32000,dtype=np.float32)*.1,refine=True)
    assert model.language=='he'
    assert result[0]['language']=='he'
    assert guide.snapshot()['detected']['code']=='en'
    assert guide.snapshot()['detected']['guided_language']=='he'


def test_manual_speech_api_opts_out_of_display_sync_and_persists(tmp_path):
    from fastapi.testclient import TestClient
    from babblet.core import Pipeline
    from babblet.web import create_app
    import json
    guide=guidance_type()()
    pipeline=Pipeline(None,targets=['en','he'])
    path=tmp_path/'speech.json'
    client=TestClient(create_app(pipeline,guidance=guide,speech_path=path))
    data=client.get('/api/speech-languages').json()
    assert data['expected']==['en','he']
    assert data['sync_with_display'] is True
    assert any(x['code']=='fr' for x in data['available'])
    assert not any(x['code']=='zh-Hant' for x in data['available'])
    body={'languages':['he','ru']}
    assert client.post('/api/speech-languages',json=body).status_code==403
    response=client.post('/api/speech-languages',headers={'Origin':'http://testserver'},json=body)
    assert response.status_code==200
    assert guide.snapshot()['expected']==['he','ru']
    assert pipeline.targets==('en','he')
    assert json.loads(path.read_text())==['he','ru']
    assert client.post('/api/speech-languages',headers={'Origin':'http://testserver'},json={'languages':[]}).status_code==200
    assert client.post('/api/speech-languages',headers={'Origin':'http://testserver'},json={'languages':['ug']}).status_code==422
