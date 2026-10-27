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
- 5 JavaScript preview lifecycle tests passed locally, including failure to provision the import runtime.
- Real Linux download comparisons above failed at YouTube's access check; a successful import/export is not claimed.
- Full Linux E2E and public deployment status must be recorded separately after they finish.

Sources: https://github.com/yt-dlp/yt-dlp/wiki/EJS and https://github.com/yt-dlp/yt-dlp/wiki/Extractors .
