import asyncio
import importlib.util

import numpy as np


def adapters():
    assert importlib.util.find_spec('babblet.adapters'), 'Model adapters must exist'
    from babblet.adapters import Translator, SpeechRecognizer, Segmenter
    return Translator, SpeechRecognizer, Segmenter


def test_translation_http_contract_and_truncation():
    Translator, _, _ = adapters()
    import httpx
    async def run():
        def respond(request):
            assert request.url.host == '127.0.0.1'
            assert b'Russian' in request.content
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': 'Привет мир'}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            engine = Translator(client=client)
            assert await engine.translate('Hello world', 'en', 'ru') == 'Привет мир'
    asyncio.run(run())


def test_silence_is_not_sent_to_recognizer():
    _, SpeechRecognizer, _ = adapters()
    class Forbidden:
        def transcribe(self, *args, **kwargs):
            raise AssertionError('Silence must not reach the recognizer')
    recognizer = SpeechRecognizer(model=Forbidden())
    assert recognizer.transcribe(np.zeros(16000, dtype=np.float32)) == []


def test_segmentation_preserves_preroll_and_caps_continuous_speech():
    _, _, Segmenter = adapters()
    segmenter = Segmenter(sample_rate=1000, frame_ms=100, pause_ms=300, max_seconds=1)
    silence = np.zeros(100, dtype=np.float32)
    voice = np.ones(100, dtype=np.float32) * 0.1
    assert segmenter.push(silence) is None
    assert segmenter.push(voice) is None
    assert segmenter.push(silence) is None
    assert segmenter.push(silence) is None
    clip = segmenter.push(silence)
    assert clip is not None and len(clip) >= 400
    clips = [segmenter.push(voice) for _ in range(20)]
    assert sum(x is not None for x in clips) >= 2
