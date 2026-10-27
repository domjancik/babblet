"""Reproducible, offline comparison of three local translation models."""
import argparse
import asyncio
import json
import statistics
import subprocess
import time
from pathlib import Path

import httpx

from babblet.adapters import SpeechRecognizer, Translator

PARALLEL = [
    {'en': 'The tablet displays the conversation in English, Hebrew, and Russian.',
     'he': 'הטאבלט מציג את השיחה באנגלית, בעברית וברוסית.',
     'ru': 'Планшет показывает разговор на английском, иврите и русском.'},
    {'en': 'Please speak slowly. I do not understand Russian.',
     'he': 'בבקשה דברו לאט. אני לא מבין רוסית.',
     'ru': 'Пожалуйста, говорите медленно. Я не понимаю русский.'},
    {'en': 'We will meet tomorrow at three near the entrance.',
     'he': 'ניפגש מחר בשעה שלוש ליד הכניסה.',
     'ru': 'Мы встретимся завтра в три часа возле входа.'},
    {'en': 'Where can I find drinking water?',
     'he': 'איפה אפשר למצוא מי שתייה?',
     'ru': 'Где можно найти питьевую воду?'},
]


def cases():
    return [{'id': f'parallel-{i}-{source}-{target}', 'kind': 'parallel',
             'text': row[source], 'source': source, 'target': target,
             'reference': row[target]}
            for i, row in enumerate(PARALLEL)
            for source in row for target in row if target != source]


def summarize(rows):
    good = [r for r in rows if not r['error']]
    times = sorted(r['seconds'] for r in good)
    scores = [r['chrf'] for r in good if r.get('chrf') is not None]
    return {'completed': len(good), 'errors': len(rows)-len(good),
            'median_seconds': statistics.median(times) if times else None,
            'p95_seconds': times[min(len(times)-1, int(len(times)*0.95))] if times else None,
            'mean_chrf': statistics.mean(scores) if scores else None}


class NllbTranslator:
    def __init__(self, path='models/nllb', device='cuda'):
        import torch
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        self.torch, self.device = torch, device
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(path, local_files_only=True,
            torch_dtype=torch.float16 if device == 'cuda' else torch.float32).to(device).eval()
        self.codes = {'en': 'eng_Latn', 'he': 'heb_Hebr', 'ru': 'rus_Cyrl'}

    def generate(self, text, source, target):
        self.tokenizer.src_lang = self.codes[source]
        inputs = self.tokenizer(text, return_tensors='pt')
        if inputs['input_ids'].shape[-1] > 512:
            raise ValueError('NLLB input exceeds 512 tokens')
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with self.torch.inference_mode():
            output = self.model.generate(**inputs,
                forced_bos_token_id=self.tokenizer.convert_tokens_to_ids(self.codes[target]),
                max_new_tokens=256, num_beams=1, do_sample=False)
        return self.tokenizer.batch_decode(output, skip_special_tokens=True)[0].strip()

    async def translate(self, text, source, target):
        return await asyncio.to_thread(self.generate, text, source, target)


def gpu_memory():
    try:
        return subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used',
            '--format=csv,noheader,nounits'], text=True, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        return None


async def run(args):
    from sacrebleu.metrics import CHRF
    score = CHRF(word_order=2)
    items = cases()
    asr_file = Path('artifacts/three-language-cpu-mt.json')
    if asr_file.exists():
        transcripts = json.loads(asr_file.read_text(encoding='utf-8'))['utterances']
        for i, utterance in enumerate(transcripts):
            for target in ('en', 'he', 'ru'):
                if target != utterance['source_language']:
                    items.append({'id': f'asr-{i}-{target}', 'kind': 'asr',
                        'text': utterance['source_text'], 'source': utterance['source_language'],
                        'target': target, 'reference': None})
    output_dir = Path('artifacts/benchmark')
    output_dir.mkdir(parents=True, exist_ok=True)
    # Keep ASR resident so MT memory measurements reflect the intended deployment.
    recognizer = SpeechRecognizer()
    base_memory = gpu_memory()
    process = None
    log = None
    started = time.perf_counter()
    if args.model == 'nllb':
        engine = NllbTranslator()
    else:
        quant = 'Q4_K_M' if args.model == 'q4' else 'Q8_0'
        key_file = Path('runtime/translation.key')
        log = (output_dir / f'{args.model}-server.log').open('w', encoding='utf-8')
        process = subprocess.Popen([str(Path('runtime/llama/llama-server.exe').resolve()),
            '-m', f'models/hymt2/Hy-MT2-1.8B-{quant}.gguf',
            '--host', '127.0.0.1', '--port', '18082', '-ngl', '99', '-c', '2048',
            '--parallel', '1', '--api-key-file', str(key_file), '--no-webui'], stdout=log, stderr=log)
        ready = False
        async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
            for _ in range(120):
                if process.poll() is not None:
                    break
                try:
                    response = await client.get('http://127.0.0.1:18082/health')
                    if response.status_code == 200:
                        ready = True
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.5)
        if not ready:
            process.terminate()
            process.wait(timeout=10)
            log.close()
            raise RuntimeError(f'{args.model} server not ready; inspect benchmark log')
        engine = Translator('http://127.0.0.1:18082/v1')
    load_seconds = time.perf_counter() - started
    results = []
    peak = int(gpu_memory() or 0)
    try:
        # Separate cold generation from timed cases.
        await engine.translate('Hello.', 'en', 'ru')
        for item in items:
            start = time.perf_counter()
            error, text = None, None
            try:
                text = await asyncio.wait_for(engine.translate(item['text'], item['source'], item['target']), 30)
                if not text:
                    raise ValueError('Empty translation')
            except Exception as exc:
                error = type(exc).__name__ + ': ' + str(exc)
            elapsed = time.perf_counter() - start
            metric = score.sentence_score(text, [item['reference']]).score if text and item['reference'] else None
            results.append({**item, 'output': text, 'seconds': elapsed, 'error': error, 'chrf': metric})
            peak = max(peak, int(gpu_memory() or 0))
            print(f'{args.model} {len(results)}/{len(items)} {elapsed:.3f}s {error or "ok"}', flush=True)
    finally:
        if process:
            process.terminate()
            process.wait(timeout=10)
            log.close()
    report = {'model': args.model, 'load_seconds': load_seconds,
        'asr_resident': True, 'gpu_base_mib': base_memory, 'gpu_peak_system_mib': peak,
        'summary': summarize(results), 'directions': {}, 'results': results,
        'caveat': 'Tiny synthetic/curated corpus. chrF is lexical similarity to one reference, not human adequacy. GPU memory is system-wide sampled usage.'}
    for source in ('en','he','ru'):
        for target in ('en','he','ru'):
            if source != target:
                report['directions'][f'{source}->{target}'] = summarize([
                    r for r in results if r['source']==source and r['target']==target])
    (output_dir / f'{args.model}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'}, ensure_ascii=True, indent=2))
    return int(report['summary']['errors'] > 0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('model', choices=['q4', 'q8', 'nllb'])
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == '__main__':
    main()
