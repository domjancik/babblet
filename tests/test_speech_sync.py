import json

from fastapi.testclient import TestClient

from babblet.core import Pipeline
from babblet.speech_languages import load_speech_guidance,SpeechGuidance
from babblet.tablet import create_bridge
from babblet.web import create_app

ORIGIN={'Origin':'http://testserver'}


def test_default_expected_languages_follow_display_and_filter_unsupported_aliases():
    pipeline=Pipeline(None,targets=['he','cs','zh-Hant','ug'])
    client=TestClient(create_app(pipeline))
    initial=client.get('/api/speech-languages').json()
    assert initial['sync_with_display'] is True
    assert initial['expected']==['he','cs']
    client.post('/api/languages',headers=ORIGIN,json={'languages':['ru','en']})
    assert client.get('/api/speech-languages').json()['expected']==['ru','en']
    tablet=client.get('/api/tablet').json()
    assert tablet['sync_with_display'] is True and tablet['expected_languages']==['ru','en']


def test_sync_toggle_persists_and_reenable_aligns_immediately(tmp_path):
    path=tmp_path/'speech-languages.json'
    pipeline=Pipeline(None,targets=['he','cs'])
    client=TestClient(create_app(pipeline,speech_path=path))
    response=client.post('/api/speech-languages',headers=ORIGIN,json={'sync_with_display':False})
    assert response.status_code==200 and response.json()['sync_with_display'] is False
    client.post('/api/languages',headers=ORIGIN,json={'languages':['en']})
    assert client.get('/api/speech-languages').json()['expected']==['he','cs']
    policy=json.loads((tmp_path/'speech-sync.json').read_text())
    assert policy=={'sync_with_display':False}
    restarted=TestClient(create_app(Pipeline(None,targets=['en']),speech_path=path))
    saved=restarted.get('/api/speech-languages').json()
    assert saved['sync_with_display'] is False and saved['expected']==['he','cs']
    enabled=restarted.post('/api/speech-languages',headers=ORIGIN,json={'sync_with_display':True}).json()
    assert enabled['sync_with_display'] is True and enabled['expected']==['en']


def test_explicit_manual_selection_turns_link_off_and_empty_payload_is_invalid():
    client=TestClient(create_app(Pipeline(None,targets=['he'])))
    response=client.post('/api/speech-languages',headers=ORIGIN,json={'languages':['ru']})
    assert response.status_code==200 and response.json()['sync_with_display'] is False
    client.post('/api/languages',headers=ORIGIN,json={'languages':['en']})
    assert client.get('/api/speech-languages').json()['expected']==['ru']
    assert client.post('/api/speech-languages',headers=ORIGIN,json={}).status_code==422
    assert client.post('/api/speech-languages',headers=ORIGIN,json={'sync_with_display':'no'}).status_code==422


def test_startup_uses_default_sync_saved_off_and_explicit_cli_override(tmp_path):
    path=tmp_path/'speech-languages.json';path.write_text('["ru"]')
    default=load_speech_guidance(['he','cs'],path)
    assert default.expected==('he','cs') and default.sync_with_display
    (tmp_path/'speech-sync.json').write_text('{"sync_with_display":false}')
    off=load_speech_guidance(['he','cs'],path)
    assert off.expected==('ru',) and not off.sync_with_display
    explicit=load_speech_guidance(['he','cs'],path,expected_override=[])
    assert explicit.expected==() and not explicit.sync_with_display


def test_bridge_sync_setting_is_authenticated_validated_and_forwarded():
    class Source:
        called=None
        async def snapshot(self): return {}
        async def select(self,mode,languages): return {'selected':languages}
        async def set_sync(self,enabled): self.called=enabled;return {'sync_with_display':enabled}
    source=Source();client=TestClient(create_bridge('x'*32,source))
    payload={'mode':'sync','enabled':False}
    assert client.post('/v1/languages',json=payload).status_code==401
    response=client.post('/v1/languages',headers={'Authorization':'Bearer '+'x'*32},json=payload)
    assert response.status_code==200 and source.called is False
    assert client.post('/v1/languages',headers={'Authorization':'Bearer '+'x'*32},json={'mode':'sync'}).status_code==422


def test_explicit_unsynced_guidance_is_respected_without_a_saved_policy():
    guidance=SpeechGuidance(['he'],sync_with_display=False)
    client=TestClient(create_app(Pipeline(None,targets=['cs']),guidance=guidance))
    result=client.get('/api/speech-languages').json()
    assert result['sync_with_display'] is False and result['expected']==['he']


def test_sync_change_notifies_other_clients_and_does_not_accept_foreign_origin():
    pipeline=Pipeline(None,targets=['he'])
    client=TestClient(create_app(pipeline))
    before=client.get('/api/snapshot').json()['sequence']
    assert client.post('/api/speech-languages',json={'sync_with_display':False}).status_code==403
    assert client.get('/api/speech-languages').json()['sync_with_display'] is True
    client.post('/api/speech-languages',headers=ORIGIN,json={'sync_with_display':False})
    assert client.get('/api/snapshot').json()['sequence']>before
