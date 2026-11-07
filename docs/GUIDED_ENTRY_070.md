# Montara 0.70 — guided tasks, standalone mastering and source roles

## Entry
After the Montara animation, ask Music or Video. Music offers Mix a song, Mix a full session, and Master a mix. Video leads to Stage (music video), Push (vertical reels) and Show (creator/story/podcast). Descriptions stay visible on desktop and mobile. Browser Back/Forward traverses the questions.

Music opens only the audio box and describes the required inputs. The session choice retains song detection, per-song mixers and exports. The one-song choice does not silently switch to full-session detection. Stage loads its finished-master example by default, keeping the Video path focused on video. Existing camera-plus-stems automatic mastering remains available through the explicit separate-track example for compatibility; it is a separate flow from standalone mastering.

Master a mix accepts exactly one full-quality finished mix. It uses FFmpeg two-pass loudness processing (-15 LUFS target, -1.5 dBTP processing target), without invoking the stem mixer, instrument EQ, panning or FX. Encode at 320 kbit/s MP3; measure the decoded result, lower the gain and re-encode from the intermediate float WAV if needed. Release only if the final measured true peak is <= -1 dBTP. Display measured input/output LUFS and final dBTP. This does not reconstruct distortion already present in the source or promise identical loudness when the peak constraint limits gain.

Cancellation terminates the active FFmpeg process. Temporary float WAV is removed on every outcome. Final outcomes survive restart; interrupted in-memory jobs become failed/retry. Master outputs participate in existing retention, preserving the newest and live work. Companion 0.6.7 must be installed with the new pinned Engine before original-quality local video export; the mixer pin is unchanged. No public accounts or billing changes.

## Stage cameras and filler
Each flat video can be Camera or Filler (no sync). Silent flat footage discovered during preparation becomes explicit B-roll and retains the song audio. Engine support is implemented in owner repository ZuckerVideos PR #61, commit 25a89485, not patched inside Montara.

User-selected B-roll bypasses semantic scene screening; it is not claimed to match the performance. Bounded windows avoid a full-file scene scan. Short cutaways may appear between covered camera shots, with opening/ending and at least 90% performance footage retained; existing screened gap-fillers keep their behavior. Spherical footage is not automatically treated as flat B-roll.

Stage checks real sync artifacts before starting the edit/export. A high peak confidence does not override instability. For questionable/nonoverlapping cameras, show a source review: leave this video out of this song, explicitly choose flat B-roll, or return to Footage. Uploads remain intact. No guessed offsets or weakened export coverage guard. The approved project registers only sources selected for that song plus fillers.

## Real incident, measured separately from synthetic acceptance
Read-only saved artifacts in 0.69 showed two different masters: 480.731429 s from session range 595.4–1076.1 s, and 705.541224 s from range 2410.1–3115.6 s. The phone matched the former (offset +226.115918 s, three checks agree), whereas the 360 matched the latter (offset -24.868571 s, three checks agree). The other combinations were unstable (82.082540 s and 618.556372 s disagreement). Those numbers describe disagreement between sync candidates, not a measured physical camera clock drift. A separate silent clip had no audio in its original.

No original media, credentials, full private paths or raw production logs are published. Production project/source selection was not modified during diagnosis.

## Validation status
- Engine focused tests: 117 passed locally, including API validation, no-inference B-roll, timeline coverage and existing sync/guard behavior.
- Mastering: four real FFmpeg tests passed (stereo ratio/duration, final MP3 peak/loudness, metadata, cancellation, silent-input and remote-path rejection).
- JS source-selection policy and existing session-window policies pass.
- Local synthetic Stage journey passed, including export, frame editing and restoration.
- Local guided-audio journey passed: questions, browser Back/Forward, real audio playback/download and restoring the master after reload. Local silent-filler journey passed through video export (one silent cutaway and one matching camera, unrelated camera explicitly left out). Screenshots reviewed. Complete Linux journeys remain required before installation; this document does not certify them in advance.
