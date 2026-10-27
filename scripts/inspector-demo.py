"""Model-free, synthetic candidate comparison for inspector UI verification."""
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import uvicorn
from babblet.core import Pipeline
from babblet.hebrew import HebrewSecondRecognizer
from babblet.web import create_app


class Fixture:
    def __init__(self,text,score): self.text=text;self.score=score
    def transcribe(self,*args):
        return [{'text':self.text,'language':'he','start':0,'end':3,
                 'avg_logprob':self.score,'no_speech_prob':.01,'compression_ratio':1.2}]


if __name__=='__main__':
    trace={}
    recognizer=HebrewSecondRecognizer(Fixture('שלום עולם',-.4),
        Fixture('שלום לכולם',-.2),trace=trace)
    recognizer.transcribe(np.ones(48000,dtype=np.float32),refine=True)
    status={'state':'ready','hebrew_recognizer':{'enabled':True,'device':'cpu'},
            'recognition_trace':trace}
    uvicorn.run(create_app(Pipeline(None),status),host='127.0.0.1',port=8091,log_level='warning')
