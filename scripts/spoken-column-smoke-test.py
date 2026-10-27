"""Check real translation output independently of raw speech and ASR labels."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from babblet.adapters import Translator
from babblet.core import Pipeline
from babblet.web import create_app


async def main(serve):
    pipeline=Pipeline(Translator(),targets=['en'],max_age=30)
    records=[]
    for uid,text,source in [
        ('mislabel','Bonjour tout le monde.','en'),
        ('fr','Bonjour tout le monde.','fr'),
        ('he','שלום לכולם.','he'),
        ('ru','Здравствуйте всем.','ru'),
        ('en','Hello everyone.','en')]:
        await pipeline.submit(uid,text,source,0,2)
        await pipeline.drain()
        item=pipeline.items[uid]
        result=item['translations']['en']
        passed=(item['source_text']==text and result['status']=='complete'
                and 'hello' in (result['text'] or '').lower())
        records.append({'case':uid,'raw':text,'english':result['text'],'passed':passed})
        print(f'{uid}: English output passed={passed}',flush=True)
    passed=all(item['passed'] for item in records)
    Path('artifacts/spoken-column-smoke-test.json').write_text(
        json.dumps({'synthetic_text_only':True,'passed':passed,'records':records},ensure_ascii=False,indent=2),encoding='utf-8')
    pipeline.discard([{'utterance_id':'mislabel','revision':1}])
    if serve:
        import uvicorn
        await uvicorn.Server(uvicorn.Config(create_app(pipeline,{'state':'synthetic source test'}),
            host='127.0.0.1',port=8091,log_level='warning')).serve()
    return int(not passed)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--serve',action='store_true')
    raise SystemExit(asyncio.run(main(parser.parse_args().serve)))
