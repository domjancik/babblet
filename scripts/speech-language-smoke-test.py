"""Validate guidance and outsider suggestions using local synthetic fixtures."""
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from faster_whisper.audio import decode_audio
from babblet.adapters import SpeechRecognizer
from babblet.speech_languages import SpeechGuidance

guide=SpeechGuidance(['en','he','ru'])
recognizer=SpeechRecognizer(guidance=guide)
results=[]
for language,name in [('en','en.wav'),('he','he.mp3'),('ru','ru.mp3')]:
    output=recognizer.transcribe(decode_audio(str(Path('artifacts/audio')/name)),refine=True)
    detected=guide.snapshot()['detected']
    passed=bool(output) and output[0]['language']==language
    results.append({'language':language,'passed':passed,'detection':detected})
    print(f'{language} guided recognition passed={passed}',flush=True)
guide=SpeechGuidance(['en'])
recognizer.guidance=guide
hebrew=decode_audio('artifacts/audio/he.mp3')
for _ in range(2):
    output=recognizer.transcribe(hebrew,refine=True)
outsider=bool(output) and output[0]['language']=='he'
suggested=any(item['code']=='he' for item in guide.snapshot()['suggested'])
report={'synthetic_audio_only':True,'passed':all(r['passed'] for r in results) and outsider and suggested,
    'results':results,'clear_outsider_recognized':outsider,'outsider_suggested':suggested,
    'guidance':guide.snapshot()}
Path('artifacts/speech-language-smoke-test.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
raise SystemExit(int(not report['passed']))
