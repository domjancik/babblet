import importlib.util
import math

import numpy as np


def meter_module():
    assert importlib.util.find_spec('babblet.audio_level'), 'Audio level measurement must exist'
    from babblet.audio_level import AudioLevel, meter_snapshot
    return AudioLevel,meter_snapshot


def test_rms_is_measured_in_dbfs_and_maps_to_display_range():
    AudioLevel,_=meter_module()
    value=AudioLevel().sample(np.full(1600,.1,dtype=np.float32))
    assert math.isclose(value['rms_dbfs'],-20,abs_tol=.1)
    assert .65<value['level']<.68
    assert not value['clipping']


def test_silence_and_invalid_samples_never_create_nan_levels():
    AudioLevel,_=meter_module()
    meter=AudioLevel()
    for frame in [np.zeros(1600),np.array([]),np.array([float('nan'),float('inf')])]:
        value=meter.sample(frame)
        assert value['level']==0
        assert math.isfinite(value['rms_dbfs'])
        assert not value['clipping']


def test_clipping_indicator_holds_briefly_after_a_peak():
    AudioLevel,_=meter_module()
    now=[0.0]
    meter=AudioLevel(clock=lambda:now[0])
    assert meter.sample(np.ones(1600))['clipping']
    now[0]=.2
    assert meter.sample(np.zeros(1600))['clipping']
    now[0]=1
    assert not meter.sample(np.zeros(1600))['clipping']


def test_stale_capture_clears_meter_instead_of_freezing_high():
    AudioLevel,snapshot=meter_module()
    meter=AudioLevel(clock=lambda:10)
    status={'state':'listening','audio_level':meter.sample(np.ones(1600)*.1)}
    assert snapshot(status,now=10.2)['active']
    value=snapshot(status,now=12)
    assert not value['active']
    assert value['level']==0


def test_meter_endpoint_exposes_only_levels_not_audio_or_transcripts():
    AudioLevel,_=meter_module()
    from fastapi.testclient import TestClient
    from babblet.core import Pipeline
    from babblet.web import create_app
    status={'state':'listening','audio_level':AudioLevel().sample(np.full(1600,.1))}
    data=TestClient(create_app(Pipeline(None),status)).get('/api/audio-level').json()
    assert data['active'] and data['label']=='Picking up'
    assert set(data)=={'active','level','rms_dbfs','peak_dbfs','clipping','label'}
