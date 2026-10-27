# reMarkable 2 frontend research

Researched 2026-10-27. Scope: the tablet displays Babblet and sends UI choices. Microphones, speech recognition, refinement, translation and model storage remain on the computer. No device software has been installed or tested by this investigation.

## Recommended authoring route

Use a native C++/QML Qt Quick client, cross-compiled with the official **rm2 SDK matching the tablet firmware**. The current official example uses Qt 6 and CMake, supports Qt Quick rather than Qt Widgets, and launches through the epaper backend. Touch is supported; pen handling requires additional work. Its reMarkable 2 launch example includes a touch-coordinate correction and temporarily stops Xochitl before restoring it. Firmware 3.17 has a documented scenegraph plugin caveat. These are deployment details to verify against the actual tablet, not commands to execute blindly. [Official Qt Quick guide](https://developer.remarkable.com/documentation/qt_epaper)

The SDK needs a Linux build environment. For this Windows workstation, an appropriate Linux VM or WSL2 environment is a candidate to validate. The SDK product name is rm2, and its internal OS version differs from the user-facing software version. Consult the release mapping before downloading. The SDK overview's x86-only statement is outdated relative to the current download table, which lists both x86_64 and aarch64 hosts for newer releases. [SDK overview](https://developer.remarkable.com/documentation/sdk), [download and firmware mapping](https://developer.remarkable.com/links)

The Paper Pro developer-mode/factory-reset procedure does not apply to reMarkable 2. [Official developer-mode documentation](https://developer.remarkable.com/documentation/developer-mode)

## Alternatives considered

| Route | Assessment for Babblet |
| --- | --- |
| Official Qt Quick + matching rm2 SDK | First choice for a standalone frontend; validate the actual firmware and available Qt modules first. |
| AppLoad / XOVI | Possible later integration into the tablet UI, with fullscreen or windowed apps; introduces another firmware-dependent layer. [Project](https://github.com/asivery/rm-appload) |
| Legacy Qt 5 / Toltec / rm2fb | Useful historical examples, but do not mix their platform plugins or libraries with the official Qt 6 route. The older template bundles epaper integration and uses qmake. Toltec's site restricts supported firmware and recommends newer tooling for recent OS versions; its repository is archived. [Qt 5 template](https://github.com/Eeems-Org/remarkable-template-qt-app), [Toltec](https://toltec-dev.org/), [repository status](https://github.com/toltec-dev/toltec) |

## Proposed Babblet architecture

This section is an implementation proposal based on the existing local code, not a claim that the tablet client already exists.

```text
Computer: mic -> ASR -> speech-end refinement -> translation -> display state
                                                           |
                                                USB/SSH tunnel initially
                                                           |
Tablet: C++ network/model adapter -> QML fixed slots + flag selection
```

- Start with Qt Network HTTP polling through QNetworkAccessManager, rather than requiring a new streaming protocol. This API supports asynchronous requests and replies. Check Qt Network availability in the matching SDK. [Qt Network documentation](https://doc.qt.io/qt-6/qnetworkaccessmanager.html)
- Read existing `/api/snapshot` and language catalogs; send settings through `/api/languages` and `/api/speech-languages`. The existing server enforces loopback hosts and same-origin mutations, so a native client must send the matching Origin header on POSTs.
- Keep the computer service bound to loopback. A proposed USB connection uses a reverse SSH forward from the computer to a tablet-local loopback port; the tablet then connects locally while the computer's API stays unexposed to the LAN. Validate SSH forwarding support on the actual device before adopting this. Do not change network binding or firewall rules as part of research.
- Make display slot assignment authoritative on the computer before adding another simultaneous frontend. At present the slot ring lives in browser memory. Export a presentation session with a global slot counter, slot generation, utterance ID and revision; all language results address that row. Old responses must never populate a reused slot.
- Define one presentation session's ownership of `/api/rollover`: two independent clients must not discard paragraphs that the other has not displayed. Shared computer-owned slots and cleanup solve this more cleanly than independent browser/tablet rings.
- On reconnect, fetch only the current bounded slot snapshot, with a session identifier to reject an old session's responses. Persist preferences only; no transcript log on the tablet.
- Render QML text natively with tested Hebrew/Arabic shaping, bidirectional text and suitable fonts. Keep logical row positions fixed when flipping individual cells.
- For e-ink, start with whole-paragraph updates and static activity labels. Disable handwriting reveals, animated spinners and high-frequency microphone animations. Coalesce drafts; tune redraw cadence and ghosting on hardware rather than promising a refresh rate.
- Use a desktop build of the same QML UI and synthetic API fixtures before cross-compiling. This tests layout and protocol; only the physical tablet can validate display updates and touch mapping.

## First device validation

1. Identify the installed software version and matching rm2 SDK; inspect SDK Qt modules.
2. Build the official minimal Qt Quick example in Linux and verify touch/display on the device with a clear way back to Xochitl.
3. Verify the loopback tunnel and a read-only Babblet snapshot.
4. Add native fixed slots, multilingual fonts and immediate flag toggles; test delayed translations, revisions, reconnect and rollover ownership.
5. Measure readability, redraw ghosting, latency and battery impact on-device; choose a launcher only after the standalone app works.

User-reported tablet software version: `3.028.0171` (recorded verbatim; confirm the exact version string before selecting an SDK). Device access and SDK compatibility remain to be validated. No firmware changes, launcher installation, service stopping or SDK installation were performed.
