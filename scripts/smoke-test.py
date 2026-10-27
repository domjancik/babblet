"""Run real local models repeatedly against the three generated audio fixtures."""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from sacrebleu.metrics import CHRF

from babblet.adapters import SpeechRecognizer, Translator
from babblet.core import Pipeline
from babblet.runner import process_file

REFERENCES = {
    'en': 'Hello everyone. This is an offline translation test. The tablet shows the conversation in English, Hebrew, and Russian.',
    'he': 'שלום לכולם. זהו מבחן תרגום מקומי. הטאבלט מציג את השיחה בעברית, באנגלית וברוסית.',
    'ru': 'Здравствуйте. Это проверка перевода без интернета. Планшет показывает разговор на русском, английском и иврите.',
}


async def run(rounds):
    recognizer = SpeechRecognizer()
    pipeline = Pipeline(Translator(), max_age=30)
    records = []
    metric = CHRF()
    started = time.perf_counter()
    for iteration in range(rounds):
        for language, name in [('en','en.wav'), ('he','he.mp3'), ('ru','ru.mp3')]:
            before = set(pipeline.items)
            begin = time.perf_counter()
            result = await process_file(Path('artifacts/audio')/name, recognizer,
                                        pipeline, wait_translation=True)
            additions = [v for k,v in pipeline.items.items() if k not in before]
            text = ' '.join(v['source_text'] for v in additions)
            passed = bool(additions) and all(v['source_language'] == language for v in additions)
            passed = passed and all(t['status'] in ('source','complete')
                for v in additions for t in v['translations'].values())
            records.append({**result, 'round': iteration+1, 'language': language,
                'end_to_end_seconds': time.perf_counter()-begin,
                'source_chrf': metric.sentence_score(text,[REFERENCES[language]]).score,
                'source_text': text, 'passed': passed})
            print(f'round {iteration+1} {language}: {"PASS" if passed else "FAIL"}', flush=True)
    silence = recognizer.transcribe(np.zeros(48000,dtype=np.float32))
    noise = recognizer.transcribe(np.random.default_rng(42).normal(0,.01,48000).astype(np.float32))
    health = pipeline.snapshot()['health']
    passed = all(r['passed'] for r in records) and not silence and not noise
    passed = passed and not any(health[k] for k in ('errors','expired','dropped','pending'))
    report = {'passed': passed, 'rounds': rounds, 'elapsed_seconds': time.perf_counter()-started,
        'silence_segments': len(silence), 'noise_segments': len(noise),
        'health': health, 'records': records, 'snapshot': pipeline.snapshot(),
        'limitations': 'Synthetic clean speech; does not validate room acoustics, microphone disconnects, code-switching or human translation adequacy.'}
    Path('artifacts/smoke-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('snapshot','records')},indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--rounds',type=int,default=5)
    args=parser.parse_args()
    raise SystemExit(asyncio.run(run(args.rounds)))
