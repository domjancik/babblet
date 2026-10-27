"""Real QML XMLHttpRequest -> authenticated FastAPI bridge integration check."""
import json
import os
import sys
import threading
import time
from pathlib import Path

os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QSG_RHI_BACKEND']='software'
from PySide6.QtCore import QEventLoop,QResource,QTimer,QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
import uvicorn

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from babblet.languages import CATALOG
from babblet.tablet import create_bridge


class Source:
    def __init__(self):
        self.calls=[]
        self.data={'session':'network-fixture','sequence':1,'slot_count':6,
            'selected_languages':['en','he'],'expected_languages':['he'],
            'languages':list(CATALOG.values()),'speech_languages':list(CATALOG.values()),
            'slots':[{'utterance_id':'test','display_index':1,'revision':1,'source_text':'שלום',
                'source_language':'he','phase':'final','translations':{
                    'en':{'status':'complete','text':'Hello'},'he':{'status':'complete','text':'שלום'}}}]+[None]*5}
    async def snapshot(self): return self.data
    async def select(self,mode,languages):
        self.calls.append((mode,languages))
        self.data['selected_languages' if mode=='display' else 'expected_languages']=languages
        return {'selected':languages}
    async def set_sync(self,enabled):
        self.calls.append(('sync',enabled))
        self.data['sync_with_display']=enabled
        if enabled: self.data['expected_languages']=self.data['selected_languages']
        return {'sync_with_display':enabled}


def main():
    source=Source();token='synthetic-test-token-32-characters-long'
    server=uvicorn.Server(uvicorn.Config(create_bridge(token,source),host='127.0.0.1',port=8093,
        log_level='error',access_log=False))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    deadline=time.monotonic()+5
    while not server.started and time.monotonic()<deadline: time.sleep(.02)
    assert server.started
    app=QGuiApplication(sys.argv)
    assert QResource.registerResource(str(ROOT/'artifacts/remarkable/babblet/resources.rcc'))
    view=QQuickView();view.setSource(QUrl('qrc:/ui/Main.qml'));root=view.rootObject()
    assert root is not None,[e.toString() for e in view.errors()]
    engine=view.engine();engine.globalObject().setProperty('testRoot',engine.newQObject(root))
    def evaluate(code):
        value=engine.evaluate(code)
        assert not value.isError(),value.toString()
    def wait_for(predicate):
        until=time.monotonic()+6
        while not predicate() and time.monotonic()<until:
            loop=QEventLoop();QTimer.singleShot(30,loop.quit);loop.exec()
        assert predicate(),'QML network condition did not complete'
    try:
        evaluate('testRoot.running=false; testRoot.serverUrl="http://127.0.0.1:8093"; testRoot.token='+json.dumps(token)+'; testRoot.running=true; testRoot.poll();')
        wait_for(lambda:root.property('successfulPolls')>=1)
        assert root.property('online')
        wait_for(lambda:root.property('changedCells')>0)
        updates=root.property('changedCells');assert updates==3,updates
        previous=root.property('successfulPolls');evaluate('testRoot.poll();')
        wait_for(lambda:root.property('successfulPolls')>previous)
        assert root.property('changedCells')==updates
        source.data['sequence']=2;source.data['slots'][0]['translations']['en']['text']='Updated'
        previous=root.property('successfulPolls');evaluate('testRoot.poll();')
        wait_for(lambda:root.property('successfulPolls')>previous)
        assert root.property('changedCells')==updates+1
        wait_for(lambda:not root.property('busy'))
        evaluate('testRoot.speechMode=false; testRoot.toggleLanguage("ru");')
        wait_for(lambda:bool(source.calls))
        assert source.calls==[('display',['en','he','ru'])]
        wait_for(lambda:not root.property('busy'))
        evaluate('testRoot.setSync(false);')
        wait_for(lambda:('sync',False) in source.calls)
        wait_for(lambda:not root.property('syncWithDisplay'))
        wait_for(lambda:not root.property('busy'))
        evaluate('testRoot.setSync(true);')
        wait_for(lambda:('sync',True) in source.calls)
        wait_for(lambda:root.property('syncWithDisplay'))
        print('Real QML XHR: authenticated GET, language selection and persisted sync toggle passed; unchanged poll=0 cell updates; changed translation=1 cell.')
    finally:
        root.unloading();server.should_exit=True;thread.join(timeout=3);view.close()


if __name__=='__main__': main()
