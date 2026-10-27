"""Check bundled font shaping without OS fallback and render a native-label sheet."""
import json
import os
import sys
from pathlib import Path

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtCore import QPointF
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QImage, QPainter, QTextLayout

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from babblet.languages import CATALOG

app = QGuiApplication(sys.argv)
mapping = json.loads((ROOT / 'remarkable/fonts/languages.json').read_text(encoding='utf-8'))
for filename in {item['file'] for item in mapping.values()}:
    assert QFontDatabase.addApplicationFont(str(ROOT / 'remarkable/fonts' / filename)) >= 0, filename

image = QImage(1404, 1872, QImage.Format_RGB32)
image.fill('white')
painter = QPainter(image)
painter.setPen('black')
for index, (code, language) in enumerate(CATALOG.items()):
    family = mapping[code]['family']
    assert family in QFontDatabase.families(), (code, family)
    font = QFont(family)
    font.setPixelSize(34)
    font.setStyleStrategy(QFont.NoFontMerging)
    layout = QTextLayout(language['native'], font)
    layout.beginLayout()
    line = layout.createLine()
    line.setLineWidth(600)
    layout.endLayout()
    runs = layout.glyphRuns()
    assert runs and all(0 not in run.glyphIndexes() for run in runs), code
    x, y = 40 + (index // 19) * 700, 20 + (index % 19) * 96
    painter.setFont(QFont('Noto Sans', 12))
    painter.drawText(x, y + 18, language['name'])
    layout.draw(painter, QPointF(x, y + 25))
painter.end()
output = ROOT / 'artifacts/remarkable/font-preview.png'
output.parent.mkdir(parents=True, exist_ok=True)
assert image.save(str(output))
print(f'Qt shaped all {len(mapping)} native labels with bundled fonts and no OS fallback; preview: {output}')
