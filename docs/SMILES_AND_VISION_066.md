# Smiles, preview audio and visual understanding — 0.66

## Implemented

Flat moving and fixed cameras share cached 320-pixel quality samples. Smile
evidence uses the face and lower-mouth detectors shipped with OpenCV, once per
second, requiring persistent evidence in the two-second quality window. It is
a visual smile hint, not an emotion/personality diagnosis. Missing evidence
does not mean an unhappy person. Raw equirectangular 360 footage is not scored
for smiles: undistorted projected views need a separate evaluation.

Smiles add a bounded preference to usable shot selection. Coverage, movement
safety, no consecutive repeated camera, camera-share balancing and explicit
preferred cameras remain. They do not rescue blur or bad exposure. Fixed cameras
need an initial small-sample quality analysis, then reuse its global cache;
there is no separate full-resolution smile decode or extra render per card.
The model's notice is in the engine's docs/licenses/OPENCV_SMILE.txt.

Hover previews now include the correct master-time excerpt as AAC 96 kb/s,
at most three seconds. The existing small preview video is copied during the
audio mux. Camera sound is never substituted. Changing the master file or
master start invalidates the preview cache. Only one card plays, and leaving
it or navigating stops playback. Browsers that block audible autoplay show
"Tap for sound" and allow a user click to enable it.

## Existing recognition models worth testing

These are licensed tools, not public-domain or "without rights" assets. Their
official model repositories declare permissive licenses; keep notices and review
the exact pinned model/code/dependencies when integrating.

| Candidate | Official license | Useful capability | Assessment for Montara |
|---|---|---|---|
| [Microsoft Florence-2-base](https://huggingface.co/microsoft/Florence-2-base) | MIT | Captions, object detection, regions and segmentation; 0.23B parameters | First candidate for a bounded scene/instrument-description experiment on selected small images. Instrument and action accuracy must be measured. |
| [Qwen2.5-VL-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct) | Apache-2.0 for this exact 7B model | Object/scene reasoning, structured positions, temporal video understanding | Candidate for the GPU server. No latency/RAM/cost measurements have been made on our hardware. Do not assume every Qwen size has the same license. |
| [OpenCV smile cascade](https://github.com/opencv/opencv/blob/4.x/data/haarcascades/haarcascade_smile.xml) | Model's own BSD-style notice, distinct from the library's Apache-2.0 license | Lightweight face/lower-mouth appearance evidence | Used here; does not explain activities or identify an instrument. |

A detector locates people/objects; a pose model locates body joints; a visual
language model can describe relationships and apparent actions. No single list
of geometric rules reliably covers musicians, kitchens, computers and rooms.
A still image cannot establish who is audibly soloing: that also needs aligned
audio evidence. The previous CLIP experiment remains separate, not a deployed
instrument recognizer. Florence/Qwen are research candidates, not installed
engines or promised commercial performance. Self-hosting avoids a per-token
provider fee but still consumes compute.

## Validation

95 local engine quality, preview, speed and edit tests passed, including decoded
two-tone audio alignment and preview cache identity. Linux browser acceptance
and installation pending. No user project or source media was committed.
