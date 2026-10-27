"""Build a frontend-only AppLoad bundle; no ARM compiler or tablet changes."""
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from babblet.tablet import read_token


def build(output,paired=False):
    import PySide6
    stage=Path(output).resolve()/'babblet'
    stage.mkdir(parents=True,exist_ok=True)
    ui=stage/'ui';ui.mkdir(exist_ok=True)
    for name in ['Main.qml','TapButton.qml','ArtButton.qml','Fonts.qml']:
        shutil.copy2(ROOT/'remarkable/ui'/name,ui/name)
    token=read_token(ROOT/'runtime/tablet.key') if paired else ''
    (ui/'Config.js').write_text('.pragma library\nvar serverUrl = "http://127.0.0.1:8092"\nvar token = '+json.dumps(token)+'\n',encoding='utf-8')
    flags=stage/'flags';flags.mkdir(exist_ok=True)
    for path in (ROOT/'babblet/static/flags').glob('*.svg'):
        shutil.copy2(path,flags/path.name)
    fonts=stage/'fonts';fonts.mkdir(exist_ok=True)
    for path in (ROOT/'remarkable/fonts').iterdir():
        if path.is_file(): shutil.copy2(path,fonts/path.name)
    artwork=stage/'art';artwork.mkdir(exist_ok=True)
    for path in (ROOT/'babblet/static/art').glob('*.svg'): shutil.copy2(path,artwork/path.name)
    files=['ui/Main.qml','ui/TapButton.qml','ui/ArtButton.qml','ui/Fonts.qml','ui/Config.js']+[
        'flags/'+path.name for path in sorted(flags.glob('*.svg'))]+[
        'fonts/'+path.name for path in sorted(fonts.iterdir()) if path.is_file()]+[
        'art/'+path.name for path in sorted(artwork.glob('*.svg'))]
    (stage/'application.qrc').write_text('<RCC><qresource prefix="/">'+''.join(
        '<file>'+escape(path)+'</file>' for path in files)+'</qresource></RCC>',encoding='utf-8')
    rcc=Path(PySide6.__file__).parent/('rcc.exe' if sys.platform=='win32' else 'Qt/libexec/rcc')
    subprocess.run([str(rcc),'--binary','--format-version','2','--no-compress',
        str(stage/'application.qrc'),'-o',str(stage/'resources.rcc')],check=True)
    shutil.copy2(ROOT/'remarkable/manifest.json',stage/'manifest.json')
    # AppLoad wants a PNG launcher icon; draw this code-native mark locally.
    from PySide6.QtGui import QImage,QPainter,QColor,QPen
    image=QImage(128,128,QImage.Format_ARGB32);image.fill(QColor('white'))
    painter=QPainter(image);painter.setPen(QPen(QColor('black'),7))
    painter.drawRoundedRect(10,10,108,108,12,12)
    for y,length in [(36,74),(58,50),(80,74)]: painter.drawLine(28,y,28+length,y)
    painter.end();image.save(str(stage/'icon.png'))
    notices=ROOT/'babblet/static/flags/LICENSE.txt'
    if notices.exists(): shutil.copy2(notices,stage/'FLAGS-LICENSE')
    (stage/'PACKAGE.txt').write_text('Babblet frontend-only QML AppLoad package\n'
        +'Paired credentials included: '+str(paired)+'\n'
        +'No model inference runs on the tablet. Use the computer SSH tunnel helper.\n',encoding='utf-8')
    archive=stage.parent/('babblet-appload-paired.zip' if paired else 'babblet-appload.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
        for name in ['manifest.json','resources.rcc','icon.png','PACKAGE.txt','FLAGS-LICENSE']:
            path=stage/name
            if path.exists(): bundle.write(path,'babblet/'+name)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n',encoding='ascii')
    print(f'Built {archive.name} ({archive.stat().st_size} bytes), paired={paired}')
    return stage


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default=str(ROOT/'artifacts/remarkable'))
    parser.add_argument('--paired',action='store_true',help='Include private tablet token; do not share this bundle')
    args=parser.parse_args()
    build(args.output,args.paired)
