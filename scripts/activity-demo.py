"""Model-free, synthetic activity-indicator QA fixture on port 8091."""
import asyncio
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import uvicorn
from babblet.core import Pipeline
from babblet.refinement import SpeechSession
from babblet.web import create_app

class Recognizer:
    def transcribe(self,audio,language=None,refine=False):
        time.sleep(5)
        return [{'text':'Testing the processing indicator.','language':'en','start':0,'end':1}]
class Translator:
    async def translate(self,*args):
        await asyncio.sleep(5)
        return 'Testing the processing indicator.'

pipeline=Pipeline(Translator(),targets=['en'],max_age=30)
status={'state':'listening'}
async def exercise():
    while True:
        session=SpeechSession(Recognizer(),pipeline,activity=status)
        await session.process(np.ones(16000,dtype=np.float32)*.1,0,'limit')
        await session.process(np.zeros(8000,dtype=np.float32),1,'pause')
        await asyncio.sleep(.25)
        pipeline.discard([{'utterance_id':uid,'revision':item['revision']} for uid,item in list(pipeline.items.items())])
@asynccontextmanager
async def lifespan(app):
    tasks=[asyncio.create_task(pipeline.run()),asyncio.create_task(exercise())]
    try: yield
    finally:
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
app=create_app(pipeline,status)
app.router.lifespan_context=lifespan
if __name__=='__main__':
    uvicorn.run(app,host='127.0.0.1',port=8091,log_level='warning')
