import asyncio

import pytest

from babblet.core import Pipeline


def test_selected_languages_schedule_only_requested_targets():
    class Translator:
        async def translate(self,text,source,target):
            return target+': '+text
    async def run():
        pipeline = Pipeline(Translator(),targets=['en','fr'])
        await pipeline.submit('a','Bonjour tout le monde','fr',0,2)
        await pipeline.drain()
        item = pipeline.snapshot()['utterances'][0]
        assert item['source_language'] == 'fr'
        assert set(item['translations']) == {'en','fr'}
        assert item['translations']['fr']['status'] == 'complete'
        await pipeline.set_targets(['fr','de'])
        await pipeline.drain()
        assert pipeline.snapshot()['selected_languages'] == ['fr','de']
        assert pipeline.snapshot()['utterances'][0]['translations']['de']['text'].startswith('de:')
    asyncio.run(run())


def test_language_selection_validates_supported_codes():
    async def run():
        p = Pipeline(None)
        with pytest.raises(ValueError):
            await p.set_targets(['made-up'])
        with pytest.raises(ValueError):
            await p.set_targets([])
    asyncio.run(run())


def test_language_api_requires_same_origin_and_updates_pipeline():
    from fastapi.testclient import TestClient
    from babblet.web import create_app
    p = Pipeline(None)
    client = TestClient(create_app(p))
    listing = client.get('/api/languages')
    assert listing.status_code == 200
    assert any(x['code']=='fr' for x in listing.json()['available'])
    assert client.post('/api/languages',json={'languages':['fr','en']}).status_code == 403
    assert client.post('/api/languages',headers={'Origin':'http://testserver'},json={'languages':['fr','en']}).status_code == 200
    assert p.targets == ('fr','en')
    assert client.post('/api/languages',headers={'Origin':'http://testserver'},json={'languages':['xx']}).status_code == 422


def test_language_selection_persists_only_valid_configuration(tmp_path):
    import json
    from fastapi.testclient import TestClient
    from babblet.web import create_app
    path=tmp_path/'languages.json'
    client=TestClient(create_app(Pipeline(None),selection_path=path))
    headers={'Origin':'http://testserver'}
    assert client.post('/api/languages',headers=headers,json={'languages':['fr','he']}).status_code==200
    assert json.loads(path.read_text())==['fr','he']
    assert client.post('/api/languages',headers=headers,json={'languages':['xx']}).status_code==422
    assert json.loads(path.read_text())==['fr','he']
