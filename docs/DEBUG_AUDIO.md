# Local debug audio capture

Audio capture is opt-in. Fresh desktop installs and standard CLI startup do not save recordings. Existing local preferences are preserved; use desktop Settings to enable or disable debugging.

```powershell
.venv\Scripts\python.exe -m babblet.cli --serve --mic --audio-device 1 --debug-audio artifacts/debug-audio
```

The latest 20 speech-end/refinement inputs are saved as exact float WAV audio at 16 kHz mono, paired with JSON candidate and routing diagnostics. Audio is saved before decoding so failed or timed-out results can be replayed. Nearby phrase redecodes can overlap in their audio. No network upload is performed. Older `clip-*.wav` recordings and their JSON sidecars in this dedicated directory are removed as newer clips arrive. Other files are untouched.

Inspect shows recording status, directory, saved count and the latest filename. Files contain actual microphone speech and recognizer text; they persist on this machine across restarts until overwritten or explicitly removed. Close Inspect does not stop recording. Restart without `--debug-audio` to stop saving; existing files remain.

Saved recordings are intended for local replay against primary automatic decoding, forced Hebrew primary decoding, and the ivrit.ai specialist before further routing changes are made. The recognizer's earlier sound-based errors cannot be reconstructed unless they were recorded.
