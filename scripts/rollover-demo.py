"""Synthetic, model-free browser fixture for ephemeral page rollover QA."""
import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import uvicorn
from babblet.core import Pipeline
from babblet.web import create_app

class FixtureTranslator:
    async def translate(self,text,source,target):
        if target=='en':
            return text
        number=text.split(':',1)[0]
        if target=='he':
            return f'{number}: '+('זהו דף זמני של שיחה חיה. המילים נכתבות מלמעלה למטה. כשהדף מלא, הוא מתנקה ואנחנו מתחילים שוב. '*(6 if args.long else 1))
        return f'{number}: '+('Это временная страница живого разговора. Слова появляются сверху вниз. Когда страница заполнена, она очищается и начинается новая. '*(6 if args.long else 1))

parser=argparse.ArgumentParser()
parser.add_argument('--long',action='store_true')
args=parser.parse_args()
pipeline=Pipeline(FixtureTranslator())
async def seed():
    for index in range(1,2 if args.long else 7):
        await pipeline.submit(f'page-test-{index}',
            f'{index}: '+('This is a temporary page of a live conversation. Words flow from top to bottom. When the page fills, it clears and we start again. '*(6 if args.long else 1)),
            'en',index,index+1)
        await pipeline.drain()
asyncio.run(seed())
if __name__=='__main__':
    uvicorn.run(create_app(pipeline,{'state':'synthetic rollover test'}),host='127.0.0.1',port=8091,log_level='warning')
