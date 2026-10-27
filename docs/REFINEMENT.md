# Pause refinement and presentation update

## Speech lifecycle

Live capture emits a six-second chunk as a draft paragraph, retaining the original PCM audio. Further chunks before the speech pause update that same paragraph ID. A 700 ms pause triggers a second Whisper decoding pass over the joined audio (beam 5 with previous-text conditioning). Final source text replaces the draft, and translations are regenerated for the selected languages when the text changes.

Paragraph revisions travel with translation jobs. A request started for an earlier revision cannot overwrite a newer paragraph. Unchanged source text can be marked final without generating duplicate translations. The audio window is bounded at 24 seconds; a longer continuous turn is finalized in bounded windows. This does not guarantee a complete entire-turn correction for arbitrarily long speech.

If final decoding fails, the source draft survives and List view shows `unrefined`. Capture generations prevent stitching across a dropped audio/clip queue or a device reconnection. This is acoustic re-decoding, not generated paraphrasing; the resulting recognition can still be incorrect.

## Display and language selection

- Clean view: paragraph columns with one flag header per selected language, Hebrew/other RTL direction support, and subdued draft/refining text. It follows new text while the reader remains near the bottom.
- List view: aligned rows with source/translation and processing statuses.
- A flag click flips a language's presentation 180 degrees. View and flip preferences are stored in the browser.
- Languages: searchable by English name, native name or language code, one to six outputs from the installed model's advertised catalog. The selection affects actual inference, persists in `config/languages.json`, backfills the latest two paragraphs, and applies to subsequent speech.
- Flags are vendored from flag-icons v7.3.2, MIT licensed (license under `babblet/static/flags/`); no network is needed by the viewer. Language support comes from the [Hy-MT2 model card](https://huggingface.co/tencent/Hy-MT2-1.8B-GGUF#supported-languages). Additional catalog languages have not all been tested locally.

## Verification

- 22 regression tests passed, covering cutoff/pause detection, joined-audio replacement, stale translation rejection, refinement failure fallback, language validation, persistence, same-origin configuration, and the existing pipeline behavior.
- A real local-model test deliberately split each English/Hebrew/Russian synthetic recording at two-second intervals. Each had four forced mid-speech cuts; the final pause produced one paragraph per recording in all three cases, with final translations and no model errors. Evidence: [refinement-smoke-test.json](benchmark/refinement-smoke-test.json). Reproduce with `python scripts/refinement-smoke-test.py` while the translation server is running.
- Browser checks exercised Clean/List switching, search for French, selection and actual French translation backfill. Hebrew and local SVG flag rendering were visually inspected. The original live microphone setting (device 1) was restored after testing.

The live microphone stream is not saved to disk by this update. The retained test evidence contains only generated speech. Real conversational accuracy, overlapping voices and long installation sessions still require further testing.
