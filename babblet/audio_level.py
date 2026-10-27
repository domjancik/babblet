"""Transient microphone pickup measurements; no audio is retained."""
import math
import time

import numpy as np


class AudioLevel:
    def __init__(self,clock=time.monotonic):
        self.clock=clock
        self.clip_until=-1

    def sample(self,audio):
        frame=np.asarray(audio,dtype=np.float32)
        now=self.clock()
        if not frame.size or not np.isfinite(frame).all():
            rms=peak=0.0
        else:
            rms=float(np.sqrt(np.mean(frame*frame)))
            peak=float(np.max(np.abs(frame)))
        db=max(-80.0,min(0.0,20*math.log10(max(rms,1e-4))))
        peak_db=max(-80.0,min(0.0,20*math.log10(max(peak,1e-4))))
        if peak>=.98:
            self.clip_until=now+.8
        return {'rms_dbfs':round(db,1),'peak_dbfs':round(peak_db,1),
                'level':round(max(0.0,min(1.0,(db+60)/60)),3),
                'clipping':now<self.clip_until,'sampled_at':now}


def meter_snapshot(status,now=None):
    now=time.monotonic() if now is None else now
    value=(status or {}).get('audio_level',{})
    active=(status or {}).get('state')=='listening' and 0<=now-value.get('sampled_at',-100)<=1.5
    if not active:
        return {'active':False,'level':0,'rms_dbfs':-80,'peak_dbfs':-80,'clipping':False,'label':'No input'}
    return {'active':True,'level':value['level'],'rms_dbfs':value['rms_dbfs'],
            'peak_dbfs':value['peak_dbfs'],'clipping':value['clipping'],
            'label':'Clipping' if value['clipping'] else ('Picking up' if value['rms_dbfs']>=-42 else 'Quiet')}
