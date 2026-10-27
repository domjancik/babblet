"""Compare local translation prompts on short meaning-preservation cases."""
import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from babblet.adapters import Translator
from babblet.languages import CATALOG

CASES=[('זה לא יותר טוב','he','cs'),('זה לא יותר טוב.','he','cs'),('זה לא יותר טוב','he','ru'),
       ('זה לא עובד עכשיו','he','cs'),('אז עכשיו זה עובד?','he','cs'),
       ('לא ראיתי שום דבר','he','en'),('It is not better.','en','he'),
       ('Это не лучше.','ru','he')]


async def main():
    engine=Translator()
    rows=[]
    async with httpx.AsyncClient(timeout=30,trust_env=False) as client:
        for text,source,target in CASES:
            prefix=f'Translate the following text into {CATALOG[target]["name"]}. '
            end='Only output the translated result without any additional explanation:\n'+text
            prompts={
                'baseline':prefix+'Note that you should only output the translated result without any additional explanation:\n'+text,
                'source':f'Translate the following {CATALOG[source]["name"]} text into {CATALOG[target]["name"]}. '+end,
                'faithful':f'Translate the following {CATALOG[source]["name"]} text into {CATALOG[target]["name"]}. '
                    'Preserve the original meaning, negation, comparisons, tense, and questions. '
                    'Do not add facts or replace translation with transliteration. '+end,
            }
            outputs={}
            for variant,prompt in prompts.items():
                response=await client.post(engine.url+'/chat/completions',headers=engine.headers,
                    json={'model':'hymt2','messages':[{'role':'user','content':prompt}],
                          'temperature':0,'max_tokens':256,'stream':False})
                response.raise_for_status()
                outputs[variant]=response.json()['choices'][0]['message']['content'].strip()
            row={'text':text,'source':source,'target':target,'outputs':outputs}
            rows.append(row)
            print(json.dumps(row,ensure_ascii=False),flush=True)
    Path('artifacts/translation-prompt-check.json').write_text(
        json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    asyncio.run(main())
