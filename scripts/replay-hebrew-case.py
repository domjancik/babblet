"""Local replay of the three user-labelled Hebrew debugging recordings."""
import json
import argparse
import asyncio
import re
import shutil
import sys
from pathlib import Path

import soundfile as sf

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from babblet.adapters import SpeechRecognizer,Translator
from babblet.hebrew import candidate_summary,HebrewSecondRecognizer,HebrewWorker
from babblet.speech_languages import SpeechGuidance

CASES=[('clip-1793087355403425200-cea994.wav','אז עכשיו זה עובד?'),
       ('clip-1793087361781241700-323637.wav','זה לא עובד עכשיו'),
       ('clip-1793087367790362100-533d48.wav','זה לא יותר טוב')]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--verify',action='store_true')
    args=parser.parse_args()
    destination=Path('artifacts/hebrew-debug-case')
    destination.mkdir(exist_ok=True)
    cases=[]
    for filename,expected in CASES:
        source=Path('artifacts/debug-audio')/filename
        saved=destination/filename
        if not saved.exists():
            shutil.copy2(source,saved)
            shutil.copy2(source.with_suffix('.json'),saved.with_suffix('.json'))
        cases.append({'file':filename,'expected':expected,'results':{}})
    if args.verify:
        primary=SpeechRecognizer(device='cpu',guidance=SpeechGuidance(['cs','he']))
        dual=HebrewSecondRecognizer(primary,HebrewWorker('models/whisper-hebrew'))
        translator=Translator()
        try:
            for case in cases:
                audio,rate=sf.read(destination/case['file'],dtype='float32')
                result=dual.transcribe(audio,refine=True)
                text=' '.join(segment['text'] for segment in result)
                normalize=lambda value:re.sub(r'[^\w\s]','',value).strip()
                case['passed']=normalize(text)==normalize(case['expected'])
                case['trace']=dict(dual.trace)
                case['translations']={code:asyncio.run(translator.translate(text,'he',code))
                                      for code in ['cs','ru','he']}
                print(json.dumps({'expected':case['expected'],'text':text,'passed':case['passed'],
                    'route':dual.trace['routing'],'selected':dual.trace['selected'],
                    'translations':case['translations']},ensure_ascii=False),flush=True)
            (destination/'verified.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
            return int(not all(case['passed'] for case in cases))
        finally:
            dual.close()
    for mode,path,language in [('automatic','models/whisper-turbo',None),
            ('primary_hebrew','models/whisper-turbo','he'),
            ('specialist','models/whisper-hebrew','he')]:
        recognizer=SpeechRecognizer(path,device='cpu',guidance=SpeechGuidance(['cs','he']))
        for case in cases:
            audio,rate=sf.read(destination/case['file'],dtype='float32')
            assert rate==16000
            result=recognizer.transcribe(audio,language=language,refine=True)
            case['results'][mode]={'candidate':candidate_summary(result),
                                   'detection':recognizer.last_detection}
            print(json.dumps({'expected':case['expected'],'mode':mode,
                              'result':case['results'][mode]},ensure_ascii=False),flush=True)
        del recognizer
    (destination/'comparison.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    raise SystemExit(main())
