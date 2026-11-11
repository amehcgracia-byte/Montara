"""Stage -> local Companion export handoff contracts.

Offline and small: no FFmpeg, actual render, files from a user's PC, or network.
The private Engine and the local renderer must have the same exact commit.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))
from video_jobs import VideoJobs
from video_recipe import validate


ENGINE = "a" * 40
OTHER_ENGINE = "b" * 40


def stage_recipe(engine=ENGINE):
    return {
        "version": 1,
        "engine": engine,
        "platform": "youtube",
        "sources": [{"key": 0}],
        "segments": [{
            "source": 0,
            "master_start_sec": 0,
            "clip_start_sec": 0,
            "duration_sec": 1.0,
            "playback_speed": 1.0,
        }],
    }


class NativeEngineHandoffTests(unittest.TestCase):
    def test_stage_recipe_carries_exact_engine_and_segment(self):
        plan = validate(stage_recipe())
        self.assertEqual(plan["engine"], ENGINE)
        self.assertEqual(plan["sources"], [{"key": 0}])
        self.assertEqual(len(plan["segments"]), 1)

    def test_other_project_mode_is_not_a_stage_export(self):
        recipe = stage_recipe()
        recipe["platform"] = "show"
        with self.assertRaisesRegex(ValueError, "Stage edit"):
            validate(recipe)

    def test_missing_or_invalid_engine_refuses_render_recipe(self):
        for value in ("", "not-a-sha", "../../etc/passwd", OTHER_ENGINE.upper(), None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate(stage_recipe(value))

    def test_mismatched_engine_rejected_before_any_media_or_render_work(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs = VideoJobs(directory)
            with patch.object(jobs, "runtime", return_value={"engine": ENGINE}):
                with patch("video_jobs.threading.Thread") as worker:
                    with self.assertRaisesRegex(ValueError, "Update the companion"):
                        jobs.start(
                            {"recipe": stage_recipe(OTHER_ENGINE)},
                            {},
                            lambda _: self.fail("Must not search local originals"),
                        )
                    worker.assert_not_called()
            self.assertFalse(jobs.jobs)
            self.assertFalse((Path(directory) / "video").exists())

    def test_renderer_must_be_installed_before_export(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs = VideoJobs(directory)
            with patch.object(jobs, "runtime", return_value=None):
                with self.assertRaisesRegex(ValueError, "Install the companion"):
                    jobs.start({"recipe": stage_recipe()}, {}, lambda _: None)
            self.assertFalse(jobs.jobs)

    def test_matching_engine_can_progress_to_local_folder_gate(self):
        # It has passed the version check, but the renderer still refuses to
        # proceed without an explicitly selected local project folder.
        with tempfile.TemporaryDirectory() as directory:
            jobs = VideoJobs(directory)
            with patch.object(jobs, "runtime", return_value={"engine": ENGINE}):
                with self.assertRaisesRegex(ValueError, "Choose the project folder"):
                    jobs.start(
                        {"recipe": stage_recipe(ENGINE)},
                        {},
                        lambda _: self.fail("Must not inspect originals without a folder"),
                    )
            self.assertFalse(jobs.jobs)


if __name__ == "__main__":
    unittest.main()
