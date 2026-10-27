from types import SimpleNamespace

import numpy as np
import pytest

from babblet.hebrew import HebrewSecondRecognizer, HebrewWorker, choose_hebrew


def segments(text='שלום עולם', score=-.2, silence=.01, compression=1.1, language='he'):
    return [{'text':text,'language':language,'start':0,'end':2,
             'avg_logprob':score,'no_speech_prob':silence,'compression_ratio':compression}]


def test_selection_prefers_usable_specialist_but_rejects_clear_regressions():
    primary=segments(score=-.35)
    specialist=segments('שלום לכולם',score=-.3)
    assert choose_hebrew(primary,specialist)[0] is specialist
    assert choose_hebrew(primary,segments(score=-1.3))[0] is primary
    assert choose_hebrew(primary,segments(silence=.7))[0] is primary
    assert choose_hebrew(primary,segments(compression=3))[0] is primary
    assert choose_hebrew(primary,segments('Thank you'))[0] is primary
    assert choose_hebrew(primary,[])[0] is primary


def test_missing_confidence_is_not_treated_as_high_confidence():
    assert choose_hebrew(segments(),[{'text':'שלום','language':'he'}])[1]=='primary'


class Recognizer:
    def __init__(self,result): self.result=result;self.calls=[]
    def transcribe(self,audio,language=None,refine=False):
        self.calls.append((language,refine,len(audio)))
        return self.result


def test_second_model_only_runs_for_hebrew_final_pass_and_is_forced_to_hebrew():
    primary=Recognizer(segments());second=Recognizer(segments('שלום לכולם'))
    dual=HebrewSecondRecognizer(primary,second)
    audio=np.ones(32000,dtype=np.float32)*.1
    dual.transcribe(audio)
    assert second.calls==[]
    result=dual.transcribe(audio,refine=True)
    assert second.calls==[('he',True,len(audio))]
    assert result[0]['text']=='שלום לכולם'
    assert dual.last_comparison['selected']=='hebrew'
    primary.result=segments('Hello',language='en')
    dual.transcribe(audio,refine=True)
    assert len(second.calls)==1
    assert dual.last_comparison['reason']=='not_hebrew'


def test_specialist_failure_keeps_the_primary_result():
    class Failed:
        def transcribe(self,*args): raise TimeoutError('worker timed out')
    primary=Recognizer(segments());dual=HebrewSecondRecognizer(primary,Failed())
    assert dual.transcribe(np.ones(32000,dtype=np.float32),refine=True)==primary.result
    assert dual.last_comparison['reason']=='secondary_failed'
    assert dual.last_comparison['failure']=='timeout'


def test_dead_worker_recovers_after_cooldown_but_explicit_close_stays_closed(monkeypatch):
    class Process:
        def is_alive(self): return False
        def join(self,**kwargs): pass
    class Connection:
        def close(self): pass
        def send(self, audio): pass
        def poll(self, timeout): return True
        def recv(self): return 'result', segments()
    worker=HebrewWorker.__new__(HebrewWorker)
    worker.process=Process();worker.connection=Connection();worker.timeout=12
    worker.closed=False;worker.restart_at=105
    starts=[]
    def start():
        starts.append(True)
        worker.process=SimpleNamespace(is_alive=lambda:True)
    worker._start=start
    monkeypatch.setattr('babblet.hebrew.time.monotonic',lambda:100)
    with pytest.raises(RuntimeError): worker.transcribe(np.zeros(10))
    assert not starts
    monkeypatch.setattr('babblet.hebrew.time.monotonic',lambda:106)
    assert worker.transcribe(np.zeros(10))==segments()
    assert len(starts)==1
    worker.closed=True
    with pytest.raises(RuntimeError): worker.transcribe(np.zeros(10))
    assert len(starts)==1


