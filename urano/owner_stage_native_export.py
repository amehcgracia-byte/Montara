"""Owner-only native Stage export identity mapping for original JM engine.

The browser can address only the Owner UUID or fixed internal alias.  Only
the per-user worker knows the physical JM folder. This middleware runs INSIDE
the isolated worker, never in the public portal or privileged root broker.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from werkzeug.wrappers import Response


def _reject(environ,start_response):
    reply=Response(json.dumps({"error":{"message":"Private Stage export rejected"}}),
                   status=409,mimetype="application/json")
    return reply(environ,start_response)


class OwnerStageNativeExport:
    """Translate reviewed Stage recipe/master requests into a local project.

    Never allows selecting another filesystem path, source or owner. No
    fallback original sources in this first local-Companion pilot.
    """
    def __init__(self, application, *, folder: Path):
        self.app=application
        self.folder=Path(folder).resolve(strict=True)
        if not (self.folder/"project.json").is_file():
            raise ValueError("Uninitialized local Owner project")

    def __call__(self,environ,start_response):
        method=environ.get("REQUEST_METHOD")
        path=environ.get("PATH_INFO")
        if method=="GET" and path in (
            "/api/v1/edit/native-recipe",
            "/api/v1/edit/native-master",
        ):
            try:
                q=parse_qs(environ.get("QUERY_STRING",""),keep_blank_values=True,
                           strict_parsing=True,max_num_fields=4)
            except ValueError:
                return _reject(environ,start_response)
            permitted={"project_id"} if path.endswith("native-recipe") else {
                "project_id","revision"}
            if (set(q)!=permitted or any(len(values)!=1 for values in q.values())
                    or q["project_id"][0] not in
                    ("owner-worker",str(self.folder))):
                return _reject(environ,start_response)
            if "revision" in q and (not q["revision"][0].isascii()
                 or not __import__("re").fullmatch(r"[a-f0-9]{20}",q["revision"][0])):
                return _reject(environ,start_response)
            rewrite=dict((key,value[0]) for key,value in q.items())
            rewrite["project_id"]=str(self.folder)
            local=dict(environ)
            local["QUERY_STRING"]=urlencode(rewrite)
            return self.app(local,start_response)

        if method=="HEAD" and path.startswith("/api/v1/edit/native-source/"):
            # The no-upload-originals product strategy must not expose remote
            # originals in response to exploratory browser fetch/HEAD.
            return _reject(environ,start_response)

        return self.app(environ,start_response)
