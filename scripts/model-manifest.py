"""Record hashes of existing local model files without redownloading them."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = []
for path in (root/'models').rglob('*'):
    if path.is_file() and '.cache' not in path.parts:
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        files.append({'file': str(path.relative_to(root)),
                      'bytes': path.stat().st_size, 'sha256': digest})
(root/'runtime/model-manifest.json').write_text(json.dumps(files, indent=2), encoding='utf-8')
print(f'Model manifest recorded: {len(files)} files')
