# Compact editor 0.34

Video Cuts and FX share the playhead and transport. Optional music has its own row. Redundant Original Voice and video controls are removed. FX + adds effects; the bottom + offers effect, music or video. Right-click the picture to remove effects. Captions and history remain separate.

Splits and deletions update optimistically, then save through one lightweight response without media probes. Durable undo and redo preserve original media. Preview regeneration is debounced 750 ms and runs only for the current part, without blocking timeline editing. Pure splits do not require another render. Complex effects still need processing time.

Local browser checks: split feedback 7.1 ms / save 52.3 ms; delete feedback 16.7 ms / save 31.8 ms. These are local measurements, not public latency guarantees. Split, delete, undo, redo and automatic preview were verified. 16 backend tests cover editing, ripple timing, framing and music.

Podcast/Story retain their programme picture track without the redundant narrator track. Shared media dialogs and Push gain compact playback controls. Source cut/delete remains supported for Gamer and Influencer.
