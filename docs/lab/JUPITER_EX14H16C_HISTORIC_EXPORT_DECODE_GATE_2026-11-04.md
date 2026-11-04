# EX-14H-16C — Historical Stage export integrity gate

Date: 2026-11-04. Read-only media validation from FER lab.

Historic fixture project: `/home/fer/montara-e2e-01/data-stage/Projects/E2E stage.zuckervid`. Video: `exports/E2E stage-youtube-20261030-132858-389424624.mp4` (40.2 s, H.264 1920x1080, AAC, 43.11 MiB; confirmed by EX-14H-16B).

EX-14H-16C ran full `ffmpeg -v error -xerror -i <file> -map 0:v:0 -map 0:a:0 -f null -` and returned `DECODE_COMPLETO_OK` (successfully decoded both streams). Audio `volumedetect` emitted a filter instance with `n_samples: 0` but another with **1,930,240 samples**, `mean_volume: -31.8 dB` and `max_volume: -14.4 dB`: the file has non-silent audio, no decoder error. At this point disk `df -h` reported 96G total, 59G used, 38G available, 61% usage.

**PASS limited to file decodability and audio presence.** This is a historical 20-second 2-camera synthetic fixture plus intro/outro, not real original iPhone+360 full end-to-end. Does not validate subjective audio quality, synchrony of exported edits, absence of glitches or choice of real cameras. All five copied `montara-focus-*` project.json files contain historical shared stage outputs and times, not five independent E2E runs.

Next: return to roadmap with isolated *new* original-sourced Stage E2E bounded run, no modifications to Chema production, verify per-stage artifacts, audio, segment selection, resource limits and cleanup, then Companion/GOP/architecture. No new code modified by this record.
