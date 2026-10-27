# Import runtime check — 27 October 2026

The deployed template contained yt-dlp 2026.10.21, no yt-dlp-ejs, no Deno, and Node at /usr/local/bin/node. Embedded YoutubeDL enabled only the absent Deno by default. The downloader logged that no supported JavaScript runtime was found.

The private preview now provisions tested versions yt-dlp 2026.10.21, yt-dlp-ejs 0.8.0 and Deno 2.5.6. `deploy/download_runtime.py` installs missing components using uv and the official Deno npm package. Boot verifies the executable; `deploy/sandbox_entry.py` adds its directory to PATH in each Flask worker, including reloads. This applies to engine Show, Push and reference imports without editing submodules. Existing user projects and media are not changed. Startup fails visibly if provisioning fails. Local Linux installs use the default yt-dlp dependency group; local users must also install a supported JavaScript runtime.

## Real server comparison

An isolated, disposable Vercel sandbox was created from the same snapshot as production. No user browser cookies, proxy services or PO-token providers were introduced. No included media or source cache was used in these download calls.

| Test | Result |
|---|---|
| Original installation, TfuHvz7pd24 | Failed: missing JS runtime warning, followed by YouTube LOGIN_REQUIRED / not-a-bot message |
| EJS installed and existing Node explicitly enabled, same URL | Missing-runtime warning gone; YouTube still returned LOGIN_REQUIRED |
| EJS + Deno on PATH, same URL | Missing-runtime warning gone; YouTube still returned LOGIN_REQUIRED |
| EJS + Deno, bfGH-664RQ4 fetched directly | Deno version and EJS installation verified; YouTube still returned LOGIN_REQUIRED |

The missing dependencies are a confirmed installation defect. They are not a complete explanation of the remaining remote access refusal. The precise additional factor is not established. Do not claim that the fix makes arbitrary YouTube links work, that OAuth solves CAPTCHA, or that a successful cached example proves fresh remote downloads.

The Editor code's `browser_setting()` reads cookies from a browser on the machine running the downloader. That explains a relevant local/server distinction; it cannot read a remote visitor's browser session. The inspected Editor code is not a CAPTCHA-solving service.

## Validation

- 79 Python regression tests passed locally.
- 6 JavaScript preview lifecycle tests passed locally, including failure to provision the import runtime and preserving busy workers.
- Real Linux download comparisons above failed at YouTube's access check; a successful import/export is not claimed.
- Full Linux Push and mix journeys passed in GitHub run 40492124936 (code commit 713b5ba). Artifact upload hit GitHub storage quota; the upload step is non-blocking.
- The Stage job in that run stalled at installing FFmpeg, before running Montara. The same Stage journey was instead run in the isolated Vercel Linux worker using Playwright 1.64.1, Chromium and explicit browser OS dependencies. It passed: 100.2 s, 1920×1080, real three-camera fixture, swap exercised, 17 cuts. Camera, frame-selection, result and exported-frame screenshots were saved locally for inspection. The redundant blocked GitHub run was cancelled after this fallback completed; do not describe all three GitHub jobs as passed.
- The staged production deployment was exercised through the private grant, the actual Flask entry and an HTTP Push request. Flask resolves the provisioned Deno executable and EJS. The fresh HTTP Push import still fails at YouTube's access check, consistent with direct tests.
- The existing public alias `https://montara-tau.vercel.app/` was assigned to the tested build `montara-2fznt0j51-amehcgracia-2381s-projects.vercel.app` after validation. No new public address is required.

Sources: https://github.com/yt-dlp/yt-dlp/wiki/EJS and https://github.com/yt-dlp/yt-dlp/wiki/Extractors .
