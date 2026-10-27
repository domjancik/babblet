# Conversation interaction

People speak into live microphones and read selected-language translations in paragraph slots. Audio fixtures are development inputs, not the primary product workflow.

## Reading

The optional **Spoken** column contains the recognized original speech, with its detected-language label. Every named output column is translated toward that language, even when its name matches the recognizer's source label. English therefore always remains an English translation target.

**Clean** and **Slots** use the same global FIFO ring: with A/B/C visible, D replaces A, then E replaces B. A translation arriving later updates its utterance's existing row; it does not advance a separate language cursor. The newest row has a small ink dot. The occupied row to be replaced next fades to 45% opacity. A single-slot view stays fully readable. List shows processing details for the remaining in-memory buffer.

The browser's ink effect reveals a readable phrase with a slight opacity change, without word-by-word movement. Facing layouts use an even quieter effect. Reduced-motion preferences disable it. The reMarkable uses static updates only.

## Facing readers

**Readers** cycles through opposite columns, stacked panels, four panels and normal columns. Every panel can choose a displayed language and turn independently, including its flag and language controls. Two readers may show the same language with different orientations. Dividers and spacing separate reader surfaces without adding row grid lines.

The browser saves display preferences locally; the tablet retains its current layout for the open app session. Rotating a whole reader panel changes its physical reading direction, while preserving logical FIFO row assignments.

## Language selection and activity

The large language seal opens the full-screen flag picker. Changes apply immediately; Close returns to reading. Up to six outputs are translated. All 38 native labels have bundled font coverage on the tablet, and its picker fits every choice without scrolling. Search matches English/native names and language codes.

Expected speech follows the display set by default, with an opt-out for independent hints. Hints guide detection, not a strict language whitelist. The microphone meter shows pickup independently of decoding. One ink-flower graphic indicates pending speech/refinement/translation instead of repeating messages across columns.

## Refinement and retention

The segmenter collects limited chunks and re-decodes joined original audio at a pause. A nearby continuation can reopen the prior paragraph within bounded time/audio limits. The Hebrew specialist can replace the primary result; every translation is then rescheduled from the selected source and stale revisions are rejected. This is acoustic refinement rather than an LLM rewrite or speaker diarization.

Overwritten completed content is discarded rather than archived. The bounded pipeline can briefly retain pending work, and the tablet keeps six presentation rows independently of browser cleanup. Recordings exist only when local debug capture is explicitly enabled. See [refinement](REFINEMENT.md), [speech guidance](SPEECH_LANGUAGES.md), [recording](DEBUG_AUDIO.md) and [tablet installation](../remarkable/INSTALL.md).
