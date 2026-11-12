"""Reviewed Owner gateway routes for Chema's native full-session flow.

No catch-all /montara forwarding. Each route is bound to one already verified
Owner + Stage project, and session IDs are fenced by owner_session_bindings.
"""
from __future__ import annotations

import re
from urllib.parse import urlencode

_SESSION_ID = r"[a-f0-9]{12}"
_RESULT_ID = r"[0-9]{1,6}"
_SESSION_PATH = re.compile(rf"session/({_SESSION_ID})(?:/(.*))?\Z")
_ALLOWED_ACTIONS = frozenset({
    "prepare","render","songs","cancel","include","video-master",
    "local-result","originals"
})
_ALLOWED_READS = frozenset({
    "video-source","waveform","listen","originals","local-plan","results.zip"
})
_INTEGER = re.compile(r"[0-9]{1,9}\Z")
_REAL = re.compile(r"[0-9]{1,9}(?:\.[0-9]{1,6})?\Z")
_NAME = re.compile(r"[^\\/\x00-\x1f]{0,160}\Z")


def session_operation(method: str, operation: str):
    """Return (worker path, bound session id) or None, with exact methods."""
    if operation=="session" and method=="POST":
        return "/montara/session", None
    if operation=="session/latest" and method=="GET":
        return "/montara/session/latest", "latest"
    found=_SESSION_PATH.fullmatch(operation)
    if not found:
        return None
    sid,sub=found.groups()
    if sub is None and method=="GET":
        return "/montara/session/"+sid,sid
    if sub in _ALLOWED_READS and method=="GET":
        return "/montara/session/"+sid+"/"+sub,sid
    if sub=="listen" and method=="HEAD":
        return "/montara/session/"+sid+"/listen",sid
    if sub in _ALLOWED_ACTIONS and method=="POST":
        return "/montara/session/"+sid+"/"+sub,sid
    if method=="GET" and re.fullmatch(r"result/("+_RESULT_ID+r")",sub or ""):
        return "/montara/session/"+sid+"/"+sub,sid
    return None


def session_query(operation: str, values) -> str | None:
    """Accept only reviewed numeric range/song parameters; no paths."""
    if not values:
        return ""
    if any(len(values.getlist(k)) != 1 for k in values):
        return None
    if operation.endswith("/listen"):
        if set(values) != {"start","end"}:
            return None
        if any(not _REAL.fullmatch(values[k]) for k in ("start","end")):
            return None
    elif operation.endswith("/originals") or operation.endswith("/local-plan"):
        if not set(values) <= {"song","start","end","name"} or "song" not in values:
            return None
        if not _INTEGER.fullmatch(values["song"]):
            return None
        for key in ("start","end"):
            if key in values and not _REAL.fullmatch(values[key]):
                return None
        if "name" in values and not _NAME.fullmatch(values["name"]):
            return None
    elif "/result/" in operation:
        if set(values) not in ({"download"},{"v"}):
            return None
        if "download" in values and values["download"]!="1":
            return None
        if "v" in values and not _INTEGER.fullmatch(values["v"]):
            return None
    else:
        return None
    return "?"+urlencode({k:values[k] for k in values})


def session_media(method: str, operation: str) -> bool:
    return ((method in ("GET","HEAD") and operation.endswith("/listen"))
            or (method=="GET" and
                (operation.endswith("/results.zip") or
                 re.search(r"/result/[0-9]{1,6}\Z",operation) is not None)))
