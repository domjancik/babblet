"""Bounded, offline Hebrew second pass. No audio or transcripts are persisted."""
import math
import multiprocessing
import time


def quality(segments,require_hebrew=True):
    if not segments:
        return None
    text=' '.join(segment['text'] for segment in segments)
    letters=[char for char in text if char.isalpha()]
    if not letters or (require_hebrew and sum('\u0590'<=char<='\u05ff' for char in letters)/len(letters)<.5):
        return None
    weights=[max(.01,segment.get('end',0)-segment.get('start',0)) for segment in segments]
    scores=[]
    for segment in segments:
        score=segment.get('avg_logprob',float('nan'))
        silence=segment.get('no_speech_prob',float('nan'))
        compression=segment.get('compression_ratio',float('nan'))
        if (not all(math.isfinite(value) for value in (score,silence,compression))
                or score < (-1 if require_hebrew else -1.5) or silence > .4 or compression > 2.4):
            return None
        scores.append(score)
    return sum(score*weight for score,weight in zip(scores,weights))/sum(weights)


def choose_hebrew(primary,secondary,require_advantage=False):
    """Prefer a usable Hebrew specialist, veto obvious quality regressions.

    These are conservative heuristics, not calibrated cross-model probabilities.
    Neither transcript is rewritten or word-spliced by another language model.
    """
    second_score=quality(secondary)
    first_score=quality(primary)
    if second_score is None:
        return primary,'primary'
    if require_advantage and primary:
        # A speculative Hebrew decode must not win merely by using Hebrew letters.
        acoustic_score=quality(primary,require_hebrew=False)
        if acoustic_score is None or second_score < acoustic_score:
            return primary,'primary'
    if first_score is not None:
        first_length=len(' '.join(s['text'] for s in primary))
        second_length=len(' '.join(s['text'] for s in secondary))
        if second_score < first_score-.25 or second_length < first_length*.35:
            return primary,'primary'
    return secondary,'hebrew'


def candidate_summary(segments):
    def finite(value):
        return round(float(value),4) if value is not None and math.isfinite(value) else None
    return {'text':' '.join(segment['text'] for segment in segments)[:8000],
            'language':segments[0]['language'] if segments else None,
            'quality_score':quality(segments),
            'segments':[{key:finite(segment.get(key)) for key in
                ('start','end','avg_logprob','no_speech_prob','compression_ratio')}
                for segment in segments[:80]]}


class HebrewSecondRecognizer:
    def __init__(self,primary,secondary,trace=None):
        self.primary=primary
        self.secondary=secondary
        self.last_comparison={'enabled':True,'selected':'primary','reason':'not_run'}
        self.trace=trace if trace is not None else {}

    def transcribe(self,audio,language=None,refine=False):
        self.trace.update(phase='decoding_primary',updated_at=time.time(),
            primary=None,secondary=None,selected=None,reason='decoding_primary',
            detection=None,secondary_seconds=0,routing='primary_only',failure=None)
        primary=self.primary.transcribe(audio,language,refine)
        detected=getattr(self.primary,'last_detection',{}) or {}
        self.trace.update(primary=candidate_summary(primary),detection=detected,
                          phase='draft',selected='primary',reason='live_draft')
        if not refine:
            return primary
        hebrew=(language=='he' or (primary and primary[0]['language']=='he') or
                (language is None and detected.get('language')=='he' and detected.get('probability',0)>=.5))
        hinted=(language is None and 'he' in detected.get('expected',[]) and
                detected.get('probability',1)<.85)
        self.trace['routing']='detected_hebrew' if hebrew else ('ambiguous_hebrew_hint' if hinted else 'not_hebrew')
        self.last_comparison={'enabled':True,'selected':'primary',
                              'reason':'not_hebrew','secondary_seconds':0,'failure':None}
        if not hebrew and not hinted:
            self.trace.update(phase='final',reason='not_hebrew',updated_at=time.time())
            return primary
        started=time.monotonic()
        self.trace.update(phase='decoding_hebrew',reason='waiting_for_hebrew',selected=None)
        try:
            secondary=self.secondary.transcribe(audio,'he',True)
            self.trace['secondary']=candidate_summary(secondary)
            result,selected=choose_hebrew(primary,secondary,require_advantage=not hebrew)
            self.last_comparison.update(selected=selected,reason='specialist_accepted' if selected=='hebrew' else 'quality_veto')
            return result
        except Exception as error:
            self.last_comparison['reason']='secondary_failed'
            # Fixed codes expose operational failures without leaking decoder input.
            self.last_comparison['failure']=('timeout' if isinstance(error,TimeoutError)
                else 'worker_unavailable' if isinstance(error,(RuntimeError,EOFError,BrokenPipeError))
                else 'decode_failed')
            return primary
        finally:
            self.last_comparison['secondary_seconds']=round(time.monotonic()-started,3)
            self.trace.update(self.last_comparison,phase='final',updated_at=time.time())

    def close(self):
        close=getattr(self.secondary,'close',None)
        if close:
            close()


def _worker(connection,path,device):
    from babblet.adapters import SpeechRecognizer
    try:
        recognizer=SpeechRecognizer(path,device)
        connection.send(('ready',None))
        while True:
            audio=connection.recv()
            if audio is None:
                return
            connection.send(('result',recognizer.transcribe(audio,'he',True)))
    except (EOFError,BrokenPipeError):
        pass
    except Exception:
        # Send no exception details: native decoders can include input content.
        try:
            connection.send(('error',None))
        except (EOFError,BrokenPipeError,OSError):
            pass
    finally:
        connection.close()


class HebrewWorker:
    """One persistent process, terminated on timeout rather than leaking threads."""
    def __init__(self,path,device='cpu',timeout=12,load_timeout=90):
        self.timeout=timeout
        self.path=str(path)
        self.device=device
        self.load_timeout=load_timeout
        self.closed=False
        self.restart_at=0
        self._start()

    def _start(self):
        # At most one new worker per cooldown; never retry the same audio or
        # retain timed-out native decoders in background threads.
        self.restart_at=time.monotonic()+30
        context=multiprocessing.get_context('spawn')
        self.connection,child=context.Pipe()
        self.process=context.Process(target=_worker,args=(child,self.path,self.device),daemon=True)
        self.process.start()
        child.close()
        try:
            if not self.connection.poll(self.load_timeout) or self.connection.recv()[0]!='ready':
                raise RuntimeError('Hebrew recognizer failed to load')
        except Exception:
            self._stop()
            raise

    def transcribe(self,audio,language=None,refine=False):
        if getattr(self,'closed',False):
            raise RuntimeError('Hebrew recognizer is closed')
        if not self.process.is_alive():
            if time.monotonic()<getattr(self,'restart_at',float('inf')):
                raise RuntimeError('Hebrew recognizer is recovering')
            self._stop()
            self._start()
        try:
            self.connection.send(audio)
            if not self.connection.poll(self.timeout):
                raise TimeoutError('Hebrew refinement exceeded its time budget')
            kind,result=self.connection.recv()
            if kind!='result':
                raise RuntimeError('Hebrew refinement failed')
            return result
        except Exception:
            self._stop()
            self.restart_at=time.monotonic()+30
            raise

    def close(self):
        self.closed=True
        self._stop()

    def _stop(self):
        if self.process.is_alive():
            self.process.terminate()
        self.process.join(timeout=2)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(timeout=2)
        self.connection.close()
