import asyncio
import importlib.util
import time

import pytest


def core():
    assert importlib.util.find_spec('babblet') is not None, 'Pipeline package must exist'
    from babblet.core import Pipeline, route_language
    return Pipeline, route_language


class Translator:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    async def translate(self, text, source, target):
        self.calls.append((text, source, target))
        if self.fail:
            raise ConnectionError('engine unavailable')
        return {'he': 'שלום עולם', 'ru': 'Привет мир', 'en': 'Hello world'}[target]


def test_script_routes_misclassified_hebrew_and_russian():
    _, route = core()
    assert route('שלום עולם', 'en') == 'he'
    assert route('Привет мир', 'en') == 'ru'
    assert route('123', 'he') == 'he'


def test_commits_source_and_translates_all_named_outputs():
    Pipeline, _ = core()
    async def run():
        translator = Translator()
        pipeline = Pipeline(translator)
        await pipeline.submit('a', 'Hello world', 'en', 0, 2)
        await pipeline.drain()
        item = pipeline.snapshot()['utterances'][0]
        assert item['translations']['en']['status'] == 'complete'
        assert item['translations']['he']['text'] == 'שלום עולם'
        assert len(translator.calls) == 3
        assert not await pipeline.submit('a', 'Hello world', 'en', 0, 2)
        assert len(pipeline.snapshot()['utterances']) == 1
    asyncio.run(run())


def test_translation_failure_preserves_source_and_recovers_next_utterance():
    Pipeline, _ = core()
    async def run():
        translator = Translator(fail=True)
        pipeline = Pipeline(translator, retries=1)
        await pipeline.submit('a', 'Hello world', 'en', 0, 2)
        await pipeline.drain()
        first = pipeline.snapshot()['utterances'][0]
        assert first['source_text'] == 'Hello world'
        assert first['translations']['he']['status'] == 'error'
        translator.fail = False
        await pipeline.submit('b', 'שלום עולם', 'he', 2, 4)
        await pipeline.drain()
        assert pipeline.snapshot()['utterances'][-1]['translations']['ru']['status'] == 'complete'
    asyncio.run(run())


def test_overload_and_expiry_keep_source_and_bound_memory():
    Pipeline, _ = core()
    async def run():
        translator = Translator()
        pipeline = Pipeline(translator, max_pending=2, max_age=0.01, history=2)
        for i in range(4):
            await pipeline.submit(str(i), 'Hello world', 'en', i, i+1)
        assert pipeline.pending <= 2
        await asyncio.sleep(0.02)
        await pipeline.drain()
        assert not translator.calls
        assert len(pipeline.snapshot()['utterances']) == 2
        assert pipeline.snapshot()['health']['expired'] >= 2
    asyncio.run(run())


def test_blank_text_does_not_create_utterance():
    Pipeline, _ = core()
    async def run():
        pipeline = Pipeline(Translator())
        assert not await pipeline.submit('a', '   ', 'en', 0, 1)
        assert not pipeline.snapshot()['utterances']
    asyncio.run(run())


def test_unexpected_engine_error_does_not_kill_worker():
    Pipeline, _ = core()
    class Broken:
        async def translate(self, *args):
            raise RuntimeError('engine crashed')
    async def run():
        pipeline = Pipeline(Broken(), retries=0)
        await pipeline.submit('a', 'Hello world', 'en', 0, 1)
        await pipeline.drain()
        assert pipeline.snapshot()['health']['errors'] == 3
        assert pipeline.snapshot()['utterances'][0]['source_text'] == 'Hello world'
    asyncio.run(run())
