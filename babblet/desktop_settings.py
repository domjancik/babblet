"""Small preferences dialog for the local desktop launcher."""
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,
    QComboBox,QCheckBox,QSpinBox,QPushButton,QTabWidget,QWidget)

from babblet.desktop import ROOT,load_preferences,validate_preferences


class SettingsDialog(QDialog):
    def __init__(self,parent=None,root=ROOT):
        super().__init__(parent)
        self.root=root
        self.original=load_preferences(root)
        self.preferences=None
        self.setWindowTitle('Babblet settings');self.resize(630,570)
        layout=QVBoxLayout(self);layout.setContentsMargins(25,22,25,22);layout.setSpacing(16)
        heading=QLabel('Make yourself heard');heading.setStyleSheet('font-family:"Noto Serif";font-style:italic;font-size:27px');layout.addWidget(heading)
        tabs=QTabWidget();layout.addWidget(tabs)
        basic=QWidget();form=QFormLayout(basic);form.setSpacing(16)
        advanced=QWidget();advanced_form=QFormLayout(advanced);advanced_form.setSpacing(16)
        tabs.addTab(basic,'Sound and models');tabs.addTab(advanced,'More preferences')
        self.microphone=QComboBox();self.microphone.setObjectName('microphonePreference')
        self.microphone.setMinimumContentsLength(25);self.microphone.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        microphone_row=QHBoxLayout();microphone_row.addWidget(self.microphone,1)
        refresh=QPushButton('Refresh');refresh.clicked.connect(self.refresh_devices);microphone_row.addWidget(refresh)
        form.addRow('Microphone',microphone_row)
        self.speech=QComboBox();self.speech.setObjectName('speechModelPreference')
        for directory in sorted((root/'models').iterdir()):
            if directory.name!='whisper-hebrew' and (directory/'model.bin').is_file():
                label='Whisper large-v3-turbo' if directory.name=='whisper-turbo' else directory.name.replace('-',' ')
                self.speech.addItem(label,directory.relative_to(root).as_posix())
        self.select(self.speech,self.original['speech_model']);form.addRow('Speech model',self.speech)
        self.translation=QComboBox();self.translation.setObjectName('translationModelPreference')
        for label,code,filename in [('Hy-MT2 Q8 · higher quality','q8','Q8_0'),('Hy-MT2 Q4 · less memory','q4','Q4_K_M')]:
            if (root/f'models/hymt2/Hy-MT2-1.8B-{filename}.gguf').is_file(): self.translation.addItem(label,code)
        self.select(self.translation,self.original['translation_model']);form.addRow('Translation model',self.translation)
        self.hebrew=QCheckBox('Check Hebrew with the second recognizer');self.hebrew.setChecked(self.original['hebrew_enabled'])
        installed_hebrew=(root/'models/whisper-hebrew/model.bin').exists()
        self.hebrew.setEnabled(installed_hebrew)
        if not installed_hebrew: self.hebrew.setChecked(False)
        form.addRow(self.hebrew)
        self.debug=QCheckBox('Save the latest 20 audio snippets for debugging');self.debug.setChecked(self.original['debug_audio']);form.addRow(self.debug)
        hint=QLabel('Languages and reader layouts are chosen in the translation view.');hint.setWordWrap(True);hint.setStyleSheet('color:#7b8372;font-size:12px');form.addRow(hint)
        self.devices={}
        for key,label in [('speech_device','Speech processing'),('translation_device','Translation processing'),('hebrew_device','Hebrew processing')]:
            combo=QComboBox();combo.addItem('GPU · faster','cuda');combo.addItem('CPU · saves GPU memory','cpu')
            self.select(combo,self.original[key]);self.devices[key]=combo;advanced_form.addRow(label,combo)
        self.hebrew_timeout=QSpinBox();self.hebrew_timeout.setRange(1,120);self.hebrew_timeout.setSuffix(' seconds');self.hebrew_timeout.setValue(int(self.original['hebrew_timeout']))
        advanced_form.addRow('Hebrew time limit',self.hebrew_timeout)
        self.queue_age=QSpinBox();self.queue_age.setRange(1,120);self.queue_age.setSuffix(' seconds');self.queue_age.setValue(int(self.original['max_job_age']))
        advanced_form.addRow('Maximum translation queue age',self.queue_age)
        self.tablet=QCheckBox('Connect reMarkable over USB at startup');self.tablet.setChecked(self.original['connect_tablet']);advanced_form.addRow(self.tablet)
        self.browser=QCheckBox('Open translations automatically');self.browser.setChecked(self.original['open_browser']);advanced_form.addRow(self.browser)
        self.error=QLabel();self.error.setWordWrap(True);self.error.setStyleSheet('color:#a24435');layout.addWidget(self.error)
        note=QLabel('Changing models, sound or recording briefly restarts speech and clears the current conversation.');note.setWordWrap(True);note.setStyleSheet('color:#7b8372;font-size:12px');layout.addWidget(note)
        buttons=QHBoxLayout();buttons.addStretch()
        cancel=QPushButton('Cancel');cancel.clicked.connect(self.reject);buttons.addWidget(cancel)
        apply=QPushButton('Save and apply');apply.setObjectName('applyPreferences');apply.clicked.connect(self.apply);buttons.addWidget(apply);layout.addLayout(buttons)
        self.refresh_devices()

    @staticmethod
    def select(combo,value):
        for index in range(combo.count()):
            candidate=combo.itemData(index)
            same=(tuple(candidate)==tuple(value) if isinstance(candidate,(tuple,list)) and isinstance(value,(tuple,list)) else candidate==value)
            if same:
                combo.setCurrentIndex(index);return

    def refresh_devices(self):
        import sounddevice
        previous=self.microphone.currentData() if self.microphone.count() else (self.original['microphone_name'],self.original['microphone_hostapi'])
        self.microphone.clear();self.microphone.addItem('System default microphone',(None,None))
        try:
            devices=sounddevice.query_devices();apis=sounddevice.query_hostapis()
            for device in devices:
                if device['max_input_channels']>0:
                    api=apis[device['hostapi']]['name'].replace('Windows ','')
                    self.microphone.addItem(f'{device["name"]} · {api}',(device['name'],device['hostapi']))
            self.select(self.microphone,previous)
            if previous and previous[0] and tuple(self.microphone.currentData())!=tuple(previous):
                self.microphone.addItem(previous[0]+' · disconnected',previous)
                self.microphone.setCurrentIndex(self.microphone.count()-1)
            self.error.clear()
        except Exception:
            self.error.setText('Could not list microphones. Reconnect your device and press Refresh.')

    def values(self):
        name,api=self.microphone.currentData()
        return {**self.original,'microphone_name':name,'microphone_hostapi':api,
            'speech_model':self.speech.currentData(),'translation_model':self.translation.currentData(),
            'hebrew_enabled':self.hebrew.isChecked(),'debug_audio':self.debug.isChecked(),
            'hebrew_timeout':self.hebrew_timeout.value(),'max_job_age':self.queue_age.value(),
            'connect_tablet':self.tablet.isChecked(),'open_browser':self.browser.isChecked(),
            **{key:combo.currentData() for key,combo in self.devices.items()}}

    def apply(self):
        try:
            values=self.values();validate_preferences(self.root,values)
            self.preferences=values;self.accept()
        except (ValueError,TypeError) as error:
            self.error.setText(str(error))
