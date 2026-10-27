"""Download a pinned Hebrew CTranslate2 model; inference remains offline."""
import hashlib
import json
from pathlib import Path

import httpx
from huggingface_hub import hf_hub_download

ROOT=Path(__file__).resolve().parents[1]
REPO='ivrit-ai/whisper-large-v3-turbo-ct2'
REVISION='72ad623a37947395efcc3933132353790e5a12f5'
MODEL_SHA256='db2a2265aa012c16c7db9edda3d699c99f984efdd3f2e22a72a8ce7e9720f3a2'


def main():
    destination=ROOT/'models/whisper-hebrew'
    destination.mkdir(parents=True,exist_ok=True)
    for name in ['config.json','preprocessor_config.json','tokenizer.json','vocabulary.json']:
        hf_hub_download(REPO,name,revision=REVISION,local_dir=destination)
    model=destination/'model.bin'
    if not model.exists():
        # HTTP streaming avoids the optional Xet transport stalling on this host.
        temporary=destination/'model.bin.part'
        digest=hashlib.sha256();written=0;reported=0
        with httpx.stream('GET',f'https://huggingface.co/{REPO}/resolve/{REVISION}/model.bin',
                          follow_redirects=True,timeout=60) as response:
            response.raise_for_status()
            with temporary.open('wb') as output:
                for chunk in response.iter_bytes(1024*1024):
                    output.write(chunk);digest.update(chunk);written+=len(chunk)
                    if written-reported>=64*1024*1024:
                        print(f'Hebrew model: {written//(1024*1024)} MiB downloaded',flush=True)
                        reported=written
        if digest.hexdigest()!=MODEL_SHA256:
            raise ValueError('Hebrew model SHA-256 mismatch')
        temporary.replace(model)
    with model.open('rb') as stream:
        actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=MODEL_SHA256:
        raise ValueError('Installed Hebrew model SHA-256 mismatch')
    (destination/'revision.json').write_text(json.dumps({'repo':REPO,'revision':REVISION,
        'model_sha256':actual}),encoding='utf-8')
    print('Hebrew recognizer installed and verified.',flush=True)


if __name__=='__main__':
    main()
