import argparse
import asyncio
import json
import time
from pathlib import Path

from babblet.adapters import SpeechRecognizer, Translator
from babblet.core import Pipeline
from babblet.runner import microphone, process_file
from babblet.web import create_app
from babblet.languages import CATALOG
from babblet.speech_languages import SPEECH_CATALOG,load_speech_guidance


async def execute(args):
    selection_path = Path(args.language_config)
    targets = args.targets
    if targets is None and selection_path.exists():
        targets = json.loads(selection_path.read_text(encoding='utf-8'))
    pipeline = Pipeline(Translator(args.translation_url), max_age=args.max_job_age,targets=targets)
    speech_path=Path(args.speech_config)
    guidance=load_speech_guidance(pipeline.targets,speech_path,expected_override=args.expected_languages)
    status = {'state': 'loading'}
    tasks = []
    started = time.perf_counter()
    recognizer = None
    if args.audio or args.mic:
        recognizer = await asyncio.to_thread(SpeechRecognizer, args.model, args.device,guidance=guidance)
        if not args.no_hebrew_second:
            from babblet.hebrew import HebrewSecondRecognizer,HebrewWorker
            if Path(args.hebrew_model,'model.bin').exists():
                try:
                    secondary=await asyncio.to_thread(HebrewWorker,args.hebrew_model,
                        args.hebrew_device,args.hebrew_timeout)
                    status['recognition_trace']={}
                    recognizer=HebrewSecondRecognizer(recognizer,secondary,trace=status['recognition_trace'])
                    status['hebrew_recognizer']={'enabled':True,'device':args.hebrew_device}
                except Exception:
                    status['hebrew_recognizer']={'enabled':False,'reason':'load_failed'}
            else:
                status['hebrew_recognizer']={'enabled':False,'reason':'model_not_installed'}
    if recognizer is not None and args.debug_audio:
        from babblet.debug_audio import DebugRecorder,RecordingRecognizer
        recorder=DebugRecorder(args.debug_audio)
        status['debug_recording']={'enabled':True,'directory':str(Path(args.debug_audio).resolve()),
                                   'limit':20,'saved':0}
        recognizer=RecordingRecognizer(recognizer,recorder,status)
    load_seconds = time.perf_counter() - started
    tasks.append(asyncio.create_task(pipeline.run()))
    if args.serve:
        import uvicorn
        server = uvicorn.Server(uvicorn.Config(create_app(pipeline, status,selection_path,guidance,speech_path),
            host='127.0.0.1', port=args.port, log_level='warning'))
        tasks.append(asyncio.create_task(server.serve()))
    try:
        metrics = []
        for audio in args.audio:
            status['state'] = 'transcribing'
            metrics.append(await process_file(audio, recognizer, pipeline, args.language,
                                              wait_translation=True,status=status,refine=True))
        while pipeline.pending or pipeline.processing:
            await asyncio.sleep(0.05)
        report = {'model': args.model, 'device': args.device, 'load_seconds': load_seconds,
            'elapsed_seconds': time.perf_counter() - started,
            'files': metrics, **pipeline.snapshot()}
        status['state'] = 'ready'
        if args.report:
            path = Path(args.report)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=True, indent=2), flush=True)
        if args.mic:
            await microphone(recognizer, pipeline, status, args.audio_device)
        elif args.serve:
            await tasks[-1]
        errors = sum(report['health'][key] for key in ('errors', 'expired', 'dropped'))
        missing = any(m['segments'] == 0 for m in metrics)
        return 1 if errors or missing else 0
    finally:
        if hasattr(recognizer,'close'):
            await asyncio.to_thread(recognizer.close)
        pipeline.closed = True
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def main():
    parser = argparse.ArgumentParser(description='Babblet offline speech translation')
    parser.add_argument('--model', default='models/whisper-turbo')
    parser.add_argument('--hebrew-model',default='models/whisper-hebrew')
    parser.add_argument('--hebrew-device',choices=['cpu','cuda'],default='cpu')
    parser.add_argument('--hebrew-timeout',type=float,default=12)
    parser.add_argument('--no-hebrew-second',action='store_true')
    parser.add_argument('--debug-audio',metavar='DIRECTORY',help='Record the last 20 refinement clips locally for debugging')
    parser.add_argument('--device', choices=['cuda', 'cpu'], default='cuda')
    parser.add_argument('--audio', nargs='*', default=[])
    parser.add_argument('--language', choices=['en', 'he', 'ru'])
    parser.add_argument('--targets',nargs='+',choices=list(CATALOG))
    parser.add_argument('--language-config',default='config/languages.json')
    parser.add_argument('--expected-languages',nargs='*',choices=list(SPEECH_CATALOG))
    parser.add_argument('--speech-config',default='config/speech-languages.json')
    parser.add_argument('--translation-url', default='http://127.0.0.1:18081/v1')
    parser.add_argument('--max-job-age', type=float, default=8)
    parser.add_argument('--report')
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--port', type=int, default=8090)
    parser.add_argument('--mic', action='store_true')
    parser.add_argument('--audio-device', type=int)
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(execute(args)))
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
