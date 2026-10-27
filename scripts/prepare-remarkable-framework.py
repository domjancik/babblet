"""Download and package reviewed upstream prerequisites; never runs on tablet."""
import hashlib
import io
import json
import tarfile
from pathlib import Path

import httpx

ROOT=Path(__file__).resolve().parents[1]
ASSETS=[
    ('xovi-arm32.so','https://github.com/asivery/xovi/releases/download/v0.3.3/xovi-arm32.so',
     '2878d88da2dcb37dcf5533fa78aeeb5cc933eb8c7e5b9041213a4e135a7fff14'),
    ('xovi-arm32.tar.gz','https://github.com/asivery/rm-xovi-extensions/releases/download/v19-23052026/xovi-arm32.tar.gz',
     '9aa00537ad41e9be0c3151992bfc25106465318cf5bb4c41cf59b3ddd4866377'),
    ('appload-arm32.tar.gz','https://github.com/asivery/rm-appload/releases/download/v0.6.0/appload-arm32.tar.gz',
     '25aa54735742ea63c0a043cba5496987dd4ca742d8b3fc26a21b7368372bf44f'),
]


def main():
    output=ROOT/'artifacts/remarkable/prerequisites'
    output.mkdir(parents=True,exist_ok=True)
    for name,url,digest in ASSETS:
        path=output/name
        if not path.exists():
            response=httpx.get(url,follow_redirects=True,timeout=60);response.raise_for_status()
            path.write_bytes(response.content)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Upstream checksum mismatch: '+name)
    archive=output/'babblet-launcher-prerequisites.tar.gz'
    with tarfile.open(archive,'w:gz') as target:
        with tarfile.open(output/'xovi-arm32.tar.gz') as source:
            for member in source:
                # Keep upstream scaffolding, but omit inactive extensions not
                # required by this app. Preserve its two reviewed absolute links.
                if member.name.startswith('xovi/inactive-extensions') or member.name=='xovi/xovi.so':
                    continue
                if member.name.startswith('/') or '..' in Path(member.name).parts:
                    raise ValueError('Unsafe archive path')
                if member.issym() and member.linkname not in ['/home/root/xovi/exthome','/home/root/xovi/extensions.d']:
                    raise ValueError('Unexpected upstream symlink')
                target.addfile(member,source.extractfile(member) if member.isfile() else None)
        info=tarfile.TarInfo('xovi/xovi.so');content=(output/'xovi-arm32.so').read_bytes()
        info.size=len(content);info.mode=0o755;target.addfile(info,io.BytesIO(content))
        with tarfile.open(output/'appload-arm32.tar.gz') as source:
            member=source.getmember('appload.so');content=source.extractfile(member).read()
            member.name='xovi/extensions.d/appload.so'
            target.addfile(member,io.BytesIO(content))
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.gz.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    (output/'sources.json').write_text(json.dumps([{'file':n,'url':u,'sha256':h} for n,u,h in ASSETS],indent=2),encoding='utf-8')
    print('Prepared pinned AppLoad 0.6.0 + XOVI 0.3.3 + resource rebuilder v19 for review.')
    print('No files installed and no tablet service changed.')


if __name__=='__main__': main()
