"""Download only official model files and a pinned upstream Windows runtime.

Run once online. Inference uses local_files_only and offline environment flags.
"""
import argparse
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
HY_REVISION = 'a0c709d9fac510f2c807aa3af52872340dc37a4a'
LLAMA_BUILD = 'b11905'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--benchmark-models', action='store_true')
    parser.add_argument('--all-translation-models', action='store_true',help='Download Q8 and Q4 without the optional NLLB benchmark model')
    args = parser.parse_args()
    quantizations = ['Q4_K_M', 'Q8_0'] if args.benchmark_models or args.all_translation_models else ['Q8_0']
    for quant in quantizations:
        hf_hub_download('tencent/Hy-MT2-1.8B-GGUF', f'Hy-MT2-1.8B-{quant}.gguf',
                        revision=HY_REVISION, local_dir=ROOT/'models/hymt2')
    snapshot_download('mobiuslabsgmbh/faster-whisper-large-v3-turbo',
        revision='0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf',
        local_dir=ROOT/'models/whisper-turbo', allow_patterns=['*.json','*.txt','*.bin'])
    if args.benchmark_models:
        snapshot_download('facebook/nllb-200-distilled-600M', local_dir=ROOT/'models/nllb',
            revision='f8d333a098d19b4fd9a8b18f94170487ad3f821d',
            allow_patterns=['config.json','generation_config.json','pytorch_model.bin',
                'sentencepiece.bpe.model','tokenizer.json','tokenizer_config.json','special_tokens_map.json'])
    runtime = ROOT/'runtime'
    runtime.mkdir(exist_ok=True)
    for name in [f'llama-{LLAMA_BUILD}-bin-win-cuda-12.4-x64.zip',
                 'cudart-llama-bin-win-cuda-12.4-x64.zip']:
        url = f'https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_BUILD}/{name}'
        archive = runtime/name
        urllib.request.urlretrieve(url, archive)
        with zipfile.ZipFile(archive) as bundle:
            for entry in bundle.infolist():
                destination = (runtime/'llama'/entry.filename).resolve()
                if not destination.is_relative_to((runtime/'llama').resolve()):
                    raise ValueError('Unsafe archive entry')
            bundle.extractall(runtime/'llama')
        archive.unlink()
    # A reproducibility receipt; not an independently authenticated checksum list.
    files = []
    for path in (ROOT/'models').rglob('*'):
        if path.is_file() and '.cache' not in path.parts:
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            files.append({'file': str(path.relative_to(ROOT)), 'sha256': digest,
                          'bytes': path.stat().st_size})
    (runtime/'model-manifest.json').write_text(json.dumps(files, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
