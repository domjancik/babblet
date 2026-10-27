"""Windows desktop entry point for the existing local Babblet services."""
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener

ROOT=Path(__file__).resolve().parents[1]
CREATE_HIDDEN=getattr(subprocess,'CREATE_NO_WINDOW',0)
DEFAULT_PREFERENCES={'microphone_name':None,'microphone_hostapi':None,
    'speech_model':'models/whisper-turbo','speech_device':'cuda',
    'translation_model':'q8','translation_device':'cuda','hebrew_enabled':True,
    'hebrew_device':'cpu','hebrew_timeout':12,'max_job_age':8,
    'debug_audio':False,'connect_tablet':True,'open_browser':True}


def load_preferences(root=ROOT):
    path=Path(root)/'config/desktop.json'
    stored=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    return {**DEFAULT_PREFERENCES,**stored}


def validate_preferences(root,settings):
    for key in ('speech_device','translation_device','hebrew_device'):
        if settings[key] not in ('cuda','cpu'): raise ValueError('Choose GPU or CPU for each model.')
    if settings['translation_model'] not in ('q4','q8'): raise ValueError('Choose an installed translation model.')
    quant='Q8_0' if settings['translation_model']=='q8' else 'Q4_K_M'
    if not (Path(root)/f'models/hymt2/Hy-MT2-1.8B-{quant}.gguf').is_file():
        raise ValueError('The selected translation model is not installed.')
    for key in ('debug_audio','hebrew_enabled','connect_tablet','open_browser'):
        if type(settings[key]) is not bool: raise ValueError('Checkbox preferences must be true or false.')
    for key in ('hebrew_timeout','max_job_age'):
        value=settings[key]
        if type(value) not in (int,float) or not 1<=value<=120: raise ValueError('Time limits must be between 1 and 120 seconds.')
    if not isinstance(settings['speech_model'],str): raise ValueError('Choose an installed speech model.')
    model=(Path(root)/settings['speech_model']).resolve()
    if not model.is_relative_to((Path(root)/'models').resolve()) or not (model/'model.bin').is_file():
        raise ValueError('Choose an installed speech model from the Babblet models folder.')
    if settings['hebrew_enabled'] and not (Path(root)/'models/whisper-hebrew/model.bin').is_file():
        raise ValueError('The Hebrew second-recognizer model is not installed.')
    if settings['microphone_name'] is not None and not isinstance(settings['microphone_name'],str):
        raise ValueError('Choose a microphone from the device list.')


