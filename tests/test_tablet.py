import asyncio
import json

from fastapi.testclient import TestClient

from babblet.core import Pipeline
from babblet.tablet import TabletPresentation,create_bridge
from babblet.web import create_app


def item(index,text=None,revision=1,phase='final'):
    return {'utterance_id':str(index),'display_index':index,'source_text':text or str(index),
            'source_language':'he','revision':revision,'phase':phase,
            'translations':{'en':{'status':'complete','text':'English '+str(index)}}}


def test_tablet_slots_are_global_fifo_and_revisions_never_change_row():
    view=TabletPresentation(count=3)
    for index in range(1,5): view.publish(item(index))
    assert [row['utterance_id'] for row in view.snapshot(['en'])['slots']]==['4','2','3']
    view.publish(item(2,'refined',revision=2))
    assert view.snapshot(['en'])['slots'][1]['source_text']=='refined'
    view.publish(item(1,'late'))
    assert view.snapshot(['en'])['slots'][0]['utterance_id']=='4'


def test_tablet_ignores_drafts_and_unchanged_updates():
    view=TabletPresentation()
    view.publish(item(1,phase='draft'))
    assert all(row is None for row in view.snapshot(['en'])['slots'])
    view.publish(item(1));first=view.snapshot(['en'])
    view.publish(item(1));assert view.snapshot(['en'])==first
    view.publish(item(1,'new draft',revision=2,phase='refining'))
    assert view.snapshot(['en'])==first


def test_browser_rollover_does_not_clear_tablet_and_pending_results_fill_same_row():
    async def run():
        class Translator:
            async def translate(self,*args): return 'Hello'
        pipeline=Pipeline(Translator(),targets=['en'])
        await pipeline.submit('a','שלום','he',0,1)
        await pipeline.drain()
        before=pipeline.tablet.snapshot(pipeline.targets)
        pipeline.discard([{'utterance_id':'a','revision':1}])
        assert pipeline.tablet.snapshot(pipeline.targets)==before
        await pipeline.submit('b','עולם','he',2,3)
        await pipeline.drain()
        rows=pipeline.tablet.snapshot(pipeline.targets)['slots']
        assert rows[0]['utterance_id']=='a' and rows[1]['utterance_id']=='b'
        assert rows[1]['translations']['en']['text']=='Hello'
    asyncio.run(run())


def test_browser_discard_marks_unfinished_tablet_translations_unavailable():
    async def run():
        pipeline=Pipeline(None,targets=['en'])
        await pipeline.submit('a','שלום','he',0,1)
        pipeline.discard([{'utterance_id':'a','revision':1}])
        value=pipeline.tablet.snapshot(pipeline.targets)['slots'][0]
        assert value['source_text']=='שלום'
        assert value['translations']['en']['status']=='skipped'
    asyncio.run(run())


def test_local_tablet_snapshot_excludes_debug_audio_and_inspector_content():
    pipeline=Pipeline(None)
    client=TestClient(create_app(pipeline,{'recognition_trace':{'secret':'not for tablet'},
        'debug_recording':{'directory':'private'}}))
    data=client.get('/api/tablet').json()
    assert 'session' in data and len(data['slots'])==6
    assert 'recognition_trace' not in json.dumps(data)
    assert 'debug_recording' not in json.dumps(data)


def test_network_bridge_requires_bearer_token_and_only_exposes_tablet_routes():
    class Source:
        async def snapshot(self): return {'session':'s','sequence':1,'slots':[],'languages':[]}
        async def select(self,mode,languages): return {'selected':languages}
    client=TestClient(create_bridge('x'*32,Source()))
    assert client.get('/v1/display').status_code==401
    assert client.get('/v1/display',headers={'Authorization':'Bearer wrong'}).status_code==401
    headers={'Authorization':'Bearer '+'x'*32}
    assert client.get('/v1/display',headers=headers).status_code==200
    assert client.get('/api/snapshot',headers=headers).status_code==404
    assert client.post('/v1/languages',headers=headers,json={'mode':'display','languages':['he']}).status_code==200
    assert client.post('/v1/languages',headers=headers,json={'mode':'display','languages':[]}).status_code==422
    assert client.post('/v1/languages',headers=headers,json={'mode':'speech','languages':['madeup']}).status_code==422
    assert client.get('/v1/display',headers={**headers,'Origin':'https://foreign.example'}).status_code==403
