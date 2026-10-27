# Hebrew second recognizer

The primary multilingual Whisper Turbo still detects language and produces live drafts. At a speech pause, the same joined audio (up to 24 seconds) is decoded by the primary, then by a Hebrew specialist when Hebrew was recognized, explicitly requested, or was the primary's strong raw detection before guidance. The winner revises the existing utterance ID; all translations remain in that utterance's shared row.

Fragments whose audio timestamps are separated by at most 1.5 seconds can reopen the previous row and be decoded from joined original audio, within the 24-second cap. The prior audio tail is held briefly in memory (three seconds after decoding), then released if no continuation arrives. A longer pause, capture reset, or discarded row prevents rejoining. This is time-based phrase context, not speaker diarization; closely spaced different speakers may share a row. `scripts/pause-context-smoke.py` verifies this with an existing local synthetic recording.

The second model is [ivrit-ai/whisper-large-v3-turbo-ct2](https://huggingface.co/ivrit-ai/whisper-large-v3-turbo-ct2), pinned to `72ad623a37947395efcc3933132353790e5a12f5`. Its authors recommend forcing Hebrew rather than using its degraded language detection, and it is a transcription model rather than a translator. [Model limitations](https://huggingface.co/ivrit-ai/whisper-large-v3-turbo)

## Selection and fallback

- Prefer a usable specialist result. It must contain predominantly Hebrew letters and expose finite segment scores, with average log probability at least -1, no-speech probability at most .4, and compression ratio at most 2.4.
- If the primary also passes those checks, veto a specialist result whose duration-weighted log probability is worse by more than .25, or whose character count is below 35% of the primary's.
- These thresholds are provisional quality heuristics. Raw scores from separately trained models are not calibrated accuracy probabilities. The implementation does not claim to prove acoustic agreement or merge words based on a confidence percentage. Broader human-labelled Hebrew tests are needed to tune selection.
- Empty output, a failed quality check, subprocess crash or timeout preserves the primary transcript. Strong non-Hebrew recognition bypasses the specialist entirely.
- If Hebrew is expected and the leading language score is below .85, an otherwise non-Hebrew primary also gets a Hebrew trial, even when its raw Hebrew detection probability is very low. This closes a routing gap that could leave phonetic Latin-letter output unchecked. For this speculative route, a usable primary is replaced only when the specialist passes the Hebrew gate and its average log probability is at least as high as the primary's. These remain provisional heuristics, not calibrated cross-model confidence. Inspect shows the raw Hebrew evidence and routing reason.
- The specialist has a persistent isolated worker with a 12-second decode budget. On timeout/failure the worker is terminated, releasing resources; the primary continues during a 30-second cooldown, after which later eligible speech can restart the worker automatically. Failures expose a content-free code in Inspect. Initialization has a 90-second budget and failure falls back to the primary.

## Device configuration

The specialist defaults to CPU/int8 to avoid competing with translation and primary ASR on the laptop's 8 GB GPU. The primary remains on CUDA. `--hebrew-device cuda` is available for a separately measured configuration with sufficient GPU memory; it is not the tested default.

Download once while online:

```powershell
.venv\Scripts\python.exe scripts/setup-hebrew.py
```

The downloader pins the model revision, verifies the weight SHA-256, and writes a revision receipt. Regular inference uses local files with no network downloads. Live audio, intermediate candidates and comparisons are never saved as reports; content-free metadata is available as `input.recognition` in `/api/snapshot` after refinement. `input.hebrew_recognizer` reports startup availability/device. Synthetic test reports are explicitly generated development artifacts.

Existing microphone startup automatically enables the second path when the weights are installed:

```powershell
.\scripts\start-deck.ps1 -Microphone -AudioDevice 1
```

Optional CLI flags: `--no-hebrew-second`, `--hebrew-model PATH`, `--hebrew-device cpu|cuda`, `--hebrew-timeout SECONDS`. Display-language choices remain independent from Expected speech. Include Hebrew in Expected speech when appropriate; the specialist does not force every conversation into Hebrew.

## Live inspection

In Clean view, tap **Controls** or press Escape, then choose **Inspect**. The modal shows the latest draft/refinement phase, raw detected language, primary and Hebrew candidate texts, native segment scores, the selected candidate, selection rules and current processing activity. A Hebrew eligibility gate failing for an English transcript is expected; it does not mean that English transcription is poor.

The inspector uses `input.recognition_trace` in the existing local snapshot. It retains only the current decode, replaces it on the next decode and expires its text after 60 seconds when snapshots are polled. No candidate history, audio or diagnostic transcript log is written to disk. The content-free `input.recognition` summary remains available separately. The synthetic inspector screenshot fixture is `scripts/inspector-demo.py`.

## Tests

`tests/test_hebrew.py` covers quality vetoes, missing confidence, language routing, forced Hebrew, worker timeout/termination, fallback, and stable utterance IDs through joined-audio refinement. File input from the CLI uses the same final refinement path.

```powershell
.venv\Scripts\python.exe scripts/hebrew-smoke-test.py
```

This checks existing synthetic Hebrew/English/Russian fixtures using the actual primary GPU model and Hebrew CPU worker, then tests a cut Hebrew phrase through final refinement and translation. Its report is `artifacts/hebrew-smoke-test.json`. Word error rates are comparisons against these synthetic prompts only, not a representative Hebrew benchmark.

## User-recorded regression case

Three locally recorded, user-labelled phrases exposed the gate failure: the primary returned Polish/Czech phonetic text while assigning Hebrew less than 1% language probability. The ivrit.ai specialist recovered all three phrases correctly; forcing Hebrew on the multilingual primary still produced errors. The uncertain-language route now tries the specialist whenever Hebrew is expected, and compares usable candidate scores without the former extra .15 margin. This provisional rule passed these recordings; it is not a general cross-language calibration claim.

The three case recordings and reports are kept separately in artifacts/hebrew-debug-case for local replay, outside the rolling 20-clip directory. They contain real microphone speech and are not uploaded. Run scripts/replay-hebrew-case.py --verify for end-to-end selection and translation.
