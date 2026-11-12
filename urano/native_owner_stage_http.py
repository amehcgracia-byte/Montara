"""Reviewed first Stage media routes for the ORIGINAL Chema browser.

Other Music, Push, Show, native export and preview URLs stay denied until
their separate contract is verified. Never forward a browser-supplied path,
owner, worker generation or arbitrary query through a generic proxy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode

_SETTINGS = frozenset({
    "fillers", "video-light", "camera-types", "camera-subjects",
    "camera-roles", "spherical-landmarks", "stage-performers",
})
_UUID = re.compile(r"[a-f0-9]{32}\Z")
_PREVIEW = re.compile(r"/api/v1/wizard/review/preview/[0-9]{1,5}\Z")
_THUMB = re.compile(
    r"/api/v1/wizard/review/thumbnail/(?:assets-v2|[a-f0-9]{16,128})/"
    r"[A-Za-z0-9_.-]{1,180}\Z")
_MAX_QUERY = 2048


@dataclass(frozen=True)
class NativeStageTarget:
    upstream: str
    kind: str  # "json", "upload-init", "upload-chunk", "upload-direct"


def native_stage_route(method: str, path: str, query: str = "") -> NativeStageTarget | None:
    if (not isinstance(method,str) or not isinstance(path,str)
            or not isinstance(query,str) or len(query)>_MAX_QUERY):
        return None
    if path.startswith("/api/v1/settings/"):
        key=path.removeprefix("/api/v1/settings/")
        if key in _SETTINGS and method=="POST" and not query:
            return NativeStageTarget(path,"json")
        return None
    static={
        ("GET","/api/v1/artifacts/sync"):"json",
        ("POST","/montara/branding"):"branding",
        ("POST","/api/v1/wizard/review/replace"):"json",
        ("POST","/api/v1/wizard/review/render"):"json",
        ("POST","/api/v1/wizard/upload"):"upload-direct",
        ("GET","/montara/uploads"):"upload-limits",
        ("POST","/montara/uploads"):"upload-init",
    }
    kind=static.get((method,path))
    if kind is not None:
        return NativeStageTarget(path,kind) if not query else None
    if method=="GET" and path=="/api/v1/wizard/review":
        if not query:
            return NativeStageTarget(path,"json")
        try:
            values=parse_qs(query,keep_blank_values=True,strict_parsing=True,
                            max_num_fields=2)
        except ValueError:
            return None
        if (not set(values) <= {"render","shot"}
                or any(len(v)!=1 for v in values.values())
                or any(k not in values for k in ("render",))
                or values.get("render",["0"])[0] not in ("0","1")
                or ("shot" in values and
                    (not re.fullmatch(r"[0-9]{1,5}",values["shot"][0])))):
            return None
        return NativeStageTarget(path+"?"+urlencode(
            {k:values[k][0] for k in ("render","shot") if k in values}),"json")
    # Original Chema local-quality export contract. URLs may carry only an
    # owner-scoped saved project path and the signed edit revision.
    if method in ("GET","HEAD") and (path in (
            "/api/v1/edit/native-recipe",
            "/api/v1/edit/native-master") or re.fullmatch(
                r"/api/v1/edit/native-source/[0-9]{1,3}",path)):
        if method=="HEAD" and "/native-source/" not in path:
            return None
        try:
            values=parse_qs(query,strict_parsing=True,max_num_fields=2)
        except ValueError:
            return None
        if (any(len(v)!=1 for v in values.values()) or
                set(values)!=({"project_id"} if path.endswith("native-recipe")
                              else {"project_id","revision"}) or
                not values["project_id"][0].startswith("/") or
                len(values["project_id"][0])>1800 or
                ("revision" in values and not re.fullmatch(
                     r"[a-f0-9]{20}",values["revision"][0]))):
            return None
        return NativeStageTarget(path+"?"+urlencode(
            {k:values[k][0] for k in ("project_id","revision")
             if k in values}),
            "native-recipe" if path.endswith("native-recipe") else
            "native-master" if path.endswith("native-master") else
            "native-source")
    # Original Chema Stage shot editor: bounded index, generation-checked
    # edit revision and explicit camera choice. No arbitrary project query.
    if path=="/api/v1/edit/shot":
        if method=="PATCH" and not query:
            return NativeStageTarget(path,"shot-patch")
        if method=="GET":
            try:
                args=parse_qs(query,strict_parsing=True,max_num_fields=1)
            except ValueError:
                return None
            if set(args)=={"index"} and len(args["index"])==1 and re.fullmatch(
                    r"[0-9]{1,4}",args["index"][0]):
                return NativeStageTarget(path+"?"+urlencode(
                    {"index":args["index"][0]}),"json")
        return None
    if method=="GET" and path=="/api/v1/edit/shot/frame":
        try:
            args=parse_qs(query,strict_parsing=True,max_num_fields=3)
        except ValueError:
            return None
        if (set(args)=={"index","choice","revision"} and
                all(len(v)==1 for v in args.values()) and
                re.fullmatch(r"[0-9]{1,4}",args["index"][0]) and
                re.fullmatch(r"[0-9]{1,2}",args["choice"][0]) and
                re.fullmatch(r"[a-f0-9]{20}",args["revision"][0])):
            return NativeStageTarget(path+"?"+urlencode(
                {k:args[k][0] for k in ("index","choice","revision")}),
                "shot-frame")
        return None
    if method=="GET" and path=="/montara/audio":
        if not query or len(query)>_MAX_QUERY:
            return None
        try:
            params=parse_qs(query,keep_blank_values=False,strict_parsing=True,
                            max_num_fields=1)
        except ValueError:
            return None
        if (set(params)!={"path"} or len(params["path"])!=1 or
                not params["path"][0].startswith("/") or
                len(params["path"][0])>1800 or
                any(c in params["path"][0] for c in (chr(0), chr(13), chr(10)))):
            return None
        return NativeStageTarget(path+"?"+urlencode({"path":params["path"][0]}),
                                 "audio-media")
    if method=="GET" and (_PREVIEW.fullmatch(path) or _THUMB.fullmatch(path)):
        if query:
            try:
                params=parse_qs(query,keep_blank_values=True,strict_parsing=True,
                                max_num_fields=1)
            except ValueError:
                return None
            if (set(params)!={"v"} or len(params["v"])!=1 or
                    not re.fullmatch(r"[A-Za-z0-9_.-]{0,80}",
                                     params["v"][0])):
                return None
            return NativeStageTarget(path+"?"+urlencode({"v":params["v"][0]}),
                                     "review-media")
        return NativeStageTarget(path,"review-media")
    prefix="/montara/uploads/"
    if path.startswith(prefix):
        tail=path[len(prefix):]
        sections=tail.split("/")
        uid=sections[0] if sections else ""
        if not _UUID.fullmatch(uid):
            return None
        if len(sections)==1 and method=="PUT" and not query:
            return NativeStageTarget(path,"upload-chunk")
        if len(sections)==1 and method in ("GET","DELETE") and not query:
            return NativeStageTarget(path,"json")
        if len(sections)==2 and sections[1]=="finish" and method=="POST" and not query:
            return NativeStageTarget(path,"upload-finish")
    return None
