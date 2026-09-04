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
        for defect, expected in (("exit-codes", "exit codes are the contract's"),
                                 ("extra-member", "matches schemas/describe.json"),
                                 ("code-drift", "INVALID_COMMAND")):
            with self.subTest(defect=defect):
                completed = kit(sys.executable, str(FIXTURE), "--json", env={"CONFORMANT_BREAK": defect})
                self.assertEqual(completed.returncode, 1)
                failed = [check["name"] for check in json.loads(completed.stdout)["checks"] if not check["passed"]]
                self.assertTrue(any(expected in name for name in failed), failed)

    def test_unrunnable_program(self) -> None:
        self.assertEqual(kit("/nonexistent/program").returncode, 2)


if __name__ == "__main__":
    unittest.main()
