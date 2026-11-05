# Camera colour measurements — 0.65

## Reproduced defect

The latest privately inspected native Stage export used verified original files,
not server proxies: both inputs were 1920×1080, one 10-bit HEVC and the other
8-bit full-range H.264. Final output was 1920×1080 H.264 at approximately
18.24 Mb/s. No private media or source paths are included here.

The camera matcher measured `signalstats` in the native pixel depth. This
compared 10-bit code values (neutral chroma around 512) with 8-bit code values
(neutral chroma around 128). The real saved artifact showed the resulting
incorrect, maximum-clamped chroma adjustment on the other camera.

Engine colour profile v8 converts only the small analysis frames to a common
8-bit limited-range YUV domain before measurement. Original render inputs are
unchanged. Old measurements are invalidated. Light recipe v2 bounds automatic
shadow recovery in predominantly dark stage views; automatic light matching
remains available and the manual light editor stays removed.

## Performer and resolution findings

The current detector finds three people in the privately inspected fixed-camera
source, including the seated player on the right. All three roles are unknown.
Detection of a person is not recognition of their instrument. Existing shot
editing can assign roles or remember a missed musician's crop. Separate-track
activity can guide confirmed roles; reliable solo recognition from a mixed master
and automatic visual instrument classification remain unimplemented.

Seating, lines or circles are insufficient on their own to label an instrument:
stage decoration and unrelated equipment can produce the same patterns. No
hard-coded right-hand pianist or false semantic recognition is introduced.

A 5× crop of 1920×1080 contains only about 384×216 source pixels before
upscaling. Better colour matching cannot recreate missing detail, undo arbitrary
baked-in camera processing or guarantee pixel-identical output after cropping
and re-encoding. The native source-linking and 6× user controls remain intact.

## Validation

- Local engine: 50 tests passed across colour calibration, automatic light,
  performers and flat framing. A decoded FFV1 8/10-bit regression verifies
  matching luma/chroma and neutral correction for equivalent pictures.
- Privately inspected original / previous / corrected comparison frames from
  the actual fixed source. Media and diagnostics remain outside Git.
- Linux acceptance `42001327109`: Stage, Push, Mix, session/native Stage and
  private-container all passed. Stage frames, native framing and result screenshots
  inspected. Full local Montara suite: 234 passed.
- Engine run `42001227390`: Fast 1,338 passed / the same 22 historical failures
  as 0.64 (failure names compared); Slow passed. No whole-engine green claim.
- Installed JM main `e8a8c83`, engine `6283d87e84342f2b14633248ac45d34ca89e196e`,
  mixer `f15ff91` unchanged. Mac Companion 0.6.4 uses that same engine.
  Both installations verified; FER untouched. PRs Montara #77 and Editor #57.

## Additional private feasibility checks

A three-frame, three-person CLIP probe ran in 2.79 seconds on the existing Mac
using the engine's existing quantized vision/text models (pinned files verified
by the existing fetch helper). It ranked pianist first for the seated musician
in all three frames, but misclassified the bassist in one. This is an experiment,
not a deployed recognizer; no new model/dependency was installed in JM or the
Companion. Local ignored model files and private probe outputs remain outside Git.

One second of the actual fixed-camera source, with identical 3.575x framing,
light and motion, was encoded at 18 and 40 Mb/s with VideoToolbox and compared
against a lossless reference of that same processed picture. SSIM was 0.982381
and 0.983392 respectively (this is not comparison against an uncropped source).
The sample is too small to certify whole-video quality. Doubling the default
bitrate was not adopted for this marginal improvement. Software CRF18 in the
same experiment measured 0.981865; encoding time observations include creating
that lossless reference and are not full-render benchmarks.
