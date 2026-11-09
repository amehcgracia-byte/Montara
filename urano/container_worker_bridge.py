"""U13D2C private bridge: supervisor protocol carried over a Docker CLI child.

This is a laboratory bridge for synthetic workers only. No public HTTP routes.
Docker daemon is a privileged infrastructure dependency; never pass user-supplied
image, workspace, container name, or worker command.
"""
from __future__ import annotations

import json
import os
import re
import select
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from urano.container_isolation import isolated_container_command
from urano.private_worker_supervisor import WorkerFailure
from urano.runtime_activation import RuntimeActivationGuard, ActivationTicket

_CID = re.compile(r"^[a-f0-9]{64}$")


class ContainerWorkerBridge:
    """One private container for an owner, fenced by the U13B runtime guard.

    Closing Docker CLI is NOT sufficient to terminate a running container;
    stop() verifies container deletion before invalidating runtime state.
    """

    def __init__(self, *, guard: RuntimeActivationGuard, owner_id: str,
                 runtime_id: str, workspace: Path, image: str, name: str,
                 worker_command: list[str], startup_timeout: float = 30,
                 open_timeout: float = 30, memory_mb: int = 512, cpus: float = 1):
        if os.name != "posix":
            raise RuntimeError("POSIX-only Docker lab bridge")
        self.guard, self.owner_id, self.runtime_id = guard, owner_id, runtime_id
        self.workspace, self.name = Path(workspace), name
        self.startup_timeout, self.open_timeout = startup_timeout, open_timeout
        if not (0 < startup_timeout <= 120 and 0 < open_timeout <= 120):
            raise ValueError("Invalid deadlines")
        self._argv = isolated_container_command(
            image=image, name=name, workspace=self.workspace,
            command=worker_command, memory_mb=memory_mb, cpus=cpus)
        self.process: subprocess.Popen | None = None
        self.cid: str | None = None
        self._cid_dir: tempfile.TemporaryDirectory | None = None
        self._rx = b""
        self._generation: int | None = None
        self._ingest_project: str | None = None
        self._ingest_generation: int | None = None
        self.last_ingest_failure_code: int | None = None

    def _docker(self, *args: str, timeout: float = 5):
        return subprocess.run(
            ["docker", *args], capture_output=True, text=True, timeout=timeout
        )

    def _recv(self, deadline: float) -> dict:
        proc = self.process
        if proc is None or proc.stdout is None:
            raise WorkerFailure("Worker not started")
        while True:
            if b"\n" in self._rx:
                raw, self._rx = self._rx.split(b"\n", 1)
                try:
                    msg = json.loads(raw)
                except (ValueError, UnicodeError) as exc:
                    raise WorkerFailure("Malformed Docker worker reply") from exc
                if not isinstance(msg, dict):
                    raise WorkerFailure("Malformed Docker worker reply")
                return msg
            if len(self._rx) > 8192 or time.monotonic() >= deadline:
                raise WorkerFailure("Docker worker timeout or oversized reply")
            wait = min(.2, max(0, deadline - time.monotonic()))
            ready, _, _ = select.select([proc.stdout], [], [], wait)
            if ready:
                chunk = os.read(proc.stdout.fileno(), 4096)
                if not chunk:
                    raise WorkerFailure("Docker worker pipe closed")
                self._rx += chunk
            elif proc.poll() is not None:
                raise WorkerFailure("Docker CLI exited")

    def _check_container(self) -> None:
        if self.cid is None:
            raise WorkerFailure("Container identity unavailable")
        inspect = self._docker(
            "inspect", "--format",
            "{{.Id}}|{{.State.Running}}|{{.HostConfig.NetworkMode}}",
            self.cid
        )
        if inspect.returncode != 0:
            raise WorkerFailure("Container inspect unavailable")
        if inspect.stdout.strip() != f"{self.cid}|true|none":
            raise WorkerFailure("Container state or identity mismatch")

    def start(self) -> None:
        if self.process is not None:
            raise WorkerFailure("Worker already running")
        state, _, generation = self.guard.get_state(self.owner_id, self.runtime_id)
        if state != "idle":
            raise WorkerFailure("Runtime must be idle")
        self._generation = generation
        cid_dir = tempfile.TemporaryDirectory(prefix="urano-cid-")
        self._cid_dir = cid_dir
        cid_file = str(Path(cid_dir.name) / "container.cid")
        argv = self._argv[:]
        argv[2:2] = ["-i", "--cidfile", cid_file]
        self.process = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, start_new_session=True, bufsize=0
        )
        try:
            ready = self._recv(time.monotonic() + self.startup_timeout)
            if (ready.get("type") != "ready" or
                type(ready.get("worker_pid")) is not int or ready["worker_pid"] <= 0):
                raise WorkerFailure("Docker worker handshake failed")
            raw_id = Path(cid_file).read_text().strip()
            if not _CID.fullmatch(raw_id):
                raise WorkerFailure("Invalid Docker container identity")
            self.cid = raw_id
            self._check_container()
        except Exception:
            self.stop()
            raise

    def open_project(self, project_id: str) -> ActivationTicket:
        if self.process is None or self.process.poll() is not None:
            raise WorkerFailure("Container worker not active")
        self._check_container()
        ticket = self.guard.request_open(self.owner_id, self.runtime_id, project_id)
        self._generation = ticket.generation
        try:
            command = json.dumps({"op": "open", "folder": ticket.project_path.name}) + "\n"
            assert self.process.stdin is not None
            self.process.stdin.write(command.encode())
            self.process.stdin.flush()
            result = self._recv(time.monotonic() + self.open_timeout)
            if (result.get("type") != "opened" or result.get("ok") is not True
                or result.get("folder") != ticket.project_path.name):
                raise WorkerFailure("Container Engine activation rejected")
            self._check_container()
            self.guard.acknowledge_open(self.owner_id, ticket, success=True)
            return ticket
        except Exception:
            self.stop()
            raise

    def register_staged_inputs(self, project_id: str) -> int:
        """Trusted operation: worker reads only fixed hashed camera files.

        No paths or media metadata pass over stdio or owner HTTP.
        """
        if self.process is None or self.process.poll() is not None:
            raise WorkerFailure("Private Engine not active")
        self._check_container()
        state, active, _ = self.guard.get_state(self.owner_id, self.runtime_id)
        if state != "ready" or active != project_id:
            raise WorkerFailure("Private project must be active")
        try:
            assert self.process.stdin is not None
            self.process.stdin.write(b'{"op":"register_staged_proxies"}\n')
            self.process.stdin.flush()
            response = self._recv(time.monotonic() + self.open_timeout)
            count = response.get("source_count")
            if (response.get("ok") is not True or
                    response.get("type") != "staged_inputs_registered" or
                    type(count) is not int or not 1 <= count <= 16):
                raise WorkerFailure("Engine rejected staged inputs")
            self._check_container()
            return count
        except Exception:
            self.stop()
            raise WorkerFailure("Cannot verify private Stage input registration")

    def ingest_start(self, project_id: str) -> None:
        """Start fixed Engine Ingest using ONLY previously provisioned inputs.

        No file path enters the command. The guard fences the active owner
        project. A rejected/ambiguous response kills the worker fail-closed.
        """
        self.last_ingest_failure_code = None
        if self._ingest_project is not None:
            raise WorkerFailure("Ingest already active")
        if self.process is None or self.process.poll() is not None:
            raise WorkerFailure("Private Engine not active")
        self._check_container()
        generation = self.guard.begin_job(self.owner_id, self.runtime_id, project_id)
        self._ingest_project = project_id
        self._ingest_generation = generation
        try:
            assert self.process.stdin is not None
            self.process.stdin.write(b'{"op":"ingest_start"}\n')
            self.process.stdin.flush()
            response = self._recv(time.monotonic() + self.open_timeout)
            if response != {"ok": True, "type": "ingest_started"}:
                # Internal diagnostic only; never exposed by the HTTP route.
                if response.get("type") == "ingest_start_rejected" and type(response.get("http_status")) is int:
                    self.last_ingest_failure_code = response["http_status"]
                raise WorkerFailure("Engine did not accept Ingest")
            self._check_container()
        except Exception:
            self.stop()
            raise WorkerFailure("Private Ingest unavailable")

    def ingest_status(self, project_id: str) -> str:
        if project_id != self._ingest_project or self._ingest_generation is None:
            raise WorkerFailure("No matching active Ingest")
        try:
            if self.process is None or self.process.poll() is not None:
                raise WorkerFailure("Private Engine not active")
            self._check_container()
            assert self.process.stdin is not None
            self.process.stdin.write(b'{"op":"ingest_status"}\n')
            self.process.stdin.flush()
            response = self._recv(time.monotonic() + self.open_timeout)
            status = response.get("status")
            if (response.get("ok") is not True or
                    response.get("type") != "ingest_status" or
                    status not in {"pending", "idle", "queued", "running",
                                   "done", "failed", "blocked", "not_started"}):
                raise WorkerFailure("Engine Ingest status unavailable")
            if status in {"done", "failed", "blocked"}:
                self.guard.finish_job(self.owner_id, self.runtime_id,
                                      project_id, self._ingest_generation)
                self._ingest_project = None
                self._ingest_generation = None
            return status
        except Exception:
            self.stop()
            raise WorkerFailure("Private Ingest status unavailable")

    def ingest_proof(self, project_id: str) -> list[dict]:
        """Return hashes computed under the isolated Engine UID, not file paths.

        Only a trusted owner-bound active container can answer. No untrusted
        path is accepted over stdio. A malformed response kills the worker.
        """
        if self.process is None or self.process.poll() is not None:
            raise WorkerFailure("Private Engine is not active")
        self._check_container()
        state, active, _ = self.guard.get_state(self.owner_id, self.runtime_id)
        if state != "ready" or active != project_id:
            raise WorkerFailure("Ingest proof requires the completed active project")
        try:
            assert self.process.stdin is not None
            self.process.stdin.write(b'{"op":"ingest_proof"}\n')
            self.process.stdin.flush()
            result = self._recv(time.monotonic() + self.open_timeout)
            sources = result.get("sources")
            if (result.get("ok") is not True or
                    result.get("type") != "ingest_proof" or
                    not isinstance(sources, list) or not 1 <= len(sources) <= 16):
                raise WorkerFailure("Invalid private Engine ingest proof")
            expected_slots = set(range(len(sources)))
            found_slots = set()
            for entry in sources:
                if not isinstance(entry, dict) or set(entry) != {
                    "slot", "proxy_sha256", "normalized_sha256"}:
                    raise WorkerFailure("Invalid private Engine proof format")
                slot = entry["slot"]
                if type(slot) is not int or slot not in expected_slots or slot in found_slots:
                    raise WorkerFailure("Invalid Engine proof slot")
                if any(not isinstance(entry[k], str) or
                       not re.fullmatch(r"[a-f0-9]{64}", entry[k])
                       for k in ("proxy_sha256", "normalized_sha256")):
                    raise WorkerFailure("Invalid Engine proof hash")
                found_slots.add(slot)
            if found_slots != expected_slots:
                raise WorkerFailure("Incomplete private Engine ingest proof")
            self._check_container()
            return sorted(sources, key=lambda entry: entry["slot"])
        except Exception:
            self.stop()
            raise WorkerFailure("Private Engine ingest proof unavailable")

    def stop(self) -> None:
        proc, self.process = self.process, None
        cid, self.cid = self.cid, None
        confirmed_gone = False
        try:
            if cid:
                removed = self._docker("rm", "-f", cid, timeout=10)
                absent = self._docker("inspect", cid)
                confirmed_gone = removed.returncode == 0 and absent.returncode != 0
            elif proc is None:
                confirmed_gone = True
            # If handshake failed before reading CID, a container might still
            # exist by NAME; never release the runtime until Docker confirms
            # there is no such container. Names are private infrastructure IDs.
            if not confirmed_gone:
                result = self._docker("rm", "-f", self.name, timeout=10)
                absent = self._docker("inspect", self.name)
                confirmed_gone = absent.returncode != 0
        finally:
            if proc:
                if proc.poll() is None:
                    try: os.killpg(proc.pid, signal.SIGTERM)
                    except ProcessLookupError: pass
                    try: proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        try: os.killpg(proc.pid, signal.SIGKILL)
                        except ProcessLookupError: pass
                        proc.wait(timeout=3)
                if proc.stdin: proc.stdin.close()
                if proc.stdout: proc.stdout.close()
            self._ingest_project = None
            self._ingest_generation = None
            self._rx = b""
            if self._cid_dir:
                self._cid_dir.cleanup()
                self._cid_dir = None
        if not confirmed_gone:
            raise WorkerFailure("Cannot verify Docker worker removal; runtime remains fenced")
        if self._generation is not None:
            self.guard.invalidate_after_worker_exit(
                self.owner_id, self.runtime_id, self._generation)
            self._generation = None
