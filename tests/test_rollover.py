import asyncio

from babblet.core import Pipeline


def test_rollover_forgets_source_translations_and_pending_work():
    async def run():
        p=Pipeline(None)
        await p.submit('old','Forget this page','en',0,1)
        await p.submit('new','Keep this page','en',1,2)
        assert hasattr(p,'discard'), 'Page discard must exist'
        result=p.discard([{'utterance_id':'old','revision':1}])
        assert result==['old']
        assert [x['utterance_id'] for x in p.snapshot()['utterances']]==['new']
        assert all(job[0]!='old' for job in p.jobs)
    asyncio.run(run())


def test_rollover_does_not_delete_a_new_revision_or_active_refinement():
    async def run():
        p=Pipeline(None)
        await p.submit('a','Draft','en',0,1,phase='draft')
        assert hasattr(p,'discard'), 'Page discard must exist'
        assert p.discard([{'utterance_id':'a','revision':1}])==[]
        await p.revise('a','Refined','en',0,2,phase='final')
        assert p.discard([{'utterance_id':'a','revision':1}])==[]
        assert p.discard([{'utterance_id':'a','revision':2}])==['a']
    asyncio.run(run())


def test_rollover_endpoint_requires_matching_origin():
    from fastapi.testclient import TestClient
    from babblet.web import create_app
    p=Pipeline(None)
    asyncio.run(p.submit('a','Temporary words','en',0,1))
    client=TestClient(create_app(p))
    body={'utterances':[{'utterance_id':'a','revision':1}]}
    assert client.post('/api/rollover',json=body).status_code==403
    response=client.post('/api/rollover',headers={'Origin':'http://testserver'},json=body)
    assert response.status_code==200
    assert response.json()['discarded']==['a']
    assert client.get('/api/snapshot').json()['utterances']==[]


def test_long_paragraph_rollover_erases_consumed_prefixes():
    class Translator:
        async def translate(self,text,source,target):
            return 'old words remaining words'
    async def run():
        p=Pipeline(Translator())
        await p.submit('long','old words remaining words','en',0,1)
        await p.drain()
        p.discard([{'utterance_id':'long','revision':1,
                    'consumed':{'en':10,'he':10,'ru':10}}])
        item=p.snapshot()['utterances'][0]
        assert item['source_text']=='remaining words'
        assert item['revision']==2
        assert all(t['text']=='remaining words' for t in item['translations'].values())
    asyncio.run(run())
