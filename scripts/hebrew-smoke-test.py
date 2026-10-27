"""Real local models; only the existing synthetic speech fixtures are recorded."""
import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from faster_whisper.audio import decode_audio
from babblet.adapters import SpeechRecognizer,Translator
from babblet.core import Pipeline
from babblet.hebrew import HebrewSecondRecognizer,HebrewWorker
from babblet.refinement import SpeechSession
from babblet.speech_languages import SpeechGuidance


def error_rate(reference,hypothesis):
    words=lambda text:re.findall(r'[^\W_]+',text.lower(),re.UNICODE)
    left,right=words(reference),words(hypothesis)
    previous=list(range(len(right)+1))
    for index,word in enumerate(left,1):
        row=[index]
        for offset,other in enumerate(right,1):
            row.append(min(previous[offset]+1,row[-1]+1,previous[offset-1]+(word!=other)))
        previous=row
    return previous[-1]/max(1,len(left))


async def run(device):
    primary=SpeechRecognizer(device=device,guidance=SpeechGuidance(['cs','he']))
    worker=HebrewWorker('models/whisper-hebrew',device='cpu',timeout=12)
    dual=HebrewSecondRecognizer(primary,worker)
    results=[]
    try:
        for code,name,reference in [
            ('he','he.mp3','שלום לכולם. זהו מבחן תרגום מקומי. הטאבלט מציג את השיחה בעברית, באנגלית וברוסית.'),
            ('en','en.wav','Hello everyone. This is an offline translation test. The tablet shows the conversation in English, Hebrew, and Russian.'),
            ('ru','ru.mp3','Здравствуйте. Это проверка перевода без интернета. Планшет показывает разговор на русском, английском и иврите.')]:
            audio=decode_audio(str(Path('artifacts/audio')/name))
            before=primary.transcribe(audio,refine=True)
            started=time.perf_counter();after=dual.transcribe(audio,refine=True)
            before_text=' '.join(segment['text'] for segment in before)
            after_text=' '.join(segment['text'] for segment in after)
            passed=bool(after) and after[0]['language']==code
            passed=passed and (dual.last_comparison['reason']!='secondary_failed')
            if code!='he': passed=passed and dual.last_comparison['reason']=='not_hebrew'
            results.append({'language':code,'passed':passed,'before':before_text,'after':after_text,
                'before_wer':error_rate(reference,before_text),'after_wer':error_rate(reference,after_text),
                'total_seconds':round(time.perf_counter()-started,3),
                'comparison':dict(dual.last_comparison)})
            print(f'{code}: passed={passed}, winner={dual.last_comparison["selected"]}, '
                  f'secondary_seconds={dual.last_comparison["secondary_seconds"]}',flush=True)
        pipeline=Pipeline(Translator(),targets=['en','he'],max_age=30)
        status={};session=SpeechSession(dual,pipeline,activity=status)
        audio=decode_audio('artifacts/audio/he.mp3')
        await session.process(audio[:32000],0,'limit')
        uid=next(iter(pipeline.items))
        await session.process(audio[32000:],2,'pause')
        await pipeline.drain()
        final=pipeline.items[uid]
        integrated=(len(pipeline.items)==1 and final['phase']=='final' and final['revision']>=2
                    and all(value['status']=='complete' for value in final['translations'].values())
                    and status['recognition']['reason']!='secondary_failed')
        report={'synthetic_audio_only':True,'primary_device':device,'secondary_device':'cpu',
                'results':results,'pipeline_passed':integrated,'final':final,
                'passed':integrated and all(item['passed'] for item in results)}
        report_path='artifacts/hebrew-smoke-test-cpu.json' if device=='cpu' else 'artifacts/hebrew-smoke-test.json'
        Path(report_path).write_text(
            json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'Joined-audio refinement and translation: passed={integrated}',flush=True)
        return int(not report['passed'])
    finally:
        dual.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--device',choices=['cuda','cpu'],default='cuda')
    raise SystemExit(asyncio.run(run(parser.parse_args().device)))
