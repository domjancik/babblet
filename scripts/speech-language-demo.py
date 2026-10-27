"""Model-free UI fixture using detection metadata from the synthetic smoke test."""
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from babblet.core import Pipeline
from babblet.speech_languages import SpeechGuidance
from babblet.web import create_app

guide=SpeechGuidance(['en'])
report=json.loads(Path('artifacts/speech-language-smoke-test.json').read_text(encoding='utf-8'))
evidence=report['guidance']['detected']
for _ in range(2):
    guide.observe(evidence['code'],evidence['probability'],3)
if __name__=='__main__':
    uvicorn.run(create_app(Pipeline(None),{'state':'synthetic detection test'},guidance=guide,
                          speech_path=Path('.cache/test-speech-languages.json')),
                host='127.0.0.1',port=8091,log_level='warning')
