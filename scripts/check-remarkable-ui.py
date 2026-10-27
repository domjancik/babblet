"""Offscreen Qt Quick integration check using synthetic, multilingual rows."""
import argparse
import json
import os
import sys
from pathlib import Path

os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QSG_RHI_BACKEND']='software'
from PySide6.QtCore import QCoreApplication,QEventLoop,QResource,QTimer,QUrl,QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from babblet.languages import CATALOG


def main(bundle):
    for qml in (ROOT/'remarkable/ui').glob('*.qml'):
        assert 'Accessible.' not in qml.read_text(encoding='utf-8'),'Tablet Qt lacks accessibility attached objects'
    application=QGuiApplication(sys.argv)
    assert QResource.registerResource(str(Path(bundle)/'resources.rcc'))
    view=QQuickView()
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    view.resize(1404,1872)
    view.setSource(QUrl('qrc:/ui/Main.qml'))
    assert view.status()!=QQuickView.Error,[error.toString() for error in view.errors()]
    root=view.rootObject()
    assert root is not None
    engine=view.engine()
    engine.globalObject().setProperty('testRoot',engine.newQObject(root))
    engine.evaluate('testRoot.running=false; testRoot.clean=true;')
    samples=[('שלום לכולם. עכשיו זה עובד.','Hello everyone. Now it works.','Ahoj všichni. Teď to funguje.'),
             ('זה לא יותר טוב.','It is not better.','Není to lepší.'),
             ('הטקסט נשאר באותה שורה.','Text stays in the same row.','Text zůstává na stejném řádku.'),
             ('רק השורות שהשתנו מתעדכנות.','Only changed rows update.','Aktualizují se pouze změněné řádky.'),
             ('אין אנימציה של תנועה.','There is no movement animation.','Bez pohybové animace.'),
             ('החישוב מתבצע במחשב.','Computation stays on the computer.','Výpočty zůstávají v počítači.')]
    data={'session':'synthetic','sequence':1,'slot_count':6,'selected_languages':['en','cs','he'],
          'expected_languages':['he'],'languages':list(CATALOG.values()),
          'speech_languages':list(CATALOG.values()),'slots':[]}
    for index,(he,en,cs) in enumerate(samples):
        data['slots'].append({'utterance_id':str(index),'display_index':index+1,'revision':1,
            'source_text':he,'source_language':'he','phase':'final',
            'translations':{code:{'status':'complete','text':text} for code,text in [('en',en),('cs',cs),('he',he)]}})
    engine.evaluate('testRoot.applySnapshot('+json.dumps(data,ensure_ascii=False)+');')
    def pump():
        loop=QEventLoop();QTimer.singleShot(100,loop.quit);loop.exec()
    view.show();pump()
    assert root.property('latestRow')==5
    assert root.property('nextReplaceRow')==0
    picker=root.findChild(QObject,'languagePickerButton')
    assert picker is not None and picker.property('visible') and picker.property('height')>=90
    engine.evaluate('testRoot.landscape=true;');pump()
    assert root.property('pageWidth')==1872 and root.property('pageHeight')==1404
    assert picker.property('visible'),'language picker must remain available in landscape'
    engine.evaluate('testRoot.settings=true;');pump()
    assert picker.property('visible'),'language picker must remain available in settings'
    grid=root.findChild(QObject,'languageGrid')
    viewport=root.findChild(QObject,'languageGridViewport')
    assert grid is not None and viewport is not None
    assert grid.property('height')<=viewport.property('height'),'all languages must fit in landscape'
    assert grid.property('width')<=viewport.property('width')+1
    assert grid.property('tileHeight')>=150,'flag targets must remain comfortable to tap'
    assert engine.evaluate('testRoot.languageOptions.length').toInt()==38
    engine.evaluate('testRoot.settings=false;');pump()
    engine.evaluate('testRoot.landscape=false;');pump()
    assert grid.property('height')<=viewport.property('height'),'all languages must fit in portrait'
    engine.evaluate('testRoot.settings=true;');pump()
    assert view.grabWindow().save(str(ROOT/'artifacts/remarkable/languages-portrait-preview.png'))
    engine.evaluate('testRoot.settings=false;');pump()
    assert root.property('changedCells')==24
    initial=root.property('changedCells')
    engine.evaluate('testRoot.applySnapshot('+json.dumps(data,ensure_ascii=False)+');');pump()
    assert root.property('changedCells')==initial,'unchanged polls must not recreate or redraw rows'
    data['sequence']=2;data['slots'][0]['translations']['en']['text']='One changed cell.'
    engine.evaluate('testRoot.applySnapshot('+json.dumps(data,ensure_ascii=False)+');');pump()
    assert root.property('changedCells')==initial+1,'a single translation changes only one cell'
    data['pending_activity']={'active':True,'label':'Listening…','display_index':7,'utterance_id':None}
    engine.evaluate('testRoot.applySnapshot('+json.dumps(data,ensure_ascii=False)+');');pump()
    assert root.property('changedCells')==initial+5,'pending capture marks the next shared row in every language'
    unchanged=root.property('changedCells')
    engine.evaluate('testRoot.applySnapshot('+json.dumps(data,ensure_ascii=False)+');');pump()
    assert root.property('changedCells')==unchanged,'unchanged activity does not redraw'
    data['pending_activity']['label']='Checking Hebrew…'
    engine.evaluate('testRoot.applySnapshot('+json.dumps(data,ensure_ascii=False)+');');pump()
    assert root.property('changedCells')==unchanged,'stage changes update the single graphic, not every language cell'
    assert root.property('workVisible') and root.property('workLevel')==3
    # Preserve a readable static preview with pending work visible in row one.
    data['sequence']=3;data['slots'][0]['translations']['en']['text']=samples[0][1]
    engine.evaluate('testRoot.online=true; testRoot.connectionMessage="Connected"; testRoot.applySnapshot('+json.dumps(data,ensure_ascii=False)+');');pump()
    screenshot=ROOT/'artifacts/remarkable/preview.png'
    assert view.grabWindow().save(str(screenshot))
    # Render the same wide-page geometry upright for a readable landscape preview.
    view.resize(1872,1404);pump()
    assert view.grabWindow().save(str(ROOT/'artifacts/remarkable/landscape-preview.png'))
    engine.evaluate('testRoot.settings=true;');pump()
    assert view.grabWindow().save(str(ROOT/'artifacts/remarkable/languages-preview.png'))
    engine.evaluate('testRoot.settings=false; testRoot.showSpoken=false;');pump()
    assert engine.evaluate('testRoot.columns.length').toInt()==3,'spoken toggle removes only the original speech column'
    engine.evaluate('testRoot.flip("en");');pump()
    def visual(name, parent=root):
        if parent.objectName()==name: return parent
        for child in parent.childItems():
            found=visual(name,child)
            if found is not None: return found
        return None
    header=visual('columnHeader-en')
    assert header is not None and header.property('rotation')==180
    assert engine.evaluate('testRoot.snapshot.slots[0].utterance_id').toString()=='0','flipping must preserve FIFO row assignment'
    engine.evaluate('testRoot.showSpoken=true;');pump()
    assert engine.evaluate('testRoot.columns.length').toInt()==4
    assert engine.evaluate('testRoot.flipped.en').toBool(),'showing spoken must preserve column orientation'
    engine.evaluate('testRoot.flip("en");');pump()
    assert visual('columnHeader-en').property('rotation')==0
    engine.evaluate('testRoot.readerLayout="opposite";');pump()
    assert engine.evaluate('testRoot.columns.length').toInt()==2
    assert visual('readerPanel-1').property('rotation')==180
    engine.evaluate('testRoot.readerTarget=1; testRoot.settings=true;');pump()
    assert engine.evaluate('testRoot.columns[testRoot.readerTarget].panelAngle').toInt()==180
    engine.evaluate('testRoot.chooseReader("he");');pump()
    assert engine.evaluate('testRoot.columns[1].code').toString()=='he'
    assert visual('readerPanel-1').property('rotation')==180
    engine.evaluate('testRoot.readerLayout="stacked";');pump()
    assert visual('readerPanel-0').property('width')>visual('readerPanel-0').property('height')
    engine.evaluate('testRoot.readerLayout="four";');pump()
    assert engine.evaluate('testRoot.columns.length').toInt()==4
    assert visual('readerPanel-2').property('rotation')==180
    engine.evaluate('testRoot.flipReader(2);');pump()
    assert visual('readerPanel-2').property('rotation')==0
    assert engine.evaluate('testRoot.snapshot.slots[0].utterance_id').toString()=='0'
    assert view.grabWindow().save(str(ROOT/'artifacts/remarkable/readers-preview.png'))
    engine.evaluate('testRoot.readerLayout="opposite";');pump()
    assert view.grabWindow().save(str(ROOT/'artifacts/remarkable/facing-preview.png'))
    assert visual('tabletRow-0-0').property('opacity')==0.45
    data['sequence']=4
    data['pending_activity']={'active':False}
    data['slots'][0]={**data['slots'][0],'utterance_id':'new','display_index':7}
    engine.evaluate('testRoot.applySnapshot('+json.dumps(data,ensure_ascii=False)+');');pump()
    assert root.property('latestRow')==0 and root.property('nextReplaceRow')==1
    assert visual('tabletRow-0-0').property('opacity')==1
    assert visual('tabletRow-1-1').property('opacity')==0.45,'next-to-replace cue rotates with the opposite reader'
    data['sequence']=5
    data['slot_count']=1
    data['slots']=data['slots'][:1]
    engine.evaluate('testRoot.applySnapshot('+json.dumps(data,ensure_ascii=False)+');');pump()
    assert root.property('latestRow')==0 and root.property('nextReplaceRow')==-1
    assert visual('tabletRow-0-0').property('opacity')==1
    root.unloading()
    print('Qt Quick resource loaded; 24 multilingual cells; unchanged poll=0 updates; changed translation=1 cell; pending activity=one global row.')
    print('Saved synthetic preview:',screenshot)
    view.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',default=str(ROOT/'artifacts/remarkable/babblet'))
    main(parser.parse_args().bundle)
