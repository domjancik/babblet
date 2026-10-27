# Ephemeral rolling paper display

**Clean and Slots share the same FIFO replacement behavior**: with three rows, A/B/C becomes D/B/C, then D/E/C, then D/E/F. Clean hides the toolbar and adds ink animation; Slots shows controls. Press Escape or tap the faint Controls button to leave Clean. Neither mode clears the entire display.

Both views use fixed-height slots shared across languages. Incoming utterances replace only the oldest slot. Refinements and translation completions stay in their assigned row. The old whole-page renderer and prefix-trimming tests remain as historical support code, but the live Clean view does not use that renderer.

Ink provides a short, subtle phrase fade with no word staggering or clipping sweep; facing layouts use an even quieter opacity change. It can be switched off and respects reduced-motion preferences. Layout remains measured at full text size during the reveal. No fonts, scripts or images are fetched remotely at runtime.

## Rollover means forgetting

The browser sends same-origin, revision-checked receipts to `POST /api/rollover`. Completed paragraphs are removed from the pipeline's memory and translation queue. For a completed paragraph spanning pages, consumed source/translation prefixes are trimmed, leaving only the remainder. These partial paragraphs become display-only and are not backfilled into newly selected languages from discarded source text.

Active drafts/refinement and still-pending translations remain temporarily in the bounded processing buffer until they can be safely discarded. Cleanup retries after a temporary connection failure. Transcript content is never stored in localStorage, IndexedDB or automatically written to disk. Browser storage contains preferences only. Explicitly generated synthetic test reports are separate development artifacts.

List view can inspect the remaining active buffer; rolled-over content is not a scrollback archive. A browser refresh cannot reconstruct discarded completed text. Language and view changes do not create an archive.

## Validation

- 26 Python tests passed, including full-page discard, queued-work removal, revision protection, same-origin enforcement and partial-paragraph prefix deletion.
- Four Node tests passed for page fitting, word boundaries, Unicode surrogate pairs and Hebrew combining marks.
- In a browser test with six synthetic paragraphs, automatic rollover removed the first five from the server snapshot, leaving only the last page.
- A synthetic long paragraph started with 788 source characters. After rolling over multiple pages, the server retained zero source/English/Hebrew characters and only the final 19 Russian characters still on screen. Refreshing showed only that remaining tail.

Run `python scripts/rollover-demo.py` or add `--long` for the model-free visual fixture on port 8091. These fixtures contain no live microphone content.

## Fixed-slot overwrite option

Choose **Slots** beside Clean and List. Clean uses the same count; reveal Controls to change it. Select 1–10 fixed slots per column (default 6). New utterances overwrite top to bottom, then return to the first slot. All languages share the same slot assignment. Draft refinements and delayed translations update that same slot without moving its neighbours. Text shrinks within its rectangle; exceptionally long text has an ellipsis and the full text in a hover tooltip. Fewer slots provide more reading space.

Slots has no scrolling, sliding or ink animation. Overwritten completed paragraphs are discarded through the existing revision-checked cleanup; active refinement is cleaned up when it finishes. Slot count and view are preferences, with no transcript persistence.


The slot cursor is global: each utterance reserves the same numbered row in Spoken and every translation column, including pending or missing translations. Only a new utterance advances it. Flipping rotates each cell and its header in place, preserving the shared visual row order.

## Pending work is visible in the row

During capture, the next FIFO row displays **Listening…** across columns. Before transcription exists it changes to **Transcribing…**, **Refining speech…**, or **Checking Hebrew…** according to the real processing stage. This is a temporary overlay; it does not advance the FIFO cursor or delete the row underneath. The arriving utterance occupies that same row. If a refinement belongs to an existing utterance, its cue stays in that utterance's row instead. Translation cells show **Translation queued…** or **Translating…** for the actual active utterance and target. Quiet idle does not show a fake processing cue.

The current UI renders this stage information as a single ink-flower graphic in the shared row, rather than repeating labels across columns. It changes only with actual stage boundaries. The reMarkable API carries the same content-free pending activity, with a global display index; unchanged activity does not redraw cells. Grid lines are hidden, and the large illustrated language control stays available in Clean and the controls view.
