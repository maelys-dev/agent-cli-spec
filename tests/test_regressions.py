# SPDX-License-Identifier: MPL-2.0
import contextlib
import copy
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

from support import FixtureProgram, ROOT

sys.path.insert(0, str(ROOT / "conformance"))
from run import Program, Report, SCHEMAS, check_jsonl, envelope, field_jsonl, field_text, main, run_kit, text_records
from validate import json_equal, unsupported_keywords, validate


class ValidatorRegressionTest(unittest.TestCase):
    def test_json_equality_and_integer_values(self):
        for a, b in ((True, 1), (False, 0), ([True], [1]), ({"a": False}, {"a": 0})):
            with self.subTest(a=a, b=b):
                self.assertFalse(json_equal(a, b))
                self.assertTrue(validate(a, {"const": b}))
                self.assertTrue(validate(a, {"enum": [b]}))
        self.assertFalse(validate({"a": [1.0]}, {"const": {"a": [1]}}))
        self.assertFalse(validate(1.0, {"type": "integer"}))
        for value in (True, 1.5, float("nan"), float("inf")):
            self.assertTrue(validate(value, {"type": "integer"}))

    def test_lengths_and_overlapping_property_rules(self):
        self.assertTrue(validate("", {"type": "string", "minLength": 1}))
        self.assertFalse(validate("é", {"type": "string", "minLength": 1, "maxLength": 1}))
        self.assertTrue(validate("ab", {"maxLength": 1}))
        schema = {"properties": {"name": {"type": "string"}}, "patternProperties": {"^n": {"minLength": 2}}}
        self.assertTrue(validate({"name": "a"}, schema))

    def test_local_refs_keep_siblings_and_decode_pointer(self):
        schema = {"$ref": "#/$defs/a~1b~0c", "minLength": 2, "$defs": {"a/b~c": {"type": "string"}}}
        self.assertTrue(validate("x", schema))
        self.assertFalse(validate("xy", schema))
        self.assertFalse(validate("xy", {"$ref": "#/$defs/a%20b", "$defs": {"a b": {"type": "string"}}}))
        self.assertFalse(validate("xy", {"$ref": "#/allOf/0", "allOf": [{"type": "string"}]}))
        self.assertTrue(validate(1, False))
        self.assertFalse(validate(1, True))
        self.assertTrue(validate(1, {"oneOf": [{}, {}]}))

    def test_supported_keywords_cover_every_embedded_schema(self):
        for name, schema in SCHEMAS.items():
            self.assertEqual(unsupported_keywords(schema), [], name)
        self.assertEqual(unsupported_keywords({"properties": {"format": {"type": "string"}},
                                               "const": {"unknown": 1}}), [])
        self.assertEqual(unsupported_keywords({"properties": {"x": {"format": "date"}}}), [])
        self.assertEqual(unsupported_keywords({"pattern": "^(?<major>[0-9]+)\\."}), [])
        self.assertFalse(validate("12.", {"pattern": "^(?<major>[0-9]+)\\."}))
        self.assertTrue(unsupported_keywords({"pattern": "^\\p{L}+$"}))
        self.assertTrue(unsupported_keywords({"patternProperties": {"[": {}}}))
        self.assertTrue(unsupported_keywords({"$schema": "http://json-schema.org/draft-07/schema#"}))
        self.assertTrue(unsupported_keywords({"$defs": {"child": {"$id": "child.json", "type": "string"}}}))

    def test_conditional_describe_forms(self):
        document = json.loads(FixtureProgram().run("describe", "--json").stdout)["data"]
        self.assertFalse(validate(document, SCHEMAS["describe"]))
        for missing in ("globalOptions", "invariants", "output"):
            changed = copy.deepcopy(document)
            changed.pop(missing)
            self.assertTrue(validate(changed, SCHEMAS["describe"]))
        for missing in ("outputSchema", "exitCodes"):
            changed = copy.deepcopy(document)
            changed["commands"][0].pop(missing)
            self.assertTrue(validate(changed, SCHEMAS["describe"]))
        self.assertTrue(validate({**document, "kind": "summary"}, SCHEMAS["describe"]))
        one = {key: value for key, value in document.items() if key not in ("globalOptions", "invariants", "output")}
        one.update(kind="command", commands=[document["commands"][0]])
        self.assertFalse(validate(one, SCHEMAS["describe"]))
        for commands in ([], document["commands"]):
            self.assertTrue(validate({**one, "commands": commands}, SCHEMAS["describe"]))

    def test_descriptor_conditions_and_extensions(self):
        schema = {"$ref": "#/definitions/descriptor"}
        command = FixtureProgram().fixture.CATALOG[0]
        self.assertTrue(validate({**command, "available": False}, schema, SCHEMAS["describe"]))
        self.assertFalse(validate({**command, "effect": "stream", "outputMode": "protocol-stream"}, schema, SCHEMAS["describe"]))
        self.assertTrue(validate({**command, "effect": "stream", "outputMode": "json-envelope"}, schema, SCHEMAS["describe"]))
        transaction = {**command, "effect": {"plan": "preview", "apply": "apply", "x-proof": "id"}}
        self.assertFalse(validate(transaction, schema, SCHEMAS["describe"]))
        self.assertTrue(validate({"name": "PICK", "type": "choice"},
                                 {"$ref": "#/definitions/argument"}, SCHEMAS["describe"]))


