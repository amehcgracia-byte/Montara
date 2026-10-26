# Music shelf and the Push example master

Show now has Music in the review and right-click menu. The compact shelf offers two small bundled CC0 tracks, uploads, audition, a source start point, placement, gain and ducking under narration. Every placed track is snapshotted into the current project's music assets through the existing HTTP music API. It is a normal jingle/audio effect: timing, trim, removal and undo use the existing timeline. Music is rendered only when Preview is requested, matching the editor's manual-preview workflow. The clean cut player remains effect-free until preview.

The first catalogue contains Face The Facts (Zane Little Music) and Our Expanse (Bobjt), with source and licence records. The library exports a music-credits text for tracks used in the project. CC0 does not guarantee that an external automatic Content ID system will never make a claim. User imports are explicitly marked as user supplied.

The public preview overlay now includes the actual Much to Me master, which came from the refined audio mix, plus the two music tracks as binary assets. New/updated previews install these with the UI. The Push sample names the song master visibly, uses it for the reel, and does not allow that bundled example to fall back to camera audio when the master is missing. Generic single-video uploads still support their embedded audio.

No changes were made to the engine/ or mixer/ submodules. All product interactions with the engine use its HTTP API.

Verification: three real media tests in tests/test_music_shelf.py, including import, byte-range playback, project snapshot, stale-project rejection, source offset, gain, timing, deletion and an actual rendered preview whose added music is verified in the audio spectrum. Linux: 28 tests passed across music shelf, Show inputs, reel selection and the existing music/audio regression suites. The existing full Linux e2e_journey.py browser journey has not been run for this update. Browser checks cover selecting, auditioning, placing and editing volume in the existing Show UI.
