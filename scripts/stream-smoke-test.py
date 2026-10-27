"""Exercise the live endpointing path with deterministic recorded PCM frames."""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from faster_whisper.audio import decode_audio

from babblet.adapters import Segmenter, SpeechRecognizer, Translator
from babblet.core import Pipeline


async def main():
    recognizer = SpeechRecognizer()
    pipeline = Pipeline(Translator(), max_age=30)
    results = []
    started = time.perf_counter()
    for language, name in [('en','en.wav'), ('he','he.mp3'), ('ru','ru.mp3')]:
        segmenter = Segmenter()
        audio = decode_audio(str(Path('artifacts/audio')/name))
        audio = np.concatenate([audio, np.zeros(16000,dtype=np.float32)])
        before = set(pipeline.items)
        clips = 0
        for offset in range(0, len(audio), 1600):
            clip = segmenter.push(audio[offset:offset+1600])
            if clip is None:
                continue
            clips += 1
            segments = await asyncio.to_thread(recognizer.transcribe, clip)
            for i, segment in enumerate(segments):
                await pipeline.submit(f'{language}:{clips}:{i}',segment['text'],segment['language'],
                                      segment['start'],segment['end'])
                await pipeline.drain()
        items = [item for uid,item in pipeline.items.items() if uid not in before]
        passed = bool(items) and all(item['source_language']==language for item in items)
        results.append({'language':language,'clips':clips,'utterances':len(items),
                        'passed':passed,'source_text':' '.join(x['source_text'] for x in items)})
        print(f'{language}: {clips} live-path clips, {len(items)} utterances, {passed}',flush=True)
    health = pipeline.snapshot()['health']
    passed = all(item['passed'] for item in results) and all(health[k]==0 for k in ('errors','dropped','expired','pending'))
    report = {'passed':passed,'elapsed_seconds':time.perf_counter()-started,
        'health':health,'results':results,'snapshot':pipeline.snapshot(),
        'limitation':'Recorded frames use the live segmenter but are not a physical microphone/device reconnect or real-time scheduling test.'}
    Path('artifacts/stream-smoke-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return int(not passed)


if __name__=='__main__':
    raise SystemExit(asyncio.run(main()))
