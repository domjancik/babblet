"""Audio ingestion shared by recorded tests and live capture."""
import asyncio
import queue
import time
import uuid

from faster_whisper.audio import decode_audio

from babblet.adapters import Segmenter
from babblet.refinement import SpeechSession
from babblet.audio_level import AudioLevel
from babblet.activity import decode_audio as recognize_audio


async def process_file(path, recognizer, pipeline, language=None, wait_translation=False,status=None,refine=False):
    audio = await asyncio.to_thread(decode_audio, str(path), sampling_rate=16000)
    started = time.perf_counter()
    segments = await recognize_audio(recognizer,audio,language,refine=refine,status=status)
    asr_seconds = time.perf_counter() - started
    prefix = uuid.uuid4().hex[:12]
    for i, segment in enumerate(segments):
        await pipeline.submit(f'{prefix}:{i}', segment['text'], segment['language'],
                              segment['start'], segment['end'])
        if wait_translation:
            await pipeline.drain()
            while pipeline.pending or pipeline.processing:
                await asyncio.sleep(0.02)
    return {'file': str(path), 'audio_seconds': len(audio) / 16000,
            'asr_seconds': asr_seconds, 'segments': len(segments)}


async def microphone(recognizer, pipeline, status, device=None):
    import sounddevice as sd
    frames = queue.Queue(maxsize=80)
    clips = asyncio.Queue(maxsize=3)
    level_meter=AudioLevel()
    status.update(state='starting', dropped_frames=0, dropped_clips=0, asr_errors=0)

    def capture(data, count, timing, flags):
        # Measure directly in capture so the meter is independent of ASR lag.
        status['audio_level']=level_meter.sample(data[:,0])
        if flags:
            status['audio_warning'] = str(flags)
        try:
            frames.put_nowait((data[:, 0].copy(),status.get('capture_generation',0)))
        except queue.Full:
            status['dropped_frames'] += 1
            status['capture_generation'] = status.get('capture_generation',0)+1

    async def recognize():
        session = SpeechSession(recognizer,pipeline,activity=status)
        active_generation = None
        while True:
            audio, start, boundary, generation = await clips.get()
            status['audio_queued']=clips.qsize()
            try:
                if generation != status.get('capture_generation'):
                    session.reset()
                    continue
                if generation != active_generation:
                    session.reset()
                    active_generation = generation
                await session.process(audio,start,boundary)
                status['last_asr_success'] = time.time()
            except Exception as exc:
                session.reset()
                status['asr_errors'] += 1
                status['last_asr_error'] = type(exc).__name__
            finally:
                clips.task_done()

    worker = asyncio.create_task(recognize())
    try:
        while True:
            status['capture_generation'] = status.get('capture_generation',0)+1
            frame_generation = status['capture_generation']
            segmenter = Segmenter()
            while not frames.empty():
                frames.get_nowait()
            try:
                with sd.InputStream(samplerate=16000, channels=1, dtype='float32',
                                    blocksize=1600, device=device, callback=capture):
                    status['state'] = 'listening'
                    while True:
                        try:
                            frame, generation = frames.get_nowait()
                        except queue.Empty:
                            await asyncio.sleep(0.02)
                            continue
                        status['last_frame'] = time.time()
                        if generation != frame_generation:
                            segmenter = Segmenter()
                            frame_generation = generation
                        clip = segmenter.push(frame)
                        status['receiving_speech']=bool(segmenter.frames or segmenter.continuing)
                        if clip is not None:
                            if clips.full():
                                clips.get_nowait()
                                clips.task_done()
                                status['dropped_clips'] += 1
                                status['capture_generation'] += 1
                            clips.put_nowait((clip, time.time() - len(clip)/16000,
                                segmenter.last_boundary,generation))
                            status['audio_queued']=clips.qsize()
                        if not sd.query_devices(device, 'input'):
                            raise OSError('Audio device lost')
            except (sd.PortAudioError, OSError) as exc:
                status.update(state='reconnecting', error=type(exc).__name__,receiving_speech=False)
                await asyncio.sleep(2)
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