def save_preferences(root,settings):
    validate_preferences(root,settings)
    directory=Path(root)/'config';directory.mkdir(exist_ok=True)
    temporary=directory/'desktop.tmp'
    temporary.write_text(json.dumps(settings,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(directory/'desktop.json')


def changed_services(before,after):
    translation=any(before.get(key)!=after.get(key) for key in ('translation_model','translation_device'))
    speech=any(before.get(key)!=after.get(key) for key in ('microphone_name','microphone_hostapi',
        'speech_model','speech_device','hebrew_enabled','hebrew_device','hebrew_timeout','max_job_age','debug_audio'))
    return (['display'] if speech or translation else [])+(['translation'] if translation else [])


def service_commands(root,settings,devices):
    root=Path(root)
    validate_preferences(root,settings)
    python=root/'.venv/Scripts/python.exe'
    quant='Q8_0' if settings['translation_model']=='q8' else 'Q4_K_M'
    translation=[root/'runtime/llama/llama-server.exe','-m',root/f'models/hymt2/Hy-MT2-1.8B-{quant}.gguf',
        '--host','127.0.0.1','--port','18081','-ngl','99' if settings['translation_device']=='cuda' else '0',
        '-c','2048','--parallel','1','--api-key-file','runtime/translation.key','--no-webui']
    speech=[python,'-m','babblet.cli','--serve','--mic','--model',root/settings['speech_model'],
        '--device',settings['speech_device'],'--hebrew-device',settings['hebrew_device'],
        '--hebrew-timeout',str(settings['hebrew_timeout']),'--max-job-age',str(settings['max_job_age'])]
    microphone=resolve_microphone(devices,settings)
    if microphone is not None: speech+=['--audio-device',str(microphone)]
    if not settings['hebrew_enabled']: speech+=['--no-hebrew-second']
    if settings['debug_audio']: speech+=['--debug-audio','artifacts/debug-audio']
    return {'translation':translation,'display':speech}


def resolve_microphone(devices,settings):
    name=settings.get('microphone_name')
    matches=[index for index,device in enumerate(devices)
             if device['max_input_channels']>0 and device['name']==name]
    for index in matches:
        if devices[index]['hostapi']==settings.get('microphone_hostapi'):
            return index
    if matches:
        return matches[0]
    if name:
        raise RuntimeError('Your saved microphone is disconnected. Reconnect it and try again.')
    return None


class DesktopServices:
    def __init__(self,root=ROOT,notify=lambda message:None):
        self.root=Path(root)
        self.notify=notify
        self.created=[]

    def get_json(self,url,headers=None):
        try:
            opener=build_opener(ProxyHandler({}))
            with opener.open(Request(url,headers=headers or {}),timeout=1) as response:
                return json.load(response)
        except (OSError,ValueError,HTTPError,URLError):
            return None

    def listening(self,url):
        parsed=urlparse(url)
        try:
            with socket.create_connection((parsed.hostname,parsed.port),timeout=.3):
                return True
        except OSError:
            return False

    def launch(self,name,command):
        directory=self.root/'artifacts'
        directory.mkdir(exist_ok=True)
        environment={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
        with (directory/f'{name}-stdout.log').open('ab') as out, (directory/f'{name}-stderr.log').open('ab') as err:
            process=subprocess.Popen([str(part) for part in command],cwd=self.root,env=environment,
                stdin=subprocess.DEVNULL,stdout=out,stderr=err,creationflags=CREATE_HIDDEN)
        (directory/f'{name}.pid').write_text(str(process.pid),encoding='ascii')
        self.created.append(name)
        return process

    def ensure(self,name,command,url,valid,headers=None,timeout=180):
        if valid(self.get_json(url,headers) or {}):
            return
        if self.listening(url):
            raise RuntimeError(f'The {name} port is already in use. An existing service is still loading or needs attention.')
        process=self.launch(name,command)
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if valid(self.get_json(url,headers) or {}):
                return
            if process.poll() is not None:
                raise RuntimeError(f'{name.capitalize()} could not start. See its log in the Babblet folder.')
            time.sleep(.5)
        # Only terminate the process tree this invocation created and still owns.
        if process.poll() is None:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],creationflags=CREATE_HIDDEN,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        raise RuntimeError(f'{name.capitalize()} took too long to start. Try again.')

    def connect_tablet(self):
        ssh=['ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=3','-o','StrictHostKeyChecking=yes']
        tablet='root@10.11.99.1'
        try:
            # An existing reverse listener means the USB tunnel is already up.
            check=subprocess.run([*ssh,tablet,"grep -q '0100007F:1F9C 00000000:0000 0A' /proc/net/tcp"],
                capture_output=True,timeout=6,creationflags=CREATE_HIDDEN)
            if check.returncode==0:
                return True
            if check.returncode==255:
                return False
            tunnel=self.launch('tablet-network-usb',[*ssh,'-N','-o','ExitOnForwardFailure=yes',
                '-o','ServerAliveInterval=15','-o','ServerAliveCountMax=3',
                '-R','127.0.0.1:8092:127.0.0.1:8092',tablet])
            time.sleep(1)
            return tunnel.poll() is None
        except (OSError,subprocess.TimeoutExpired):
            return False

    def process_info(self,pid):
        query=(f"Get-CimInstance Win32_Process -Filter 'ProcessId = {int(pid)}' | "
               'Select-Object ExecutablePath,CommandLine,ParentProcessId | ConvertTo-Json -Compress')
        result=subprocess.run(['powershell','-NoProfile','-Command',query],capture_output=True,
            text=True,timeout=10,creationflags=CREATE_HIDDEN,check=True)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def port_owner(self,url):
        port=urlparse(url).port
        query=(f'Get-NetTCPConnection -LocalPort {int(port)} -State Listen -ErrorAction SilentlyContinue | '
               'Select-Object -ExpandProperty OwningProcess -Unique')
        result=subprocess.run(['powershell','-NoProfile','-Command',query],capture_output=True,
            text=True,timeout=10,creationflags=CREATE_HIDDEN,check=False)
        owners=result.stdout.strip().splitlines()
        return int(owners[0]) if len(owners)==1 and owners[0].strip().isdigit() else None

    def service_identity(self,name):
        if name not in ('display','translation'): raise ValueError('Unknown service')
        url='http://127.0.0.1:'+('8090' if name=='display' else '18081')
        path=self.root/f'artifacts/{name}.pid'
        pid=int(path.read_text().strip()) if path.exists() else None
        info=self.process_info(pid) if pid is not None else None
        if info is None:
            if not self.listening(url): return None
            pid=self.port_owner(url)
            info=self.process_info(pid) if pid is not None else None
            if info is None: raise RuntimeError(f'Cannot safely identify the running {name} process.')
            if name=='display':
                # A venv shim owns the base-Python process actually listening.
                for _ in range(3):
                    if Path(info.get('ExecutablePath') or '').resolve()==(self.root/'.venv/Scripts/python.exe').resolve(): break
                    if '-m babblet.cli' not in (info.get('CommandLine') or ''): break
                    parent=info.get('ParentProcessId')
                    parent_info=self.process_info(parent) if parent else None
                    if not parent_info: break
                    pid,info=parent,parent_info
        expected=self.root/('.venv/Scripts/python.exe' if name=='display' else 'runtime/llama/llama-server.exe')
        actual=Path(info.get('ExecutablePath') or '').resolve()
        if actual!=expected.resolve() or (name=='display' and '-m babblet.cli' not in (info.get('CommandLine') or '')):
            raise RuntimeError(f'Cannot safely restart {name}: its recorded process belongs to another program.')
        return pid

    def stop_service(self,name):
        pid=self.service_identity(name)
        if pid is None: return
        url='http://127.0.0.1:'+('8090' if name=='display' else '18081')
        subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],capture_output=True,
            creationflags=CREATE_HIDDEN,check=True)
        deadline=time.monotonic()+8
        while self.listening(url):
            if time.monotonic()>deadline: raise RuntimeError(f'{name.capitalize()} has not stopped yet. Try again.')
            time.sleep(.2)

    def apply(self,settings):
        validate_preferences(self.root,settings)
        import sounddevice
        resolve_microphone(sounddevice.query_devices(),settings)
        previous=load_preferences(self.root)
        changes=changed_services(previous,settings)
        for name in changes:
            self.service_identity(name)
        for name in changes:
            self.notify('Restarting speech…' if name=='display' else 'Changing translation model…')
            self.stop_service(name)
        save_preferences(self.root,settings)
        return self.start()

    def start(self):
        from babblet.tablet import read_token
        import sounddevice
        settings=load_preferences(self.root)
        commands=service_commands(self.root,settings,sounddevice.query_devices())
        python=self.root/'.venv/Scripts/python.exe'
        key=read_token(self.root/'runtime/translation.key')
        self.notify('Waking the translation engine…')
        self.ensure('translation',commands['translation'],
            'http://127.0.0.1:18081/health',lambda data:data.get('status')=='ok',
            {'Authorization':'Bearer '+key})
        self.notify('Preparing the microphone and speech models…')
        self.ensure('display',commands['display'],'http://127.0.0.1:8090/healthz',
            lambda data:data.get('input',{}).get('state')=='listening')
        if not settings['connect_tablet']:
            return 'Listening on this computer'
        self.notify('Connecting the tablet over USB…')
        token=read_token(self.root/'runtime/tablet.key')
        self.ensure('tablet-gateway',[python,'-m','babblet.tablet'],'http://127.0.0.1:8092/v1/display',
            lambda data:bool(data.get('session')),{'Authorization':'Bearer '+token},timeout=15)
        connected=self.connect_tablet()
        return 'Listening · tablet connected by USB' if connected else 'Listening on this computer · connect tablet by USB, then press Start / reconnect'