class KitRegressionTest(unittest.TestCase):
    def test_unavailable_completion_and_unknown_schema_are_not_false_failures(self):
        program = FixtureProgram()
        program.fixture.CATALOG[1]["outputSchema"] = {"type": "object", "unevaluatedProperties": True}
        report = run_kit(program)
        self.assertTrue(report.passed, report.checks)
        self.assertTrue(any(check["passed"] is None and "unsupported" in check["detail"] for check in report.checks))
        self.assertTrue(any("omits hidden and unavailable" in check["name"] and check["passed"] for check in report.checks))

    def test_ecma_pattern_is_skipped_not_failed(self):
        program = FixtureProgram()
        program.fixture.CATALOG[1]["outputSchema"] = {"type": "object", "properties": {"version": {"pattern": "^\\p{L}"}}}
        report = run_kit(program)
        self.assertTrue(report.passed, [check for check in report.checks if check["passed"] is False])
        self.assertTrue(any(check["passed"] is None and "regex not supported" in check["detail"] for check in report.checks))

    def test_malformed_schemas_are_reported(self):
        for schema in ({"properties": []}, {"$ref": "#/missing"}, {"$ref": "#"},
                       {"type": "unknown"}, {"$ref": "#/allOf/1", "allOf": [{}]}):
            program = FixtureProgram()
            program.fixture.CATALOG[1]["outputSchema"] = schema
            report = run_kit(program)
            self.assertFalse(report.passed, schema)

    def test_product_global_shape_and_trunk_default_disagreement(self):
        program = FixtureProgram()
        option = program.fixture.option("--identity", "Identity.", {"name": "ID", "type": "string"})
        program.fixture.GLOBAL_OPTIONS.append(option)
        program.fixture.CATALOG[1]["input"]["options"].append({**option, "argument": {"name": "ID", "type": "integer"}})
        report = run_kit(program)
        self.assertTrue(any(check["passed"] is False and "product global declaration" in check["name"] for check in report.checks))
        program = FixtureProgram()
        next(item for item in program.fixture.GLOBAL_OPTIONS if item["long"] == "--progress")["default"] = "never"
        report = run_kit(program)
        self.assertTrue(any(check["passed"] is False and "contract's default" in check["name"] for check in report.checks))

    def test_bad_responses_are_reported_without_losing_remaining_checks(self):
        for target, data in (("describe", {"commands": [None]}), ("help", {"text": "help", "commands": None}),
                             ("__complete", {"count": 1, "records": [3]})):
            def transform(args, result):
                if args[0] == target and "json" in args:
                    body = json.loads(result.stdout)
                    body["data"] = data
                    result.stdout = json.dumps(body)
                return result
            report = run_kit(FixtureProgram(transform=transform))
            self.assertFalse(report.passed, (target, report.checks))
            if target != "describe":
                self.assertTrue(any("unknown command fails" in check["name"] for check in report.checks))

    def test_failure_json_and_non_json_constants_are_rejected(self):
        for text in ("not JSON", "null", "[]", '{"value": NaN}', '{"value": Infinity}'):
            report = Report()
            completed = subprocess.CompletedProcess([], 1, "", text)
            self.assertIsNone(envelope(report, "failure", completed, False))
            self.assertFalse(report.passed)

    def test_pipe_records_and_escaping(self):
        records = [{"z": {"inner": "\t"}, "a": "a\tb\nc\r\\", "n": None, "b": False},
                   {"a": "", "b": 2, "z": [1, True]}]
        expected = 'a\\tb\\nc\\r\\\\\tfalse\tnull\t{"inner":"\\t"}\n\t2\t\t[1,true]\n'
        self.assertEqual(text_records(records), expected)
        self.assertEqual(FixtureProgram().fixture.record_text(records), expected)
        self.assertEqual(text_records([{}]), "\n")
        self.assertEqual(text_records([]), "")
        for renderer in (text_records, FixtureProgram().fixture.record_text):
            self.assertEqual(renderer([{"a": "\x1b[31m\x00\x7f"}]), "\\u001b[31m\\u0000\\u007f\n")

    def test_field_renders_every_shape_the_same_in_both_implementations(self):
        fixture = FixtureProgram().fixture
        for value, text, lines in (
                ([{"b": 1, "a": "x"}, {"a": "", "c": None}], "x\t1\t\n\t\tnull\n", '{"b":1,"a":"x"}\n{"a":"","c":null}\n'),
                (["a\tb", "c"], "a\\tb\nc\n", '"a\\tb"\n"c"\n'),
                ([1, {"a": 2}], '1\n{"a":2}\n', '1\n{"a":2}\n'),
                ([], "", ""),
                ({"z": True, "a": "v"}, "v\ttrue\n", '{"z":true,"a":"v"}\n'),
                ("plain", "plain\n", '"plain"\n'),
                (0, "0\n", "0\n"),
                (None, "null\n", "null\n"),
        ):
            with self.subTest(value=value):
                self.assertEqual(field_text(value), text)
                self.assertEqual(fixture.field_text(value), text)
                self.assertEqual(field_jsonl(value), lines)

    def test_jsonl_compares_records_and_types_not_only_line_count(self):
        for output in ('{"word":"other"}\n', 'garbage\n', 'true\n', '{"word":"a"}\n\n'):
            report = Report()
            check_jsonl(report, "records", subprocess.CompletedProcess([], 0, output, ""), [{"word": "a"}])
            self.assertFalse(report.passed)
        report = Report()
        record = {"word": "before\u2028after"}
        check_jsonl(report, "unicode", subprocess.CompletedProcess([], 0, json.dumps(record, ensure_ascii=False) + "\n", ""), [record])
        self.assertTrue(report.passed)

    def test_fixture_flags_and_duplicates(self):
        program = FixtureProgram()
        for arguments in (("version", "--verbose", "--verbose"),
                          ("version", "--progress=auto", "--progress=never"),
                          ("version", "--pager=always", "--pager=always")):
            completed = program.run(*arguments, "--json")
            self.assertEqual(completed.returncode, 1)
            self.assertEqual(json.loads(completed.stderr)["error"]["code"], "VALIDATION_FAILED")
        result = program.run("note", "write", "a-file", "--apply=false", "--json")
        self.assertEqual(json.loads(result.stdout)["data"]["mode"], "plan")

    def test_real_kit_reports_jsonl_corruption_as_json(self):
        completed = subprocess.run([sys.executable, str(ROOT / "conformance/run.py"), sys.executable,
                                    str(ROOT / "tests/fixtures/conformant.py"), "--json"],
                                   env={**os.environ, "CONFORMANT_BREAK": "malformed-jsonl"},
                                   capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertEqual(completed.stderr, "")
        self.assertFalse(json.loads(completed.stdout)["passed"])

    def test_kit_argument_errors(self):
        for arguments in (("--timeout",), ("--report",), ("--timeout", "nan"), ("--timeout", "0")):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(list(arguments)), 2)


