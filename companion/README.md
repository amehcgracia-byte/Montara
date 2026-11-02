# Montara companion

A small background helper that runs on the person's own computer, next to their originals.
No window, no wizard: one command in Terminal.

```sh
curl -fsSL https://raw.githubusercontent.com/amehcgracia-byte/Montara/main/companion/install.sh | bash
```

The command installs into `~/.montara-companion`, adds the `montara-companion` command and
starts it. Next time, open Terminal and type `montara-companion`. Ctrl+C stops it.

## What it does (version 0.1)
- When Montara's page receives a video, it asks the companion for it by name, size and the
  SHA-256 of its first and last 64 KiB. Only a page that already holds the file can compute
  these, so the companion cannot be used to browse the disk.
- The companion finds the original: Spotlight first on a Mac, then the usual folders and
  external drives.
- It makes a small version with FFmpeg: at most 1280×720 (landscape) or 608×1080 (portrait),
  H.264, constant frame rate, SDR, with camera audio as 192 kbps AAC. It uses the Mac's
  hardware encoder when FFmpeg has VideoToolbox, and tone-maps HDR.
- Montara uploads only that small version. The engine uses it as it is, with no conversion
  on the server.
- 360 videos are still uploaded as they are (their projection metadata must survive).

## Audio and final export
- WAV/AIFF tracks (16/24/32-bit integer) are sent as lossless FLAC (`name.wav.flac`), usually
  30–60 % of the size. The server turns each back into the identical WAV, BWF time reference
  included, before the mixer reads it. 32-bit float WAVs go as WavPack (FLAC has no float), also lossless.
- With *Full session · audio* ticked, tracks go as light Opus previews instead; at export only the
  song ranges of the originals are sent (FLAC or WavPack).
- Stage can now export on this computer from the fingerprint-verified original videos. Only the edit recipe and master audio travel back; original camera files stay on the disk. The same pinned Editor renders the light correction, reframing, camera changes and audio timing.
- Install/update the video runtime once: `curl -fsSL https://raw.githubusercontent.com/amehcgracia-byte/Montara/main/companion/install.sh | bash -s -- --video`. It uses Python 3.10–3.12, NumPy/SciPy/OpenCV/Pillow and FFmpeg; no LLM or speech-model installation. The installer also works with the existing optional local mixer.
- Final Stage output is 1080p; a 720p editing copy is never silently offered as the original-quality final file when the companion created that copy. The result is saved in the chosen project folder and can be watched/downloaded while the companion is running. Disconnecting the original drive stops export with an error.
- Current native-export scope: Stage, Montara/no branding. Personal logos and native Push/Show export are not wired into this route yet. Projects uploaded directly as originals retain their server export path.

## Requirements
- Python 3.9 or newer. On a Mac: `xcode-select --install`.
- FFmpeg. On a Mac: `brew install ffmpeg`.
- Chrome or Edge. Chrome may ask once whether the page may reach devices on your local network: allow it.

It listens on `127.0.0.1:47820` only. Small versions are cached in `~/.montara-companion/proxies`.