def main():
    from PySide6.QtCore import QThread,Signal,QTimer,QLockFile
    from PySide6.QtGui import QIcon,QFont,QFontDatabase
    from PySide6.QtNetwork import QLocalServer,QLocalSocket
    from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout,QLabel,QPushButton,QSystemTrayIcon,QMenu

    check_ui='--check-ui' in sys.argv
    application=QApplication(sys.argv)
    application.setApplicationName('Babblet')
    identity='babblet-'+hashlib.sha256(str(ROOT).lower().encode()).hexdigest()[:16]
    # Windows permits multiple named-pipe listeners. Use a process-owned lock
    # for exclusion and the pipe only to bring the existing window forward.
    lock=QLockFile(str(ROOT/'runtime/desktop-launch.lock'))
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        existing=QLocalSocket();existing.connectToServer(identity)
        existing.waitForConnected(1000)
        return 0
    server=QLocalServer()
    if not server.listen(identity):
        raise RuntimeError('Could not open the Babblet launcher connection')
    for filename in ['NotoSans.ttf','NotoSerif.ttf']:
        assert QFontDatabase.addApplicationFont(str(ROOT/'remarkable/fonts'/filename))>=0
    application.setFont(QFont('Noto Sans',11))

    class Worker(QThread):
        progress=Signal(str)
        ready=Signal(str)
        failed=Signal(str)
        settings=None
        def run(self):
            try:
                services=DesktopServices(notify=self.progress.emit)
                self.ready.emit(services.apply(self.settings) if self.settings is not None else services.start())
            except Exception as error:
                self.failed.emit(str(error))

    icon=QIcon(str(ROOT/'runtime/babblet.ico'))
    application.setWindowIcon(icon)
    window=QWidget();window.setWindowTitle('Babblet');window.resize(490,300)
    window.setStyleSheet('QWidget{background:#f8f7f1;color:#30372a;font-family:"Noto Sans";font-size:15px} QPushButton{background:#e8eddf;border:0;border-radius:14px;padding:12px} QPushButton:disabled{color:#9aa18f}')
    layout=QVBoxLayout(window);layout.setContentsMargins(28,24,28,24);layout.setSpacing(15)
    title=QLabel('babblet');title.setStyleSheet('font-family:"Noto Serif";font-size:38px;font-style:italic');layout.addWidget(title)
    status=QLabel('Starting…');status.setWordWrap(True);layout.addWidget(status)
    note=QLabel('Local speech and translation · USB tablet connection');note.setWordWrap(True);note.setStyleSheet('color:#7b8372;font-size:12px');layout.addWidget(note)
    background_note=QLabel('Close this window to leave Babblet listening in the tray.');background_note.setWordWrap(True);background_note.setStyleSheet('color:#7b8372;font-size:12px');layout.addWidget(background_note)
    open_button=QPushButton('Open translations');open_button.setEnabled(False);layout.addWidget(open_button)
    retry=QPushButton('Start / reconnect');layout.addWidget(retry)
    settings_button=QPushButton('Settings…');layout.addWidget(settings_button)
    open_button.clicked.connect(lambda:webbrowser.open('http://127.0.0.1:8090/'))
    def show_window():
        window.show();window.raise_();window.activateWindow()
        connection=server.nextPendingConnection()
        if connection:
            connection.disconnectFromServer()
    server.newConnection.connect(show_window)
    worker=Worker()
    worker.progress.connect(status.setText)
    def ready(message):
        status.setText(message);open_button.setEnabled(True)
        if check_ui:
            def capture():
                assert window.grab().save(str(ROOT/'artifacts/desktop-preview.png'))
                application.exit(0)
            QTimer.singleShot(200,capture)
        elif load_preferences()['open_browser']:
            webbrowser.open('http://127.0.0.1:8090/')
    worker.ready.connect(ready)
    worker.failed.connect(status.setText)
    if check_ui:
        worker.failed.connect(lambda message:QTimer.singleShot(200,lambda:application.exit(1)))
    def finished():
        retry.setEnabled(True);settings_button.setEnabled(True)
    worker.finished.connect(finished)
    def start():
        if worker.isRunning(): return
        worker.settings=None;retry.setEnabled(False);settings_button.setEnabled(False);worker.start()
    retry.clicked.connect(start)
    def preferences():
        from babblet.desktop_settings import SettingsDialog
        dialog=SettingsDialog(window)
        if dialog.exec() and dialog.preferences is not None:
            worker.settings=dialog.preferences
            retry.setEnabled(False);settings_button.setEnabled(False);open_button.setEnabled(False)
            worker.start()
    settings_button.clicked.connect(preferences)
    # Closing the small launcher leaves capture running; the tray offers a way
    # back to its status window without starting more model processes.
    tray=QSystemTrayIcon(icon,window)
    menu=QMenu();menu.addAction('Open translations',lambda:webbrowser.open('http://127.0.0.1:8090/'))
    menu.addAction('Show Babblet',show_window)
    menu.addAction('Quit launcher',lambda:application.quit() if not worker.isRunning() else show_window())
    tray.setContextMenu(menu);tray.setToolTip('Babblet · live translation')
    tray.activated.connect(lambda reason:show_window() if reason==QSystemTrayIcon.Trigger else None)
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray.show();application.setQuitOnLastWindowClosed(False)
    else:
        window.closeEvent=lambda event:event.ignore() if worker.isRunning() else event.accept()
    window.show();QTimer.singleShot(0,start)
    return application.exec()


if __name__=='__main__':
    raise SystemExit(main())
