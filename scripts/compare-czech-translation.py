"""Compare installed translation weights locally on the recorded-case texts."""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from babblet.adapters import Translator
from babblet.benchmark import NllbTranslator


async def main():
    import torch
    torch.set_num_threads(4)
    alternative=NllbTranslator(device='cpu')
    alternative.codes['cs']='ces_Latn'
    primary=Translator()
    rows=[]
    for text in ['זה לא יותר טוב','זה לא יותר טוב.','זה לא עובד עכשיו.',
                 'אז עכשיו זה עובד?','לא ראיתי שום דבר.']:
        started=time.perf_counter()
        nllb=await alternative.translate(text,'he','cs')
        elapsed=time.perf_counter()-started
        hymt=await primary.translate(text,'he','cs')
        row={'source':text,'hymt_q8':hymt,'nllb_600m':nllb,'nllb_seconds':round(elapsed,3)}
        rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    Path('artifacts/czech-model-check.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    asyncio.run(main())
