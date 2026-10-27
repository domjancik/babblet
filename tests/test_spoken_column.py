import asyncio

from babblet.core import Pipeline


def test_english_is_translated_even_when_nonenglish_text_was_labelled_english():
    class Translator:
        async def translate(self,text,source,target):
            assert target=='en'
            return 'Hello everyone.'
    async def run():
        p=Pipeline(Translator(),targets=['en'])
        await p.submit('a','Bonjour tout le monde.','en',0,2)
        await p.drain()
        item=p.snapshot()['utterances'][0]
        assert item['source_text']=='Bonjour tout le monde.'
        assert item['translations']['en']=={'status':'complete','text':'Hello everyone.'}
    asyncio.run(run())


def test_every_named_output_is_a_translation_and_raw_source_is_independent():
    class Translator:
        async def translate(self,text,source,target):
            return {'he':'שלום לכולם.','en':'Hello everyone.'}[target]
    async def run():
        p=Pipeline(Translator(),targets=['he','en'])
        await p.submit('a','שלום לכולם','he',0,2)
        await p.drain()
        item=p.snapshot()['utterances'][0]
        assert item['source_text']=='שלום לכולם'
        assert all(value['status']=='complete' for value in item['translations'].values())
        assert item['translations']['he']['text']=='שלום לכולם.'
    asyncio.run(run())


def test_page_trimming_tracks_raw_and_translated_source_separately():
    class Translator:
        async def translate(self,*args):
            return 'Hello. Remaining.'
    async def run():
        p=Pipeline(Translator(),targets=['en'])
        await p.submit('a','Bonjour. La suite.','en',0,2)
        await p.drain()
        p.discard([{'utterance_id':'a','revision':1,'consumed':{'_spoken':9,'en':7}}])
        item=p.snapshot()['utterances'][0]
        assert item['source_text']=='La suite.'
        assert item['translations']['en']['text']=='Remaining.'
    asyncio.run(run())
