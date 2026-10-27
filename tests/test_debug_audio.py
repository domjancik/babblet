import json
import numpy as np
import soundfile as sf

from babblet.debug_audio import DebugRecorder


def test_debug_recorder_saves_exact_audio_and_diagnostics_and_bounds_history(tmp_path):
    recorder=DebugRecorder(tmp_path,limit=2)
    audio=np.linspace(-.2,.2,16000,dtype=np.float32)
    for index in range(3):
        recorder.save(audio,{'phase':'final','primary':{'text':str(index)}})
    files=sorted(tmp_path.glob('clip-*.wav'))
    assert len(files)==2
    restored,rate=sf.read(files[-1],dtype='float32')
    assert rate==16000
    np.testing.assert_array_equal(restored,audio)
    assert json.loads(files[-1].with_suffix('.json').read_text())['trace']['primary']['text']=='2'
    assert len(list(tmp_path.glob('clip-*.json')))==2


def test_disabled_recording_never_creates_files(tmp_path):
    recorder=DebugRecorder(tmp_path)
    recorder.enabled=False
    assert recorder.save(np.ones(16000,dtype=np.float32),{}) is None
    assert list(tmp_path.iterdir())==[]


def test_recording_wrapper_captures_before_failure_and_leaves_drafts_unrecorded(tmp_path):
    import pytest
    from babblet.debug_audio import RecordingRecognizer
    class Recognizer:
        trace={'phase':'final','reason':'test_failure'}
        def transcribe(self,audio,language,refine):
            if refine:
                assert len(list(tmp_path.glob('*.wav')))==1
                raise RuntimeError('decoder failed')
            return []
    status={'debug_recording':{'saved':0}}
    wrapper=RecordingRecognizer(Recognizer(),DebugRecorder(tmp_path),status)
    wrapper.transcribe(np.zeros(16000),refine=False)
    assert list(tmp_path.iterdir())==[]
    with pytest.raises(RuntimeError): wrapper.transcribe(np.zeros(16000),refine=True)
    report=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert report['trace']['reason']=='test_failure'
    assert status['debug_recording']['saved']==1
