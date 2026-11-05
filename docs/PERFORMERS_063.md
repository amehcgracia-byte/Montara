# Fixed-camera musicians — 0.63 candidate

This completes the missing connection between Stage and automatic person crops;
0.62 only animated manually authored crops.

## Implemented

- Stage enables performer rotation through the engine HTTP API before planning.
- Fixed cameras only: five small proxy stills in the first twenty seconds of the
  selected song, cached by source revision, source offset, song window and detector version.
  An independent MobileNet network avoids concurrent singleton inference; missing
  models/detections preserve the general. Callback cancellation propagates.
- Dark detector input is lifted for recognition only. Automatic exported camera
  light matching is preserved; the manual light editor stays removed.
- Persistent people are ordered left to right. General every fourth fixed take,
  balanced changing individual order, no immediate repeated close-up. Crops are
  capped at 1.8x and keep the existing 0.62 gentle opening/closing motion.
- Crops are assigned before `shot_ready`: thumbnails, previews, native recipe and
  server export use the same geometry, without a second full-video analysis.
- In Edit, assign instruments to numbered musicians. A missed musician can be
  remembered from the current crop. Role/region corrections persist by source;
  auto takes update, while already manual crops, timing and light are preserved.
- The one-song mixer publishes its existing one-second RMS analysis. Muted and
  inactive tracks remain explicitly silent evidence. Stage receives bounded finite metadata, tied to
  that exact mix master. No extra audio decode or model download.
- Known silent instruments are excluded; relative stem prominence biases takes
  without starving the others. Missing/out-of-window evidence remains unknown.
  Generic `horn` / Demucs `other` are never labelled saxophone.

## Explicit limits

Person detection does not identify an instrument. Confirm the role once; dark,
occluded or small people can be missed and a spectator can be mistaken for a
performer. This is a stationary camera profile, not tracking a moving musician.

With a master alone, useful visual rotation is enabled, but reliable instrument
identification and solo recognition have not been implemented. RMS prominence
from separate tracks is an editorial hint, not musical solo recognition; bleed
and sustained accompaniment can fool it. Full-session exports subsequently
reimported as MP3 do not carry the stems' evidence. A future validated audio/vision
model or confirmed timed annotations are needed for those cases. No paid AI
provider is silently enabled and no LLM access is assumed.

Existing reviewed projects are not rewritten on update: create a new edit to
obtain automatic crops. A source explicitly marked Moving remains moving.

## Validation

Pending final Linux journeys and installation. Local directed engine tests:
59 passed (performer policy/API, crop/filter parity, automatic light, previews
and hardware-decode guards). Local adapter/browser/FX: 7 passed.

A private real 20-second dark stage excerpt was tested locally, without uploading
media. Detection and crop contact sheet were inspected. The intentionally
pixelated repository fixture is not an adequate quality benchmark for recognition.

Pinned engine: `0fc0ceb40661acb622014fa75aba321483af1ae2`; prior `a13dc640` remains an ancestor. Swapping cameras clears the previous source’s performer coordinates.
