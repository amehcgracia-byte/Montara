"""I31 route-admission unit tests: no real Engine, network or broker process."""
import unittest
import uuid
from dataclasses import replace

from urano.private_engine_route_contract import (
    PrivateEngineRouteDenied, VerifiedEngineBinding, plan_private_engine_request,
)


OWNER = "owner-a"
PROJECT = str(uuid.UUID("7b8f5fd6-02b4-4cd0-8d16-c2d6d606a505"))
OTHER_PROJECT = str(uuid.UUID("b6e40fcf-a923-494c-acaa-c5836da72e80"))
ENGINE = "a" * 40


class PrivateEngineRouteContractTests(unittest.TestCase):
    def setUp(self):
        self.binding = VerifiedEngineBinding(
            owner_id=OWNER, project_id=PROJECT, mode="stage",
            generation=12, engine_sha=ENGINE, ready=True,
        )
        self.request = dict(owner_id=OWNER, project_id=PROJECT,
                            generation=12, method="GET",
                            path="/api/v1/wizard/status")

    def plan(self, *, binding=None, **changes):
        return plan_private_engine_request(
            self.binding if binding is None else binding,
            **{**self.request, **changes},
        )

    def denied(self, *, binding=None, **changes):
        with self.assertRaises(PrivateEngineRouteDenied):
            self.plan(binding=binding, **changes)

    def test_whitelisted_bodyless_stage_operations(self):
        for path in ("/api/v1/wizard/status", "/api/v1/project",
                     "/api/v1/artifacts/sync"):
            with self.subTest(path=path):
                plan = self.plan(path=path)
                self.assertEqual(plan.owner_id, OWNER)
                self.assertEqual(plan.project_id, PROJECT)
                self.assertEqual(plan.generation, 12)
                self.assertEqual(plan.engine_sha, ENGINE)

    def test_never_trust_foreign_owner_project_or_older_job(self):
        self.denied(owner_id="owner-b")
        self.denied(project_id=OTHER_PROJECT)
        self.denied(generation=11)
        self.denied(generation=True)
        self.denied(binding=replace(self.binding, generation=13))
        self.denied(binding=replace(self.binding, owner_id="owner-b"))
        self.denied(binding=replace(self.binding, project_id=OTHER_PROJECT))
        self.denied(binding=replace(self.binding, ready=False))
        self.denied(binding=replace(self.binding, engine_sha="unverified"))

    def test_mutating_arbitrary_and_encoded_routes_denied(self):
        for method, path in (
            ("POST", "/api/v1/wizard/start"),
            ("POST", "/api/v1/wizard/status"),
            ("GET", "/api/v1/wizard/projects/open"),
            ("GET", "/api/v1/wizard/status?project=other"),
            ("GET", "/api/v1/../admin"),
            ("GET", "/api/v1/%77izard/status"),
            ("GET", "//api/v1/wizard/status"),
            ("GET", "http://localhost:8101/api/v1/wizard/status"),
            ("DELETE", "/api/v1/project"),
            ("get", "/api/v1/project"),
            ("GET", "/api/v1/project/"),
        ):
            with self.subTest(method=method, path=path):
                self.denied(method=method, path=path)

    def test_modes_not_interchangeable(self):
        self.denied(binding=replace(self.binding, mode="show"))
        self.denied(binding=replace(self.binding, mode="push"))
        self.denied(binding=replace(self.binding, mode="music"))
        self.denied(binding=replace(self.binding, mode=""))

    def test_malformed_project_and_invalid_generation_fail_closed(self):
        for bad in ("../../x", PROJECT.upper(), "", None, OTHER_PROJECT):
            with self.subTest(project_id=bad):
                self.denied(project_id=bad)
        self.denied(generation=0)
        self.denied(binding=replace(self.binding, generation="12"))


if __name__ == "__main__":
    unittest.main()
