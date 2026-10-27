# Original speech and fixed-language outputs

Spoken is a dedicated, always-visible column containing `source_text`, the original ASR transcription. Each paragraph shows its detected language and uses automatic text direction. It is not counted as one of the selected translation outputs.

Every selected output now runs through the translation model with that target language, even when it matches `source_language`. This closes the case where an ASR label incorrectly says English while the decoded words are French or another language: raw words remain in Spoken, and the English column receives an English translation request. If translation fails, its output shows the normal pending/error state rather than silently substituting raw source text.

Clean and List views both show Spoken. Original paragraphs align with their translations. Its raw text has independent page offsets and prefix-deletion receipts, so rollover never derives the original transcript from a translation or restores discarded text. The layout supports Spoken plus up to six selected output languages.

## Validation

- 34 Python regression tests and five Node pagination/column tests passed.
- A live local Hy-MT2 test produced English outputs for French, Hebrew, Russian and English input, including French deliberately labeled as English. Original text was preserved separately in all five cases.
- The synthetic preview showed French/Hebrew/Russian/English original text in Spoken and English in every corresponding English paragraph. The retained smoke report contains only synthetic test sentences: [spoken-column-smoke-test.json](benchmark/spoken-column-smoke-test.json).

ASR language labels and transcription can still be inaccurate. This change separates their outputs from the explicitly requested translation language; it does not introduce a second language classifier or claim perfect translation accuracy.
