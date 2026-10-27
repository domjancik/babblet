import asyncio
import importlib.util

import numpy as np
import soundfile as sf


def test_recorded_audio_uses_shared_pipeline_and_returns_metrics(tmp_path):
    assert importlib.util.find_spec('babblet.runner'), 'Audio runner must exist'
    from babblet.runner import process_file
    from babblet.core import Pipeline
    source = tmp_path / 'speech.wav'
    sf.write(source, np.ones(16000, dtype=np.float32) * 0.1, 16000)
    class Recognizer:
        def transcribe(self, audio, language=None):
            assert len(audio) == 16000
            return [{'text': 'Hello world', 'language': 'en', 'start': 0, 'end': 1}]
    class Translator:
        async def translate(self, *args):
            return 'translated'
    async def run():
        pipeline = Pipeline(Translator())
        result = await process_file(source, Recognizer(), pipeline)
        await pipeline.drain()
        assert result['audio_seconds'] == 1
        assert result['segments'] == 1
        assert result['asr_seconds'] >= 0
        assert pipeline.snapshot()['health']['completed'] == 3
    asyncio.run(run())


def test_recording_runner_awaits_translation_when_requested(tmp_path):
    from babblet.runner import process_file
    from babblet.core import Pipeline
    source = tmp_path / 'speech.wav'
    sf.write(source, np.ones(16000, dtype=np.float32) * 0.1, 16000)
    class Recognizer:
        def transcribe(self, *args):
            return [{'text': 'Hello world', 'language': 'en', 'start': 0, 'end': 1}
                    for _ in range(10)]
    class Translator:
        async def translate(self, *args):
            return 'translated'
    async def run():
        pipeline = Pipeline(Translator(), max_pending=3)
        await process_file(source, Recognizer(), pipeline, wait_translation=True)
        assert pipeline.health['completed'] == 30
        assert pipeline.health['dropped'] == 0
    asyncio.run(run())
