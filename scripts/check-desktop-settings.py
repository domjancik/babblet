"""Exercise actual Qt preference widgets without changing the live services."""
import os
import sys
from pathlib import Path

os.environ['QT_QPA_PLATFORM']='offscreen'
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication,QTabWidget
from PySide6.QtGui import QFontDatabase,QFont
from babblet.desktop import load_preferences
from babblet.desktop_settings import SettingsDialog

application=QApplication([])
for filename in ['NotoSans.ttf','NotoSerif.ttf']:
    assert QFontDatabase.addApplicationFont(str(ROOT/'remarkable/fonts'/filename))>=0
application.setFont(QFont('Noto Sans',11))
dialog=SettingsDialog()
dialog.setStyleSheet('QWidget{background:#f8f7f1;color:#30372a;font-family:"Noto Sans";font-size:14px} QPushButton{background:#e8eddf;border:0;border-radius:10px;padding:10px} QComboBox{padding:6px;min-height:24px}')
original=load_preferences()
assert dialog.values()['microphone_name']==original['microphone_name']
assert 'disconnected' not in dialog.microphone.currentText()
assert dialog.speech.count()>=1 and dialog.translation.count()==2
dialog.refresh_devices()
assert dialog.values()['microphone_name']==original['microphone_name'],'refresh must retain microphone selection'
dialog.show();application.processEvents()
assert dialog.grab().save(str(ROOT/'artifacts/desktop-settings-preview.png'))
dialog.findChild(QTabWidget).setCurrentIndex(1);application.processEvents()
assert dialog.grab().save(str(ROOT/'artifacts/desktop-settings-advanced-preview.png'))
dialog.select(dialog.translation,'q4');dialog.debug.setChecked(False)
dialog.devices['speech_device'].setCurrentIndex(1);dialog.hebrew.setChecked(False)
dialog.queue_age.setValue(30);dialog.apply()
assert dialog.preferences['translation_model']=='q4'
assert dialog.preferences['speech_device']=='cpu' and not dialog.preferences['debug_audio']
assert not dialog.preferences['hebrew_enabled'] and dialog.preferences['max_job_age']==30
assert load_preferences()==original,'UI check must not change live preferences'
print('Qt preference edits, microphone refresh, installed model choices and typed values passed; live settings unchanged.')