class ProcessTest(unittest.TestCase):
    def test_stdin_is_closed_and_invalid_utf8_is_reported(self):
        program = Program([sys.executable, "-c", "import sys; print(len(sys.stdin.read()))"])
        self.assertEqual(program.run().stdout, "0\n")
        program = Program([sys.executable, "-c", "import sys; sys.stdout.buffer.write(bytes([255]))"])
        self.assertEqual(program.run().returncode, -1)
        self.assertIn("UTF-8", program.failures[0])

    def test_timeout_produces_a_json_report(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main([sys.executable, "-c", "import time; time.sleep(10)", "--timeout", "0.1", "--json"])
        self.assertEqual(code, 1)
        report = json.loads(stdout.getvalue())
        self.assertFalse(report["passed"])
        self.assertTrue(any("timed out" in check["detail"] for check in report["checks"]))

    @unittest.skipUnless(os.name == "posix", "process groups are POSIX")
    def test_timeout_does_not_wait_for_a_grandchild_in_another_session(self):
        child = "import time; time.sleep(6)"
        parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}], start_new_session=True); time.sleep(10)"
        program = Program([sys.executable, "-c", parent], timeout=0.3)
        started = time.monotonic()
        self.assertEqual(program.run().returncode, -1)
        self.assertLess(time.monotonic() - started, 3)

    @unittest.skipUnless(os.name == "posix", "process groups are POSIX")
    def test_timeout_kills_children_holding_the_pipes(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = pathlib.Path(directory) / "child-survived"
            child = f"import pathlib,time; time.sleep(1); pathlib.Path({str(marker)!r}).touch()"
            parent = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(10)"
            program = Program([sys.executable, "-c", parent], timeout=0.5)
            self.assertEqual(program.run().returncode, -1)
            time.sleep(1.1)
            self.assertFalse(marker.exists())
