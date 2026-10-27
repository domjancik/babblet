# Translation benchmark — 26 October 2026

RTX 4070 Laptop GPU, 8 GB VRAM. Whisper large-v3-turbo remains resident during each translation benchmark. Candidates run sequentially, with no concurrent test-model jobs. All model inference uses local weights and offline mode.

| Model | Completed | Median request | p95 request | Mean chrF++ | Sampled system GPU peak |
|---|---:|---:|---:|---:|---:|
| Hy-MT2 1.8B Q4_K_M | 40/40 | 0.347 s | 0.491 s | 76.34 | 5433 MiB |
| Hy-MT2 1.8B Q8_0 | 40/40 | 0.391 s | 0.593 s | 77.97 | 6192 MiB |
| NLLB-200 distilled 600M FP16 | 40/40 | 0.169 s | 0.304 s | 72.32 | 5348 MiB |

Request time excludes model loading and one warmup request. The llama.cpp candidates use greedy decoding (`temperature=0`), a 2048-token context, a single slot, full GPU offload and a 256-token output limit. NLLB uses greedy decoding, a forced target language and a 256-token output limit. The runtime stacks differ, so these are deployment measurements rather than isolated architecture comparisons. Model load times were approximately 1.6 s (Q4), 2.9 s (Q8), and 14.9 s (NLLB, including Transformers initialization).

## Corpus and limits

Each candidate translated the same 24 curated sentences (four meanings × six language directions) and 16 segments from recognized synthetic English/Hebrew/Russian speech. chrF++ is averaged over the 24 curated cases with manually written parallel references. The recognized-text cases have no reference score. No inference errors occurred in the final 120 requests.

The corpus is small and synthetic. Scores measure character/word overlap with one possible reference, not human adequacy. Equivalent wording can score lower; fluent mistranslations can score high. GPU usage is sampled system-wide and includes the desktop and other existing applications; it is not an isolated model allocation or guaranteed peak under load. Whisper is loaded but not actively transcribing during this comparison; the separate audio smoke test exercises actual ASR and MT in the same run.

## Initial decision

Use **Whisper Turbo + Hy-MT2 Q8** as the initial device default, retaining Q4 as a lower-memory fallback. Q8 fit alongside the recognizer with useful VRAM headroom and corrected one material Q4 English→Hebrew error: “near the entrance” became “after the entrance” with Q4 but was preserved with Q8. Its median latency increase was about 44 ms per request in this run.

Q8 is not consistently superior. Its Hebrew→English reference similarity was lower than Q4 in this sample. Both Hy-MT2 variants mistranslated the English word “tablet” as a pill in a Russian output; NLLB also had errors on that sentence and produced malformed Hebrew words in another output. These failures remain visible in the retained outputs rather than being patched with word substitutions.

NLLB was the fastest and had the best Hebrew→Russian reference similarity on this corpus (85.94 versus 72.32 for Q4 and 69.40 for Q8). It remains a useful benchmark alternative, with its noncommercial research-model license and uneven outputs taken into account.

## End-to-end verification

- **14 automated tests passed**: queue limits, stale-job expiry, deduplication, source preservation, translation failure recovery, unexpected engine errors, script-based routing, silence handling, recorded-input pacing, local API access controls and benchmark coverage.
- **Five audio passes passed**: 15 recordings (English, Hebrew, Russian repeated five times), totaling 142.47 seconds of speech, produced 80 translations with zero errors, expired jobs, dropped jobs or pending jobs. Processing took 43.14 seconds after model load. Median complete-file processing was 2.71 seconds for a roughly 9.5-second recording; this is not live speech-to-display latency.
- Mean ASR inference time per recording was 0.587 s (English), 0.532 s (Hebrew), and 0.495 s (Russian). Source-reference chrF was 100.0, 94.79, and 96.30 respectively, with automatic language detection enabled. These are character similarity scores on three synthetic utterances, not word-error rates.
- **Live endpointing path passed**: the same recordings were supplied as 100 ms PCM frames through the capture segmenter, producing nine recognized utterances and 18 translations without queue or model errors. This exercises the segmentation code used by the microphone, without claiming to test a physical microphone or disconnect recovery.
- Deterministic silence and noise controls produced zero source segments.
- The running display returned HTTP 200 with eight utterances and 16 complete translations, zero pending/errors. A foreign Origin was rejected with 403, and an unauthenticated translation request was rejected with 401. Browser inspection confirmed the three-column display and Hebrew RTL layout.

Reports: [smoke-test.json](benchmark/smoke-test.json) and [stream-smoke-test.json](benchmark/stream-smoke-test.json). The short repeat tests do not establish all-day reliability. Failure recovery and microphone reconnection are implemented; physical disconnects, room acoustics, overlapping speakers and exhibition-duration soak testing remain unverified.

## Reproduce and inspect

Run `python -m babblet.benchmark q4`, then `q8`, then `nllb`. The harness saves all inputs, references, outputs, per-case timings, per-direction summaries and sampling caveats. Raw final reports are retained in [benchmark/q4.json](benchmark/q4.json), [benchmark/q8.json](benchmark/q8.json), and [benchmark/nllb.json](benchmark/nllb.json).

This establishes a functioning local ML pipeline and an initial default. It does not establish exhibition-duration reliability, mixed-language recognition accuracy, diarization quality, or performance on a reMarkable tablet.
