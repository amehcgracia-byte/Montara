# Public preview access and storage

Public entry: https://montara-tau.vercel.app/. Share that entry, using the
editor's **Share Montara** control. A `vercel.run` URL belongs to one browser
session and requires its private cookie; it is not a shareable public entry.
An unauthenticated visitor now gets an explanation and a public-entry button.
The per-session access checks remain enabled.

The previous deployment allocated a 1 GiB Drive per visitor. The real failure
was an export requiring about 0.8 GiB when only 0.7 GiB remained. Separately,
the account had reserved its entire 15 GiB Hobby Drive allowance, so a new
visitor could not open a preview at all.

Preview data now uses the sandbox's larger private working filesystem, with
automatic snapshot persistence on stop. It does not allocate a new visitor
Drive. Existing snapshot-based sessions retain their current data. An old
Drive-based session is migrated only when idle: its Drive is retained, mounted
as a read-only snapshot and copied into the working filesystem. The template's
old workspace is moved outside the visitor's accessible data namespace. A
marker makes initialization idempotent. Busy renders are left running.

Keep the four-active-preview limit, 45-minute runtime, seven-day snapshot
expiration and one retained snapshot per preview. This remains a limited test
environment, not permanent user-account storage. Other Vercel compute or
snapshot quotas can still limit availability. No billing plan was upgraded and
no saved visitor Drive was deleted.

## Verification

- 77 Python regression tests passed locally, including migration failure and
  data preservation, isolation and the unauthenticated access page.
- Four JavaScript session-policy tests passed: new visitors allocate no Drive,
  saved Drives migrate read-only, busy sessions are preserved, and existing
  snapshot sessions retain their data.
- The staged deployment opened from an independent HTTP client without a
  ChatGPT session and returned the How interface and example inputs.
- A real sandbox had 58.5 GiB available; the engine's 0.8 GiB export-space
  check passed, and FFmpeg produced a one-second test video with audio.
- The affected visitor's two projects were copied to the larger disk. Forty
  saved project, artifact/input and mixed-audio files were compared byte for
  byte with the retained source Drive. All matched; the export-space check
  passed there with 58.3 GiB available. The user's full edited video was not
  re-rendered as part of this storage check.
