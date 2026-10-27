"""Synthetic preview of a pending utterance in the next fixed FIFO row."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from babblet.core import Pipeline
from babblet.web import create_app


class Translator:
    async def translate(self,text,source,target):
        return {'en':'A conversation is in progress.','he':'השיחה נמשכת.','cs':'Rozhovor pokračuje.'}[target]


async def main():
    pipeline=Pipeline(Translator(),targets=['en','cs','he'])
    for index in range(6):
        await pipeline.submit(str(index),'A conversation is in progress.','en',index,index+1)
        await pipeline.drain()
    status={'state':'listening','asr_phase':'refining','asr_utterance_id':'next-utterance',
            'recognition_trace':{'phase':'decoding_hebrew'}}
    await uvicorn.Server(uvicorn.Config(create_app(pipeline,status),host='127.0.0.1',port=8091,
                                      log_level='warning')).serve()


if __name__=='__main__':
    asyncio.run(main())
