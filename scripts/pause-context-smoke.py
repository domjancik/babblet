"""Verify a pause-split local synthetic Hebrew recording is decoded as one row."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from faster_whisper.audio import decode_audio
from babblet.adapters import SpeechRecognizer,Translator
from babblet.core import Pipeline
from babblet.hebrew import HebrewSecondRecognizer,HebrewWorker
from babblet.refinement import SpeechSession
from babblet.speech_languages import SpeechGuidance


async def main():
    dual=HebrewSecondRecognizer(SpeechRecognizer(device='cpu',guidance=SpeechGuidance(['cs','he'])),
        HebrewWorker('models/whisper-hebrew'))
    pipeline=Pipeline(Translator(),targets=['cs','ru','he'],max_age=30)
    status={};session=SpeechSession(dual,pipeline,activity=status)
    try:
        audio=decode_audio('artifacts/audio/he.mp3')
        await session.process(audio[:32000],0,'pause')
        uid=next(iter(pipeline.items))
        await session.process(audio[32000:],2.3,'pause')
        await pipeline.drain()
        item=pipeline.items[uid]
        passed=(len(pipeline.items)==1 and item['revision']>=2 and item['phase']=='final'
                and item['source_language']=='he' and status['speech_context']['continuing_row']
                and status['recognition']['reason']!='secondary_failed'
                and all(result['status']=='complete' for result in item['translations'].values()))
        Path('artifacts/pause-context-smoke.json').write_text(json.dumps({
            'synthetic_audio_only':True,'passed':passed,'utterance':item,'status':status,
        },ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'Pause-split Hebrew: same row, joined audio and translations passed={passed}',flush=True)
        return int(not passed)
    finally:
        session.reset();dual.close()


if __name__=='__main__':
    raise SystemExit(asyncio.run(main()))
