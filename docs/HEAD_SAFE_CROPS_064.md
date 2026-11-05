# Individual musician crops — 0.64

0.63 capped all automatic crops at 1.8x and aimed at the torso. This could show
two players and cut a head when closing the shot.

## Change

The fixed-camera analysis retains body and head regions across its five cached
samples. Faces provide head evidence when available; otherwise an explicitly
approximate upper-body estimate extends above the detected body. The union
protects sampled head movement. Recognition still uses only small proxy images.

Crop geometry now considers neighboring body regions, keeps the head inside
both the outer crop and the tightest state of the existing 6% motion, and leaves
headroom. Normalized crop coordinates match the actual flat filter geometry,
including edge clamping. Adjacent people are excluded where the geometry allows;
head preservation takes precedence when silhouettes overlap or the original
already cuts a person. This is not segmentation or a guarantee of perfect face
localization in dark/occluded footage.

Deep flat crops up to 6x are accepted consistently by the engine, shared camera
editor and Companion 0.6.3. Native original relinking is preserved. Other motion
recipes retain their previous 3x validation bound. Zoom cannot recover detail
absent in the original source. No manual light tool is reintroduced; automatic
camera light matching remains enabled.

Performer detector version and Stage planning version are bumped. Existing
manual edits and custom remembered musician regions are preserved. Generate a
new edit for the new automatic analysis; an update does not rewrite finished
projects.

## Validation

Local engine: 63 focused tests passed, including head containment during motion,
neighbor exclusion at source edges, overlapping silhouettes and actual decoded
pixels for all 30 frames of a rendered close-up. The native recipe accepts a
5.4x flat crop and rejects out-of-bound crops and oversized motion recipes.
Linux native Stage acceptance now exports a 3.4x crop to exercise the whole path.

A private real dark-stage contact sheet was inspected locally; no source media
was committed. Production installation and Linux acceptance pending.