def test_specialist_text_is_used_for_every_translation_after_refinement():
    import asyncio
    from babblet.core import Pipeline
    from babblet.refinement import SpeechSession
    async def run():
        calls=[]
        class Translator:
            async def translate(self,text,source,target):
                calls.append((text,source,target))
                return 'translated '+target
        primary=Recognizer(segments('Ani Medaber Ivrit Achshav',score=-.93,language='en'))
        primary.last_detection={'language':'en','probability':.12,'expected':['he','en']}
        dual=HebrewSecondRecognizer(primary,Recognizer(segments('אני מדבר עברית עכשיו')))
        pipeline=Pipeline(Translator(),targets=['cs','he','en','fr'])
        session=SpeechSession(dual,pipeline)
        await session.process(np.ones(16000,dtype=np.float32),0,'limit')
        await pipeline.drain()
        calls.clear()
        await session.process(np.ones(8000,dtype=np.float32),1,'pause')
        await pipeline.drain()
        assert set(calls)=={('אני מדבר עברית עכשיו','he',target) for target in pipeline.targets}
        session.reset()
    asyncio.run(run())


def test_raw_hebrew_detection_can_trigger_second_pass_when_guidance_misroutes():
    primary=Recognizer(segments('wrong',language='cs'))
    primary.last_detection={'language':'he','probability':.9}
    dual=HebrewSecondRecognizer(primary,Recognizer(segments()))
    assert dual.transcribe(np.ones(32000,dtype=np.float32),refine=True)[0]['language']=='he'


def test_adapter_exposes_native_quality_without_changing_transcription():
    from babblet.adapters import SpeechRecognizer
    class Model:
        def transcribe(self,*args,**kwargs):
            segment=SimpleNamespace(text='שלום',start=0,end=1,no_speech_prob=.01,
                                    avg_logprob=-.2,compression_ratio=1.1)
            return iter([segment]),SimpleNamespace(language='he',language_probability=.95)
    result=SpeechRecognizer(model=Model()).transcribe(np.ones(16000,dtype=np.float32)*.1)
    assert result[0]['avg_logprob']==-.2
    assert result[0]['no_speech_prob']==.01
    assert result[0]['compression_ratio']==1.1


def test_timed_out_worker_is_terminated_and_not_reused():
    class Process:
        alive=True
        def is_alive(self): return self.alive
        def terminate(self): self.alive=False
        def join(self,**kwargs): pass
    class Connection:
        closed=False
        def send(self,audio): pass
        def poll(self,timeout): return False
        def close(self): self.closed=True
    worker=HebrewWorker.__new__(HebrewWorker)
    worker.process=Process();worker.connection=Connection();worker.timeout=.01
    with pytest.raises(TimeoutError): worker.transcribe(np.zeros(10))
    assert not worker.process.alive and worker.connection.closed
    with pytest.raises(RuntimeError): worker.transcribe(np.zeros(10))


def test_second_pass_refines_original_utterance_in_place():
    import asyncio
    from babblet.core import Pipeline
    from babblet.refinement import SpeechSession
    async def run():
        pipeline=Pipeline(None)
        primary=Recognizer(segments('שלום',score=-.4))
        dual=HebrewSecondRecognizer(primary,Recognizer(segments('שלום לכולם')))
        status={};session=SpeechSession(dual,pipeline,activity=status)
        await session.process(np.ones(16000,dtype=np.float32),0,'limit')
        uid=next(iter(pipeline.items))
        await session.process(np.ones(8000,dtype=np.float32),1,'pause')
        assert list(pipeline.items)==[uid]
        assert pipeline.items[uid]['source_text']=='שלום לכולם'
        assert pipeline.items[uid]['revision']==2
        assert status['recognition']['selected']=='hebrew'
        assert not any('text' in key for key in status['recognition'])
    asyncio.run(run())


def test_inspector_keeps_only_latest_candidates_and_explains_the_choice():
    trace={};primary=Recognizer(segments('שלום',score=-.3))
    dual=HebrewSecondRecognizer(primary,Recognizer(segments('שלום לכולם')),trace=trace)
    dual.transcribe(np.ones(32000,dtype=np.float32),refine=True)
    assert trace['primary']['text']=='שלום'
    assert trace['secondary']['text']=='שלום לכולם'
    assert trace['selected']=='hebrew' and trace['phase']=='final'
    assert trace['primary']['segments'][0]['avg_logprob']==-.3
    primary.result=segments('New draft',language='en')
    dual.transcribe(np.ones(16000,dtype=np.float32))
    assert trace['phase']=='draft'
    assert trace['primary']['text']=='New draft'
    assert trace['secondary'] is None
    assert 'שלום' not in str(trace)


