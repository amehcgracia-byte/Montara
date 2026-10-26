# Shared source import 0.36

Observed source of the apparent Push/Show difference: Push has an included original for youtube:bfGH-664RQ4 (All Minds). Its download method returns that source before contacting YouTube. This is genuine editable source, not a finished reel, but it does not prove fresh YouTube downloading works.

Push and Show now consult the same source resolver. It checks the explicitly included original catalogue and then ready Push packs from the current isolated workspace. It validates resolved paths and does not inspect other users' workspaces. Show extracts only the requested interval into the current project and reuses it on the next request. The engine source remains unmodified; the Montara adapter wraps the download entry point in the current application context.

New URLs still fall through to the real internet downloader and remain subject to the source site's access checks. No OAuth, CAPTCHA solver, remote cookies, proxies or paid services have been enabled. The fix is source reuse, not a claim that arbitrary YouTube links work.

Validation covers equivalent YouTube URL forms, cross-workspace/path escape rejection, completed Push source reuse, no network request on a cache hit, actual three-second MP4 extraction and the origin returned to the UI.
