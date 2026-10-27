# Expected speaking languages and suggestions

Expected speech follows **Display** by default: selecting translation languages also guides recognition toward those same supported speech languages. **Languages → Expected speech → Follow display** can be switched off to choose an independent set. Changes apply immediately. An empty independent expected set means automatic detection.

The expected-language list remains in `config/speech-languages.json`. The follow-display policy is saved separately in `config/speech-sync.json` as `{"sync_with_display": true|false}`. A missing policy file means enabled. Disabling it preserves the current expected set; enabling it immediately aligns the set with the current display choices. Unsupported speech variants are filtered out, so a display set containing only unsupported input hints falls back to automatic detection. The policy is loaded before the recognizer starts.

The CLI supports `--expected-languages en he ru` or an empty `--expected-languages` for automatic mode. An explicit CLI expected-language override disables synchronization for that run. The browser and tablet expose the current policy, and settings changed through either client are visible to the other.

API: `GET /api/speech-languages` includes `sync_with_display`. `POST` with `{"sync_with_display":false}` toggles the policy; the existing `{"languages":[...]}` payload explicitly chooses independent input languages and turns the link off. Both require the existing same-origin protection. The tablet gateway accepts authenticated `POST /v1/languages` with `{"mode":"sync","enabled":true|false}`; normal display/speech payloads retain their existing form. `/api/tablet` includes the same top-level policy boolean.

## Recognition guidance

The installed faster-whisper runtime exposes Whisper's acoustic language probabilities. With expected languages configured, Babblet runs that detector first and prefers the strongest expected candidate when its raw score is at least 0.15 and twice that score reaches the strongest unrestricted candidate. This is a small explicit prior, not a strict whitelist. Strong outside-language evidence still wins. Raw detection and the language used for decoding are tracked separately so guidance cannot manufacture evidence for its own suggestions.

No new model, training, cloud inference, or word-list classifier is required. The extra detection pass adds some work when guidance is enabled. With automatic detection, the runtime's normal language detection is retained. The expected-language picker uses the intersection of this translation catalog and installed Whisper support: Traditional Chinese is represented by spoken Chinese (`zh`), and Uyghur is not offered as an input hint by this Whisper build.

## Optional suggestions

The Expected speech tab offers an **Add** chip after a language is detected in at least two completed speech/refinement turns, with a raw model score of at least 0.75 and at least 1.5 seconds of detected speech per turn. Up to three languages outside the expected set are suggested. Independent speech selection is available after switching Follow display off; flag/suggestion toggles save immediately, without an Apply button. Suggestions never automatically change recognition preferences or translation outputs.

Observations expire after two minutes and are bounded to 64 language/score/time tuples in memory. No recognized words, recordings, or transcripts are stored for suggestion history. Model scores are heuristic evidence rather than calibrated confidence, and short utterances, noise and code-switching can still produce incorrect language detections.

## Verification

Current sync-policy regressions cover default alignment, catalog intersection, opt-out persistence across restarts, immediate realignment, explicit CLI overrides, manual compatibility, authenticated gateway forwarding, strict boolean validation and same-origin enforcement. Older verification notes below describe the original independent-language implementation.

- 31 Python regression tests passed, including ambiguous-language guidance, clear outside-language acceptance, suggestion thresholds/expiry, independent input/output settings, persistence, origin checks and the native detector's required VAD option type. Four existing pagination tests also passed.
- Real local Whisper Turbo inference passed for English, Hebrew and Russian synthetic fixtures with all three expected.
- With only English expected, two completed Hebrew fixture turns were still recognized as Hebrew and produced a Hebrew suggestion. No transcript text was retained in that test report: [speech-language-smoke-test.json](benchmark/speech-language-smoke-test.json).
- Browser verification accepted the Hebrew suggestion and saved expected languages `en, he`, while display languages stayed `en, he, ru` in the isolated synthetic UI fixture. The live app retained the user's own saved display settings and automatic speech mode.

Reproduce the local model check with `python scripts/speech-language-smoke-test.py`. The optional `speech-language-demo.py` fixture uses only its synthetic detection metadata on port 8091.
