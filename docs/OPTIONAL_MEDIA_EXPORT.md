# Optional media and original-quality export

Media stays in the upload library. Flat video has an explicit role: Camera
(synchronization required), Insert (optional, no sync), or Asset / logo (excluded
from the montage). No filename heuristic decides that a logo is a camera or that
a silent clip belongs to a performance. Unknown or unmatched camera audio remains
excluded by the existing preparation policy; people can explicitly select an insert.

Native recipes receive the original identity from the completed upload metadata,
including video proxies without an audio restoration step. Reimporting the same
bytes at a new server path no longer requires guessing from `.small.mp4` names.
Companion checks remembered files again and can reuse a registered renamed file
only when size and the SHA-256 of its first/last 64 KiB match. This existing bounded
identity is not a full-file cryptographic digest; it does not detect middle-only
changes of equal-size files. Legacy video proxies can recover their association from a newly uploaded, byte-identical
proxy with exactly one original identity. Migration compares complete proxy bytes,
not filenames or visual similarity, and refuses ambiguous matches. This bounded
lookup covers proxies up to 512 MiB and upload libraries up to 5,000 records; larger
or ambiguous legacy records need a fresh source association.

The engine proposes a deterministic fallback for an optional insert only when a
current completed sync stage proves coverage for the entire slot. It uses an
already selected flat camera and its saved base framing (holding automatic Ken Burns still only in the fallback slot), rejects uncertain/unstable/silent/error
sync, refuses piecewise offset corrections rather than flattening them to one offset,
and preserves the master start, duration, and 1x synchronized camera timing.
No safe fallback means a named shot-level reconnection diagnostic. Required camera
shots are never silently omitted. Spherical or unsupported manually moving views are deliberately not inferred.
Server exports apply the same policy to missing optional uploads, ignore unused
library media when checking required sources, and save a separate effective recipe
next to each export. The authored edit stays intact, and Result displays warnings. No proxy is downloaded as an original.

The final recipe retains omission decisions and source keys in the render manifest.
Completed jobs retain diagnostics across Companion restarts, and the result displays
an omission warning. The source plan is not mutated, nor is the master shortened.
Original size/edge identity is checked before queuing and again before rendering.

Companion 0.6.8 and the exact engine commit pinned by Montara are required for the
complete workflow. No installer was run against an existing user installation.

Validation must include the native omission integration test (Node policy ->
Companion job -> actual FFmpeg output), stream duration, audio alignment across the
insert boundary, persisted diagnostics, original native-detail regression, upload
identity and stale-cache reconnection. Linux full journeys and screenshot review
remain the release gate; focused tests alone do not certify production readiness.
