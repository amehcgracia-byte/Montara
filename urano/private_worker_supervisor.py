"""U13D lab-only subprocess supervisor. NOT a multi-tenant OS sandbox.

Caller must provision an isolated UID/container and private storage beforehand.
Never expose this API to untrusted clients. Worker protocol is internal stdio.
"""
from __future__ import annotations

import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

from urano.runtime_activation import RuntimeActivationGuard, ActivationTicket, RuntimeBusy


class WorkerFailure(RuntimeError):
    pass


class PrivateWorkerSupervisor:
    """One worker tied to one trusted owner + runtime slot; no public HTTP."""

    def __init__(self, guard: RuntimeActivationGuard, owner_id: str,
                 runtime_id: str, engine_dir: Path, data_root: Path,
                 *, startup_timeout: float = 30, open_timeout: float = 30,
                 command: list[str] | None = None):
        if os.name != "posix":
            raise RuntimeError("U13D supervisor requires POSIX; Windows gate pending")
        self.guard, self.owner_id, self.runtime_id = guard, owner_id, runtime_id
        self.engine_dir, self.data_root = Path(engine_dir), Path(data_root)
        self.startup_timeout, self.open_timeout = startup_timeout, open_timeout
        if not (0 < startup_timeout <= 120 and 0 < open_timeout <= 120):
            raise ValueError("Invalid worker deadlines")
        self.command = command
        self.process: subprocess.Popen | None = None
        self._buffer = b""
        self._generation: int | None = None

    def _receive(self, deadline: float) -> dict:
        process = self.process
        if process is None or process.stdout is None:
            raise WorkerFailure("No worker")
        while True:
            if b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                try:
                    packet = json.loads(line)
                except (ValueError, UnicodeDecodeError) as exc:
                    raise WorkerFailure("Malformed worker protocol") from exc
                if not isinstance(packet, dict):
                    raise WorkerFailure("Malformed worker protocol")
                return packet
            if len(self._buffer) > 8192:
                raise WorkerFailure("Worker response too large")
            wait = deadline - time.monotonic()
            if wait <= 0:
                raise WorkerFailure("Worker response timeout")
            ready, _, _ = select.select([process.stdout], [], [], min(wait, 0.25))
            if not ready:
                if process.poll() is not None:
                    raise WorkerFailure("Worker exited")
                continue
            chunk = os.read(process.stdout.fileno(), 4096)
            if not chunk:
                raise WorkerFailure("Worker pipe closed")
            self._buffer += chunk

    def start(self) -> None:
        if self.process is not None:
            raise WorkerFailure("Worker already started")
        state, _, gen = self.guard.get_state(self.owner_id, self.runtime_id)
        if state != "idle":
            raise WorkerFailure("Runtime must be idle before a new worker starts")
        self._generation = gen
        if (not self.engine_dir.is_dir() or not self.data_root.is_dir()
            or self.data_root.is_symlink() or not (self.data_root / "Projects").is_dir()):
            raise ValueError("Missing private Engine runtime paths")
        command = self.command or [
            sys.executable, "-m", "urano.engine_worker_process",
            "--engine-dir", str(self.engine_dir), "--data-root", str(self.data_root)
        ]
        # Only process separation. Strong isolation requires a different OS
        # identity/container and restricted mounts, NOT achieved here.
        self.process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0, start_new_session=True
        )
        try:
            packet = self._receive(time.monotonic() + self.startup_timeout)
            if packet.get("type") != "ready" or not isinstance(packet.get("worker_pid"), int):
                raise WorkerFailure("Worker did not handshake")
            if packet["worker_pid"] != self.process.pid:
                raise WorkerFailure("Worker PID handshake mismatch")
        except Exception:
            self.stop()
            raise

    def _send(self, command: dict) -> None:
        process = self.process
        if process is None or process.stdin is None or process.poll() is not None:
            raise WorkerFailure("Worker unavailable")
        payload = (json.dumps(command, separators=(",", ":")) + "\n").encode()
        if len(payload) > 8192:
            raise WorkerFailure("Command too large")
        try:
            process.stdin.write(payload)
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise WorkerFailure("Worker pipe broken") from exc

    def open_project(self, project_id: str) -> ActivationTicket:
        """Trusted caller only. Failure leaves guard non-ready, never fake success."""
        if self.process is None or self.process.poll() is not None:
            raise WorkerFailure("Worker not running")
        ticket = self.guard.request_open(self.owner_id, self.runtime_id, project_id)
        self._generation = ticket.generation
        try:
            self._send({"op": "open", "folder": ticket.project_path.name})
            packet = self._receive(time.monotonic() + self.open_timeout)
            if packet.get("ok") is not True or packet.get("type") != "opened" or (
                packet.get("folder") != ticket.project_path.name
            ):
                raise WorkerFailure("Engine project activation failed")
            self.guard.acknowledge_open(self.owner_id, ticket, success=True)
            return ticket
        except Exception:
            # A stuck worker must die: its Engine state may have changed even
            # when the command timed out. Never reuse this process.
            self.stop()
            raise

    def stop(self) -> None:
        process, self.process = self.process, None
        self._buffer = b""
        if process is None:
            return
        try:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=3)
        except (ProcessLookupError, OSError):
            pass
        finally:
            if process.stdin: process.stdin.close()
            if process.stdout: process.stdout.close()
            try: process.wait(timeout=1)
            except subprocess.TimeoutExpired: pass
            if process.poll() is not None and self._generation is not None:
                self.guard.invalidate_after_worker_exit(
                    self.owner_id, self.runtime_id, self._generation)
                self._generation = None
