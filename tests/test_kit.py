# SPDX-License-Identifier: MPL-2.0
"""Tests of the conformance kit: the validator, the schemas on the example
contract, the kit on a conformant fixture and on deliberately broken ones."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "conformance"))
from validate import validate  # noqa: E402
from run import run_kit  # noqa: E402
from support import FixtureProgram  # noqa: E402

KIT = ROOT / "conformance" / "run.py"
FIXTURE = ROOT / "tests" / "fixtures" / "conformant.py"
SCHEMAS = {name: json.loads((ROOT / "schemas" / f"{name}.json").read_text()) for name in ("describe", "envelope", "version", "records")}


def kit(*arguments: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(KIT), *arguments], env={**os.environ, **(env or {})}, check=False,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class ValidatorTest(unittest.TestCase):
    def test_types_and_members(self) -> None:
        schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer", "minimum": 1}},
                  "patternProperties": {"^x-": {}}, "additionalProperties": False}
        self.assertEqual(validate({"a": 1, "x-extra": [1]}, schema), [])
        self.assertEqual([issue.message for issue in validate({"a": 0}, schema)], ["0 is below 1"])
        self.assertIn("missing member 'a'", repr(validate({}, schema)))
        self.assertIn("member not allowed", repr(validate({"a": 1, "b": 2}, schema)))
        self.assertIn("expected integer", repr(validate({"a": True}, schema)))

    def test_ref_enum_const_oneof(self) -> None:
        schema = {"oneOf": [{"$ref": "#/definitions/yes"}, {"$ref": "#/definitions/no"}],
                  "definitions": {"yes": {"type": "object", "properties": {"ok": {"const": True}}, "required": ["ok"]},
                                  "no": {"type": "object", "properties": {"ok": {"const": False}}, "required": ["ok"]}}}
        self.assertEqual(validate({"ok": True}, schema), [])
        self.assertTrue(validate({"ok": "maybe"}, schema))
        self.assertTrue(validate("x", {"enum": ["a", "b"]}))
        self.assertTrue(validate([1, "a"], {"type": "array", "items": {"type": "integer"}}))

    def test_example_contract_matches_the_descriptor_schema(self) -> None:
        # maelys-cli's committed contract, at the trunk of the tag maelys-cli pins (2.2.1: no --progress,
        # --verbose nor --pager yet, so the kit would fail it on "catalog lists the global options").
        # The schema checks the shape of the document, not the presence of the trunk options; the kit does.
        example = json.loads((ROOT / "examples" / "maelys-cli.contract.json").read_text())
        for program in example["programs"].values():
            document = {**program, "version": "0.0.0", "framework": "example"}
            self.assertEqual(validate(document, SCHEMAS["describe"]), [], program["program"])

    def test_envelope_schema(self) -> None:
        success = {"schemaVersion": 2, "contract": "agent-cli/v2", "command": "x", "ok": True, "exitCode": 0, "data": {}}
        failure = {"schemaVersion": 2, "contract": "agent-cli/v2", "command": "x", "ok": False, "exitCode": 1,
                   "error": {"code": "NOT_FOUND", "message": "m", "hint": "h", "issues": [{"code": "c", "message": "m", "path": "a.b"}]}}
        self.assertEqual(validate(success, SCHEMAS["envelope"]), [])
        self.assertEqual(validate(failure, SCHEMAS["envelope"]), [])
        self.assertTrue(validate({**success, "ok": False}, SCHEMAS["envelope"]))
        self.assertTrue(validate({**failure, "exitCode": 0}, SCHEMAS["envelope"]))
        self.assertTrue(validate({**success, "extra": 1}, SCHEMAS["envelope"]))

    def test_filtered_summary_schema(self) -> None:
        example = json.loads((ROOT / "examples" / "maelys-cli.contract.json").read_text())
        document = {**example["programs"]["maelys"], "version": "0.0.0", "framework": "example",
                    "kind": "summary", "filter": {"kind": "command-prefix", "value": "agents"}}
        document.pop("globalOptions", None)
        document.pop("invariants", None)
        document.pop("output", None)
        document["commands"] = [
            {key: value for key, value in command.items() if key not in ("outputSchema", "exitCodes")}
            for command in document["commands"]
            if command["id"] == "agents" or command["id"].startswith("agents.")
        ]
        self.assertTrue(document["commands"], "the example must contain the agents namespace")
        self.assertEqual(validate(document, SCHEMAS["describe"]), [])
        self.assertTrue(validate({**document, "filter": {"kind": "command-prefix", "value": "agents."}},
                                 SCHEMAS["describe"]))
        self.assertTrue(validate({**document, "filter": {"kind": "command-prefix", "value": "Agents"}},
                                 SCHEMAS["describe"]))

    def test_hidden_option_schema(self) -> None:
        example = json.loads((ROOT / "examples" / "maelys-cli.contract.json").read_text())
        document = {**example["programs"]["maelys"], "version": "0.0.0", "framework": "example", "kind": "catalog"}
        options = document["commands"][0]["input"]["options"]
        hidden = {"long": "--trace", "required": False, "repeatable": False, "summary": "Trace.",
                  "requires": [], "conflictsWith": [], "hidden": True}
        document["commands"][0]["input"]["options"] = [*options, hidden]
        self.assertEqual(validate(document, SCHEMAS["describe"]), [])
        document["commands"][0]["input"]["options"] = [*options, {**hidden, "hidden": "yes"}]
        self.assertTrue(validate(document, SCHEMAS["describe"]))


class KitTest(unittest.TestCase):
    def test_conformant_fixture_passes(self) -> None:
        completed = kit(sys.executable, str(FIXTURE))
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("conformance: ", completed.stdout)
        self.assertFalse([line for line in completed.stdout.splitlines() if line.startswith("FAIL ")])
        report = kit(sys.executable, str(FIXTURE), "--json")
        body = json.loads(report.stdout)
        self.assertTrue(body["passed"])
        self.assertGreater(body["counts"]["passed"], 40)
        self.assertEqual(body["counts"]["failed"], 0)

    def test_broken_fixtures_fail(self) -> None:
        for defect, expected in (("exit-codes", "matches schemas/describe.json"),
                                 ("extra-member", "matches schemas/describe.json"),
                                 ("code-drift", "INVALID_COMMAND"),
                                 ("hidden-leak", "hidden option"),
                                 ("text-on-stderr", "text success"),
                                 ("verbose-json", "--verbose writes nothing"),
                                 ("progress-json", "--progress always writes nothing"),
                                 ("header-in-pipe", "one plain line per record"),
                                 ("envelope-types", "describe envelope"),
                                 ("empty-command", "describe envelope"),
                                 ("missing-output-schema", "matches schemas/describe.json"),
                                 ("output-schema", "declared outputSchema"),
                                 ("malformed-catalog", "matches schemas/describe.json"),
                                 ("jsonl-noise", "preserves records"),
                                 ("malformed-jsonl", "records"),
                                 ("text-garbage", "one plain line per record"),
                                 ("pager-in-pipe", "never starts a pager"),
                                 ("field-silent", "does not carry")):
            with self.subTest(defect=defect):
                report = run_kit(FixtureProgram(defect))
                self.assertFalse(report.passed)
                failed = [check["name"] for check in report.checks if check["passed"] is False]
                self.assertTrue(any(expected in name for name in failed), failed)

    def test_unrunnable_program(self) -> None:
        self.assertEqual(kit("/nonexistent/program").returncode, 2)


if __name__ == "__main__":
    unittest.main()
