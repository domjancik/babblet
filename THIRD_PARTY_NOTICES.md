# Third-party components

Babblet application code is licensed under MIT. Third-party assets, dependencies,
models and device extensions retain their own licenses.

- **Noto fonts:** SIL Open Font License 1.1. The font files, complete license
  notices, source URLs and download hashes are in [remarkable/fonts](remarkable/fonts).
  This includes the shared Noto Sans CJK collection and Tibetan serif font.
- **flag-icons:** MIT, copyright lipis. The bundled flags retain the upstream
  [license notice](babblet/static/flags/LICENSE.txt).
- **PySide6 / Qt:** installed separately; LGPLv3/GPLv3/commercial terms apply.
  See [Qt for Python licensing](https://doc.qt.io/qtforpython-6/licenses.html).
- **faster-whisper / CTranslate2 / llama.cpp / PyTorch:** installed or downloaded
  separately, with their respective upstream licenses and notices. Runtime and
  model downloads are not part of the Git repository.
- **Hy-MT2:** the official [Tencent model card](https://huggingface.co/tencent/Hy-MT2-1.8B-GGUF)
  identifies the model license. Quantized weights are downloaded separately.
- **Whisper Turbo and ivrit.ai Hebrew:** downloaded separately from their model
  repositories; consult the model cards and included licenses before redistribution.
- **NLLB-200:** optional benchmarking only, not the live default. Its
  [model card](https://huggingface.co/facebook/nllb-200-distilled-600M)
  specifies CC-BY-NC-4.0 and research-use limitations.
- **XOVI, AppLoad and qt-resource-rebuilder:** separate reMarkable prerequisites
  downloaded from their upstream releases. No compiled copies are committed here.

The bundled SVG controls are Babblet artwork. Riddle informed the emphasis on
changed-region updates; its native rendering code and binaries are not bundled.
