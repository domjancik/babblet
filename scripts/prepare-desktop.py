"""Create the local launcher icon and remember the currently chosen microphone."""
import argparse
import json
import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtGui import QGuiApplication,QImage,QPainter,QColor,QFont,QFontDatabase

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--microphone-index',type=int,default=-1)
    args=parser.parse_args()
    application=QGuiApplication([])
    assert QFontDatabase.addApplicationFont(str(ROOT/'remarkable/fonts/NotoSerif.ttf'))>=0
    runtime=ROOT/'runtime';runtime.mkdir(exist_ok=True)
    image=QImage(256,256,QImage.Format_ARGB32);image.fill(QColor('#f8f7f1'))
    painter=QPainter(image);painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QColor('#526047'));font=QFont('Noto Serif',140);font.setItalic(True);painter.setFont(font)
    painter.drawText(60,195,'b');painter.end()
    assert image.save(str(runtime/'babblet.ico')),'ICO writer unavailable'
    directory=ROOT/'config';directory.mkdir(exist_ok=True)
    settings_path=directory/'desktop.json'
    if not settings_path.exists():
        settings={'microphone_name':None,'microphone_hostapi':None,'debug_audio':False}
        if args.microphone_index>=0:
            import sounddevice
            device=sounddevice.query_devices(args.microphone_index)
            if device['max_input_channels']<=0: raise RuntimeError('Choose an input microphone index')
            settings.update(microphone_name=device['name'],microphone_hostapi=device['hostapi'])
        settings_path.write_text(json.dumps(settings,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Prepared Babblet launcher icon and microphone settings.')


if __name__=='__main__':
    main()
