"""Force mid-sentence cuts and verify the real pause refinement replaces drafts."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from faster_whisper.audio import decode_audio
from babblet.adapters import SpeechRecognizer, Translator
from babblet.core import Pipeline
from babblet.refinement import SpeechSession
from babblet.web import create_app


async def main(serve):
    recognizer = SpeechRecognizer()
    pipeline = Pipeline(Translator(),max_age=30)
    records = []
    for language,name in [('en','en.wav'),('he','he.mp3'),('ru','ru.mp3')]:
        session = SpeechSession(recognizer,pipeline)
        audio = decode_audio(str(Path('artifacts/audio')/name))
        before = set(pipeline.items)
        drafts = 0
        for offset in range(0,len(audio),32000):
            clip = audio[offset:offset+32000]
            boundary = 'pause' if offset+len(clip)==len(audio) else 'limit'
            await session.process(clip,offset/16000,boundary)
            await pipeline.drain()
            if boundary=='limit':
                drafts += 1
        items = [v for uid,v in pipeline.items.items() if uid not in before]
        passed = (len(items)==1 and items[0]['phase']=='final' and
                  items[0]['source_language']==language and
                  all(t['status'] in ('source','complete') for t in items[0]['translations'].values()))
        records.append({'language':language,'forced_cuts':drafts,'passed':passed,
                        'final':items})
        print(f'{language}: {drafts} forced cuts, {len(items)} final paragraph, passed={passed}',flush=True)
    passed = all(r['passed'] for r in records)
    report = {'passed':passed,'records':records,'snapshot':pipeline.snapshot()}
    Path('artifacts/refinement-smoke-test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    if serve:
        import uvicorn
        worker = asyncio.create_task(pipeline.run())
        try:
            await uvicorn.Server(uvicorn.Config(create_app(pipeline,{'state':'test replay'}),
                host='127.0.0.1',port=8091,log_level='warning')).serve()
        finally:
            worker.cancel()
            await asyncio.gather(worker,return_exceptions=True)
    return int(not passed)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--serve',action='store_true')
    raise SystemExit(asyncio.run(main(parser.parse_args().serve)))
