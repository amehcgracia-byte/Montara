"""Observe the existing Stage journey; evaluate a one-selector QA UI correction.

Only the browser response is changed, never the application/engine sources.
The original failing journey must be observed before the corrected control.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("SATURNO09_STAGE_OUT", "/tmp/saturno09-stage"))
OLD = "$('#cameraList .cam').forEach"
NEW = "$$('#cameraList .cam').forEach"


def server():
    """QA server entry point: encoder control in memory, with effective command log."""
    sys.path.insert(0, str(ROOT / "engine"))
    sys.path.insert(0, str(ROOT))
    import core.stages.export as export
    import threading
    original = export._run_ffmpeg_progress
    lock = threading.Lock()

    def controlled(command, duration, label, progress):
        effective = list(command)
        if "libx264" in effective:
            effective[-1:-1] = ["-threads:v", "1"]
        record = {"engine_command": command, "effective_command": effective, "label": str(label)}
        started = time.perf_counter()
        try:
            return original(effective, duration, label, progress)
        except Exception as exc:
            record["error"] = repr(exc)
            raise
        finally:
            record["elapsed_sec"] = time.perf_counter() - started
            with lock, (OUT / "commands.jsonl").open("a") as handle:
                handle.write(json.dumps(record) + "\n")

    export._run_ffmpeg_progress = controlled
    import app
    sys.argv = [str(ROOT / "app.py"), *sys.argv[2:]]
    app.main()


class ObservedPage:
    def __init__(self, page):
        self.page = page

    def __getattr__(self, key):
        return getattr(self.page, key)

    def wait_for_selector(self, selector, **kwargs):
        if "timeout" in kwargs:
            kwargs["timeout"] = min(kwargs["timeout"], 600_000)
        if selector == "#cameras:not([hidden]), #making:not([hidden])":
            selector += ", #failed:not([hidden])"
            kwargs["timeout"] = 60_000
        result = self.page.wait_for_selector(selector, **kwargs)
        if self.page.locator("#failed").is_visible():
            raise RuntimeError("OBSERVED_UI_FAILURE: " + self.page.locator("#errorText").inner_text())
        return result

    def wait_for_function(self, function, **kwargs):
        if "timeout" in kwargs:
            kwargs["timeout"] = min(kwargs["timeout"], 180_000)
        return self.page.wait_for_function(function, **kwargs)


def capture(page, url, out, events):
    data = {"events": events,
            "visible_screens": page.locator("section.screen:not([hidden])").evaluate_all("xs => xs.map(x => x.id)"),
            "error_text": page.locator("#errorText").text_content()}
    try:
        with urlopen(url + "/api/v1/wizard/status", timeout=15) as response:
            data["wizard_status"] = json.load(response)
    except Exception as exc:
        data["status_error"] = repr(exc)
    data["json_files"] = {}
    for path in sorted((OUT / "runtime").rglob("*.json")):
        if path.stat().st_size > 1_000_000:
            continue
        # Includes exact edit_plan/project when present, rather than inventing a plan.
        try:
            data["json_files"][str(path.relative_to(OUT))] = json.loads(path.read_text())
        except (ValueError, UnicodeError):
            pass
    return data


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"status": "NOT_RUN", "gate_full_stage": False,
              "scope": "Existing real Stage journey, observed original UI then QA-only selector correction",
              "qa_controls": ["Browser response only: single selector $ -> $$", "libx264 encoder threads:v 1 in server memory"]}
    proc = None
    try:
        spec = importlib.util.spec_from_file_location("journey", ROOT / "tests/e2e_journey.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        port = module.free_port()
        url = f"http://127.0.0.1:{port}"
        runtime = OUT / "runtime"
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "ZUCKER_DATA_ROOT": str(runtime)}
        server_log = (OUT / "server.log").open("w")
        proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "server",
                                 "--port", str(port), "--data", str(runtime)],
                                env=env, stdout=server_log, stderr=subprocess.STDOUT)
        ready = False
        for _ in range(90):
            if proc.poll() is not None:
                raise RuntimeError("Server exited before readiness")
            try:
                urlopen(url + "/api/v1/wizard/status", timeout=2).close()
                ready = True
                break
            except Exception:
                time.sleep(1)
        if not ready:
            raise RuntimeError("Server readiness timed out")
        source_js = (ROOT / "web/montara.js").read_text()
        assert source_js.count(OLD) == 1, "UI correction no longer matches exactly one occurrence"
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for label, corrected in (("original", False), ("selector_control", True)):
                context = browser.new_context(viewport={"width": 1440, "height": 960})
                if corrected:
                    context.route("**/montara.js", lambda route: route.fulfill(
                        status=200, content_type="application/javascript", body=source_js.replace(OLD, NEW)))
                page = context.new_page()
                events = []
                page.on("pageerror", lambda error: events.append({"kind": "pageerror", "message": str(error)}))
                page.on("console", lambda message: events.append({"kind": "console", "type": message.type,
                                                                  "message": message.text[:2000]}) if message.type == "error" else None)
                page.on("response", lambda response: events.append({"kind": "http_error", "status": response.status,
                                                                      "url": response.url}) if response.status >= 400 else None)
                started = time.perf_counter()
                try:
                    result = module.journey(ObservedPage(page), url, "stage", module.REAL, OUT / label)
                except Exception as exc:
                    result = {"passed": False, "error": repr(exc)}
                result["elapsed_sec"] = time.perf_counter() - started
                result["evidence"] = capture(page, url, OUT / label, events)
                report[label] = result
                print(json.dumps({"stage_arm": label, "passed": result.get("passed"),
                                  "error": result.get("error"), "elapsed_sec": result["elapsed_sec"]}), flush=True)
                context.close()
                if not corrected:
                    if result.get("passed"):
                        report["gate_full_stage"] = True
                        report["selector_control_skipped"] = "Original succeeded; no correction justified"
                        break
                    if "forEach" not in str(result):
                        report["selector_control_skipped"] = "Failure does not support predeclared selector hypothesis"
                        break
                elif result.get("passed"):
                    report["gate_full_stage"] = True
            browser.close()
        report["status"] = "STAGE_COMPLETE_UNDER_QA_CONTROLS" if report["gate_full_stage"] else "STAGE_BLOCKED_WITH_EVIDENCE"
    except Exception as exc:
        report.update(status="PROBE_INFRASTRUCTURE_ERROR", error=repr(exc))
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        log = OUT / "server.log"
        report["server_log_tail"] = log.read_text(errors="replace")[-12000:] if log.exists() else ""
        command_log = OUT / "commands.jsonl"
        report["ffmpeg_commands"] = [json.loads(line) for line in command_log.read_text().splitlines()] if command_log.exists() else []
        report["export_files"] = [{"path": str(p), "bytes": p.stat().st_size,
                                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                                   for p in OUT.rglob("render.mp4")]
        (OUT / "REPORT.json").write_text(json.dumps(report, indent=2))
        print("SATURNO09_STAGE_BEGIN", flush=True)
        print(json.dumps(report), flush=True)
        print("SATURNO09_STAGE_END", flush=True)
    # This step COLLECTS a diagnosis. The scientific gate is explicit, never inferred from exit code.
    return 0 if report["status"] != "PROBE_INFRASTRUCTURE_ERROR" else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        server()
    else:
        raise SystemExit(main())
