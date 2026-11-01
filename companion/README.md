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

## Not yet
- WAV/AIFF tracks (16/24/32-bit integer) are sent as lossless FLAC (`name.wav.flac`), usually
  30–60 % of the size. The server turns each back into the identical WAV, BWF time reference
  included, before the mixer reads it. 32-bit float WAVs go as WavPack (FLAC has no float), also lossless.
- With *Full session · audio* ticked, tracks go as light Opus previews instead; at export only the
  song ranges of the originals are sent (FLAC or WavPack).
- The final video is made on the server from the small versions (720p source).
- Rendering the originals on this computer is the next step. It needs the engine to relink
  a project from small versions to originals (`docs/lab/INVENTORY-FER.md`, F8 FOCUS_A_C).

## Requirements
- Python 3.9 or newer. On a Mac: `xcode-select --install`.
- FFmpeg. On a Mac: `brew install ffmpeg`.
- Chrome or Edge. Chrome may ask once whether the page may reach devices on your local network: allow it.

It listens on `127.0.0.1:47820` only. Small versions are cached in `~/.montara-companion/proxies`.
