# MONTARA I28 — First owner-scoped editor workspace

Date 2026-11-10. Scope: a **working project recipe/editor planning workspace** in the private Google Owner beta, not an arbitrary proxy to the single-user classic Engine.

## What changed
- New authenticated `/urano/v1/workspace?project=<UUID>` page, accessible only to the logged-in owner of that project. Separate same-origin `workspace.css` and `workspace.js` also require an active session.
- Dashboard under I27 feature flag shows `Entrar al estudio` beside each project, leaving `Abrir Engine (beta)` and `Cerrar Engine` available.
- Dark Montara study layout with Stage/Push/Show choices, output aspect ratio, editing notes, a list of up to 30 planned montage blocks (adding, removing and editing), clear empty monitor, transport marked as awaiting media, and real isolated Engine open/close controls.
- Edits are saved **durably** through existing Owner `PUT /urano/v1/projects/<UUID>/recipe` with cookie+CSRF+expected_revision. `montara_beta_workspace` is namespaced inside the existing recipe and the rest of the recipe is retained. Concurrency conflicts do not overwrite changes without an explicit reload.
- No upload of original local videos and no direct access to the classic shared Engine API endpoints; owner isolation and the I27 root broker remain intact. No fake playable timeline is presented.

## Verified
- VM lab: **36 pytest PASS + 12 subtests** for I28, I27 and C1/C4/C8 compatibility, including own-project editor GET, foreign-project 404, unauthenticated 401 for all editor assets, wrong origin 403, invalid ID 404 and recipe persistence/revision tests.
- Deployed only the private Owner beta module files in `~/montara-owner-portal-release/urano/`. Backup: `~/.local/share/montara-owner-backups/i28-20261110-221617/`. Existing I27 feature flag remains the gate. No changes to `main`, Chema servers 8101–8103, Cloudflare or root broker.
- After restart, Owner `active`, `/healthz` **HTTP 200**, unauthenticated workspace GET **401**.
- Need Fernando's human browser check for page appearance and saved recipe reload; no actual user session has been manufactured or impersonated.

## Limit / next action
This is the first **functional owner-scoped editor workspace**, **not** yet the full classic editor with Stage/Show timeline, live video rendering, Companion upload, persisted media or MP4 export. Classic `web/index.html` depends extensively on global `/api/v1/wizard` and `/api/v1/edit` APIs; mounting them behind the Owner proxy as-is would bypass owner isolation. Follow up by adapting the existing UI to the per-project Engine routing and Companion lifecycle, rather than exposing global paths.

## Human trial
With Google logged into `https://montara-owner.memoriainvalida001.workers.dev/`, choose a project and click **Entrar al estudio**; choose Stage, add a montage block, save, refresh the tab and check persistence; open/close Engine in the workspace if desired. Do not install Companion until we inventory Windows versions.

## Rollback
Restore `minimal_owner_api.py` and `owner_dashboard.py` from the I28 backup directory, optionally remove `owner_editor_workspace.py`, and restart `montara-owner-beta.service` (user systemd). This does not change any database schema or the I27 broker. If necessary the I27 flag can be disabled independently.

Current remote access: Desktop Commander Remote -> Oracle -> `ssh montara`; TryGateway retired.

