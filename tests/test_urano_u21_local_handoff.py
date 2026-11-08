"""U21 local descriptor adapter: only local identities, no paths or uploads."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
from copy import deepcopy

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"companion"))
from urano_local_handoff import local_render_payload

OWNER_PLAN={
    "schema":"urano-local-handoff-descriptor-v1",
    "project_id":"11111111-1111-4111-8111-111111111111",
    "project_revision":1,
    "cuts":[{"source_slot":0,"start_ms":500,"end_ms":2500}],
    "requires_local_originals":True,
    "local_source_resolution_verified":False,
    "render_ready":False,
}
ORIGINAL={"name":"camera-original.mp4","size":1200000,"fingerprint":"a"*64}
BODY={"plan":OWNER_PLAN,"project":"b"*16,
      "master":"montara-render-audio-"+"a"*32+".audio",
      "originals":[{"source":0,"original":ORIGINAL}],
      "branding":"none","name":"Local U21"}
SHA="c"*40


class U21LocalTranslationContracts(unittest.TestCase):
    def test_valid_translation_and_millisecond_precision(self):
        result=local_render_payload(deepcopy(BODY),engine_sha=SHA)
        self.assertEqual(result["recipe"]["engine"],SHA)
        self.assertEqual(result["recipe"]["platform"],"youtube")
        self.assertEqual(result["recipe"]["segments"][0],{
            "source":0,"clip_start_sec":0.5,"duration_sec":2.0,
            "master_start_sec":0.0,"playback_speed":1.0})
        self.assertEqual(result["originals"][0]["original"]["fingerprint"],"a"*64)
        self.assertNotIn("path",str(result))
        self.assertNotIn("source_files",str(result))

    def test_multiple_cuts_consecutive_master_timeline(self):
        body=deepcopy(BODY)
        body["plan"]["cuts"].append({"source_slot":0,"start_ms":3500,"end_ms":4500})
        result=local_render_payload(body,engine_sha=SHA)
        self.assertEqual(result["recipe"]["segments"][1]["master_start_sec"],2.0)
        self.assertEqual(result["recipe"]["segments"][1]["duration_sec"],1.0)

    def test_bad_inputs_do_not_make_executable_recipe(self):
        def invalid(mutator):
            candidate=deepcopy(BODY)
            mutator(candidate)
            with self.assertRaises(ValueError):
                local_render_payload(candidate,engine_sha=SHA)
        examples=[
            lambda x:x["plan"].update(source_files={"0":"/Users/alice/private.mp4"}),
            lambda x:x["plan"].update(render_ready=True),
            lambda x:x["plan"].update(local_source_resolution_verified=True),
            lambda x:x["plan"]["cuts"][0].update(path="/Users/alice/private.mp4"),
            lambda x:x["plan"]["cuts"][0].update(source_slot=1),
            lambda x:x["plan"]["cuts"][0].update(source_slot=True),
            lambda x:x["plan"]["cuts"][0].update(end_ms=0),
            lambda x:x["plan"].update(cuts=[]),
            lambda x:x.update(originals=[]),
            lambda x:x["originals"][0].update(asset="proxy.small.mp4"),
            lambda x:x["originals"][0]["original"].update(name="../x.mp4"),
            lambda x:x["originals"][0]["original"].update(size=True),
            lambda x:x["originals"][0]["original"].update(fingerprint="bad"),
            lambda x:x.update(project="../other"),
            lambda x:x.update(master="/etc/passwd"),
            lambda x:x.update(recipe={"segments":[]}),
            lambda x:x.update(branding="mine"),
        ]
        for index,example in enumerate(examples):
            with self.subTest(case=index):invalid(example)

    def test_rejects_excess_output_and_wrong_engine(self):
        with self.assertRaises(ValueError):
            local_render_payload(BODY,engine_sha="invalid")
        body=deepcopy(BODY)
        body["plan"]["cuts"]=[{"source_slot":0,"start_ms":0,"end_ms":7200000}]*4
        with self.assertRaises(ValueError):
            local_render_payload(body,engine_sha=SHA)


if __name__=="__main__":
    unittest.main()
