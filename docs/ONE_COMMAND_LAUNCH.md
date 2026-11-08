# Open and update Montara together

For the Mac already configured with the Montara connection tools and Google Cloud
login, one command updates both applications and then opens Montara:

```sh
curl -fsSL https://raw.githubusercontent.com/amehcgracia-byte/Montara/main/deploy/vm/launch.py | python3
```

New installations of `deploy/vm/mac-tools.sh` also provide `montara-open` as the
short form. `montara-start` remains available to connect without updating.

The launcher resolves one immutable Montara release, starts the VM if necessary,
and updates only the JM installation on port 8101. It checks wizard, session,
mastering and media-worker activity and refuses to replace a modified checkout.
It never uses forced Git checkout/reset/clean and never operates on FER.
Already-current server code is reused without restarting its service.

Companion is installed from that same Montara commit, including the engine and
mixer pins. Its idle process is stopped before replacement, then started in the
background. The launcher verifies the actual Companion health response against
both server pins before opening the browser. Failed downloads or installs stop
the sequence; a version mismatch never proceeds to the browser. A current,
healthy Companion is reused even while it works. Its release marker is application
metadata, not an edit or source file.

Project plans, original media, remembered folders and exports are preserved.
The update requires an idle application when code changes are necessary. It does
not override active work or repair a dirty checkout. Connection/setup failures
produce a retry message; credentials are never included in its output.

Validation includes isolated cloud/installer orchestration tests, busy-job and
wrong-account rejection, no-reinstall behavior, and execution of the real installer
against disposable test processes. The tests never update or restart the real VM.
A real JM update remains an explicit operational action by the person running it.