def test_inspector_sanitizes_nonfinite_scores_for_json():
    import json
    primary=Recognizer(segments(score=float('nan')))
    dual=HebrewSecondRecognizer(primary,Recognizer([]))
    dual.transcribe(np.ones(32000,dtype=np.float32),refine=True)
    json.dumps(dual.trace,allow_nan=False)


def test_ambiguous_detection_tries_hebrew_when_expected_and_requires_score_advantage():
    primary=Recognizer(segments('shalom olam',score=-.8,language='en'))
    primary.last_detection={'language':'en','probability':.6,'hebrew_probability':.2,'expected':['he','cs']}
    second=Recognizer(segments('שלום עולם',score=-.2))
    dual=HebrewSecondRecognizer(primary,second)
    assert dual.transcribe(np.ones(32000,dtype=np.float32),refine=True)[0]['language']=='he'
    assert len(second.calls)==1
    assert dual.trace['routing']=='ambiguous_hebrew_hint'
    primary.result=segments('Hello everyone',score=-.1,language='en')
    assert dual.transcribe(np.ones(32000,dtype=np.float32),refine=True)==primary.result
    assert len(second.calls)==2
    assert dual.trace['reason']=='quality_veto'


def test_hebrew_trial_does_not_run_on_strong_english_or_without_hebrew_hint():
    primary=Recognizer(segments('English',language='en'));second=Recognizer(segments())
    dual=HebrewSecondRecognizer(primary,second)
    for probability,expected in [(0.95,['he']),(.6,['cs'])]:
        primary.last_detection={'language':'en','probability':probability,
                                'hebrew_probability':.02,'expected':expected}
        dual.transcribe(np.ones(32000,dtype=np.float32),refine=True)
    assert second.calls==[]


@pytest.mark.parametrize('text,language,probability,hebrew_probability,primary_score,hebrew_text,secondary_score',[
    ('a z Akshaw ze Oved.','pl',.166,.006,-.7189,'אז עכשיו זה עובד.',-.3602),
    ('Zelo oved a chčav.','cs',.274,.0055,-.4344,'זה לא עובד עכשיו.',-.3411),
    ('zelo jutartowy.','pl',.54,.0039,-.623,'זה לא יותר טוב.',-.5986),
])
def test_recorded_hebrew_regressions_reach_specialist_and_select_recovered_words(
        text,language,probability,hebrew_probability,primary_score,hebrew_text,secondary_score):
    primary=Recognizer(segments(text,score=primary_score,language=language))
    primary.last_detection={'language':language,'probability':probability,
        'hebrew_probability':hebrew_probability,'expected':['cs','he']}
    secondary=Recognizer(segments(hebrew_text,score=secondary_score))
    dual=HebrewSecondRecognizer(primary,secondary)
    result=dual.transcribe(np.ones(32000,dtype=np.float32),refine=True)
    assert secondary.calls
    assert result[0]['text']==hebrew_text


def test_adapter_keeps_hebrew_alternative_probability_for_routing():
    from babblet.adapters import SpeechRecognizer
    from babblet.speech_languages import SpeechGuidance
    class Model:
        def detect_language(self,**kwargs): return 'en',.6,[('en',.6),('he',.2),('cs',.2)]
        def transcribe(self,*args,**kwargs):
            return iter([]),SimpleNamespace(language='en',language_probability=.6)
    recognizer=SpeechRecognizer(model=Model(),guidance=SpeechGuidance(['he']))
    recognizer.transcribe(np.ones(16000,dtype=np.float32))
    assert recognizer.last_detection['hebrew_probability']==.2
    assert recognizer.last_detection['expected']==['he']
