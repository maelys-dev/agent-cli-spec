# SPDX-License-Identifier: MPL-2.0
"""A default command (sections 1 and 8), proved on the reference fixture with a journal of what its handlers ran.

The fixture declares a default command only when CONFORMANT_DEFAULT names one, and then writes to the file
CONFORMANT_JOURNAL names one line per command that reached its handler: the proof of a call, and of its absence.
The kit cannot do this on a product, whose default command it never runs.
"""
import json
import os
import pathlib
import sys
import tempfile
import unittest

from support import FIXTURE, ROOT, FixtureProgram

sys.path.insert(0, str(ROOT / "conformance"))
from run import SCHEMAS, run_on_terminal  # noqa: E402
from validate import validate  # noqa: E402

SUM = "ab" * 32
DIGEST = f"--sum={SUM}"


class Journal:
    """Runs lines and reads back what reached a handler."""

    def __init__(self, program):
        self.program = program
        self.directory = tempfile.TemporaryDirectory(prefix="agent cli default ")
        self.path = pathlib.Path(self.directory.name) / "journal"

    def run(self, *words):
        self.path.unlink(missing_ok=True)
        done = self.program.run(*words, env={"CONFORMANT_JOURNAL": str(self.path)})
        ran = [json.loads(line) for line in self.path.read_text().splitlines()] if self.path.exists() else []
        return done, ran

    def close(self):
        self.directory.cleanup()


def answer(done):
    """Exit code, error code and the command an envelope names, from the stream that carries it."""
    for stream in (done.stdout, done.stderr):
        try:
            body = json.loads(stream)
        except ValueError:
            continue
        return done.returncode, (body.get("error") or {}).get("code"), body.get("command")
    return done.returncode, None, None


class WithoutADefaultTest(unittest.TestCase):
    def test_a_line_that_starts_with_an_option_is_read_as_before(self):
        """Proof 1: no default declared, nothing changes. The answers of 2.15.1's fixture, line for line."""
        program = FixtureProgram()
        for words, expected in (([], (1, "INVALID_COMMAND", "unknown")), (["--json"], (1, "INVALID_COMMAND", "unknown")),
                                (["--json", "version"], (0, None, "version")),
                                (["--format", "json", "version"], (0, None, "version")),
                                (["--json", "--help"], (0, None, "help")),
                                (["--label", "list", "--json"], (1, "INVALID_COMMAND", "unknown")),
                                (["-h", "--json"], (1, "INVALID_COMMAND", "unknown")),
                                (["-x", "--json"], (1, "INVALID_COMMAND", "unknown")),
                                (["-x", "version", "--json"], (1, "VALIDATION_FAILED", "version")),
                                (["--json", "--version"], (0, None, "version")),
                                (["--json", "describe", "--summary"], (0, None, "describe"))):
            with self.subTest(words=words):
                done = program.run(*words)
                if expected[2] is None or "--json" in words:
                    self.assertEqual(answer(done), expected)
                else:
                    self.assertEqual(done.returncode, expected[0])
        self.assertNotIn("defaultCommand", json.loads(program.run("describe", "--json").stdout)["data"])


class WithADefaultTest(unittest.TestCase):
    def setUp(self):
        self.journal = Journal(FixtureProgram(default="limits"))

    def tearDown(self):
        self.journal.close()

    def test_the_implicit_line_is_the_explicit_one(self):
        """Proof 2: the same handler, the same values, the same answer."""
        for implicit, explicit in (([DIGEST, "--", "near"], ["limits", "near", DIGEST]),
                                   ([DIGEST, "--depth", "3", "--json", "--", "far", "sha1:" + "cd" * 20],
                                    ["limits", "far", "sha1:" + "cd" * 20, DIGEST, "--depth", "3", "--json"]),
                                   ([DIGEST, "--name", "list", "--", "near"], ["limits", "near", DIGEST, "--name", "list"])):
            with self.subTest(implicit=implicit):
                done, ran = self.journal.run(*implicit)
                again, ran_again = self.journal.run(*explicit)
                self.assertEqual((done.returncode, done.stdout, done.stderr), (again.returncode, again.stdout, again.stderr))
                self.assertEqual(ran, ran_again)
                self.assertEqual([entry["command"] for entry in ran], ["limits"])
        # proof 6: the value of an option is that value, a command's name or not
        _, ran = self.journal.run(DIGEST, "--name", "list", "--", "near")
        self.assertEqual((ran[0]["options"]["--name"], ran[0]["operands"]), ("list", ["near"]))
        # an empty line is the default command's too, and is refused for its missing operand as `limits` alone is
        done, ran = self.journal.run()
        self.assertEqual((answer(self.journal.run("--json")[0]), ran), ((1, "VALIDATION_FAILED", "limits"), []))
        self.assertEqual(done.returncode, 1)

    def test_explicit_commands_resolve_as_before(self):
        """Proof 3: a first word that names a command, of one word or several."""
        for words, command in ((["version"], "version"), (["note", "write", "x"], "note.write"),
                               (["limits", "near", DIGEST], "limits")):
            with self.subTest(words=words):
                done, ran = self.journal.run(*words)
                self.assertEqual((done.returncode, [entry["command"] for entry in ran]), (0, [command]))

    def test_what_is_refused_runs_nothing(self):
        """Proofs 4, 5 and 6: an unknown or partial command, and every refusal of the default command's line."""
        for words, code, command in ((["lst", "--json"], "INVALID_COMMAND", "unknown"),
                                     (["note", "--json"], "INVALID_COMMAND", "unknown"),
                                     (["--bogus", "--json"], "VALIDATION_FAILED", "limits"),
                                     ([DIGEST, DIGEST, "--json", "--", "near"], "VALIDATION_FAILED", "limits"),
                                     ([DIGEST, "--depth", "99", "--json", "--", "near"], "VALIDATION_FAILED", "limits"),
                                     ([DIGEST, "--report", "r", "--json", "--", "near"], "VALIDATION_FAILED", "limits"),
                                     ([DIGEST, "--json"], "VALIDATION_FAILED", "limits"),
                                     (["--json", "list"], "VALIDATION_FAILED", "limits"),
                                     (["--json", DIGEST, "near"], "VALIDATION_FAILED", "limits"),
                                     (["-h", "--json"], "VALIDATION_FAILED", "limits"),
                                     (["-x", "--json"], "VALIDATION_FAILED", "limits")):
            with self.subTest(words=words):
                done, ran = self.journal.run(*words)
                self.assertEqual((answer(done), ran), ((1, code, command), []))

    def test_help_version_discovery_and_completion_run_no_command_of_the_product(self):
        """Proof 7: none of these reaches the default command's handler."""
        for words, command in ((["--help"], "help"), ([DIGEST, "--help"], "help"), (["limits", "--help"], "help"),
                               (["--version"], "version"), (["--json", "--version"], "version"),
                               (["--lang", "fr", "--help"], "help"), (["describe", "--json"], "describe"),
                               (["describe", "--summary", "--json"], "describe"),
                               (["__complete", "--", "--"], "complete.candidates"),
                               (["__complete", "--", "--non-interactive", ""], "complete.candidates")):
            with self.subTest(words=words):
                done, ran = self.journal.run(*words)
                self.assertEqual((done.returncode, [entry["command"] for entry in ran]), (0, [command]))
        implicit = self.journal.run(DIGEST, "--help")[0].stdout
        self.assertEqual(implicit, self.journal.run("limits", "--help")[0].stdout)
        self.assertNotEqual(implicit, self.journal.run("--help")[0].stdout)
        self.assertIn("default command: limits", self.journal.run("--help")[0].stdout)
        offered = self.journal.run("__complete", "--", "--")[0].stdout.split()
        self.assertTrue({"--sum", "--depth", "--json"} <= set(offered), offered)

    def test_every_form_of_describe_carries_the_declaration_and_matches_the_schema(self):
        """Proof 11."""
        for words in (["describe"], ["describe", "--summary"], ["describe", "--summary", "--prefix", "note"],
                      ["describe", "version"]):
            with self.subTest(words=words):
                data = json.loads(self.journal.run(*words, "--json")[0].stdout)["data"]
                self.assertEqual(data["defaultCommand"], "limits")
                self.assertEqual(validate(data, SCHEMAS["describe"]), [])


class MigrationTest(unittest.TestCase):
    def test_the_same_program_before_and_after_it_declares_a_default(self):
        """What declaring a default changes, line by line: the answer and what ran, before and after. A line that
        ran can stop (`--json version`); a refusal can become a run; what names a command stays as it was."""
        refused, ran_version = (1, "INVALID_COMMAND", "unknown"), ((0, None, "version"), ["version"])
        for default, words, before, after in (
                ("limits", ["--json"], (refused, []), ((1, "VALIDATION_FAILED", "limits"), [])),
                ("limits", ["--json", "version"], ran_version, ((1, "VALIDATION_FAILED", "limits"), [])),
                ("limits", ["version", "--json"], ran_version, ran_version),
                ("limits", [DIGEST, "--name", "version", "--json", "--", "near"], (refused, []),
                 ((0, None, "limits"), ["limits"])),
                ("limits", ["lst", "--json"], (refused, []), (refused, [])),
                ("limits", ["--version"], ((0, None, None), ["version"]), ((0, None, None), ["version"])),
                ("limits", ["--help"], ((0, None, None), ["help"]), ((0, None, None), ["help"])),
                ("limits", [DIGEST, "--help"], ((1, None, None), []), ((0, None, None), ["help"])),
                ("limits", ["-h", "--json"], (refused, []), ((1, "VALIDATION_FAILED", "limits"), [])),
                ("limits", ["-x", "--json"], (refused, []), ((1, "VALIDATION_FAILED", "limits"), [])),
                ("limits", [DIGEST, "--json", "--", "near"], (refused, []), ((0, None, "limits"), ["limits"])),
                ("serve", ["--json"], (refused, []), ((1, "VALIDATION_FAILED", "serve"), [])),
                ("note.write", ["--", "notes/today.txt"], ((1, None, None), []), ((0, None, None), ["note.write"]))):
            for declared, expected in (("", before), (default, after)):
                program = FixtureProgram(default=declared)
                with self.subTest(default=declared, words=words):
                    journal = Journal(program)
                    try:
                        done, ran = journal.run(*words)
                    finally:
                        journal.close()
                    self.assertEqual((answer(done), [entry["command"] for entry in ran]), expected)
        # an empty line: refused before, the default's own refusal after, its missing operand; nothing ran either way
        for program in (FixtureProgram(), FixtureProgram(default="limits")):
            journal = Journal(program)
            try:
                done, ran = journal.run()
            finally:
                journal.close()
            self.assertEqual((done.returncode, ran), (1, []))
        self.assertIn("a line that starts with an option is its",
                      FixtureProgram(default="limits").run("--help").stdout)


class WhatMayBeTheDefaultTest(unittest.TestCase):
    def test_a_catalog_that_declares_another_is_refused_before_anything_runs(self):
        """Proof 8: a command that does not exist, cannot run, is hidden, belongs to section 6, is a delegate, or
        is an `execute` command."""
        for default in ("no.such", "offline", "complete.candidates", "help", "completion.install", "tool", "stamp"):
            journal = Journal(FixtureProgram(default=default))
            try:
                for words in ([], ["version", "--json"], ["describe", "--json"], ["stamp", "--json"], ["--help"]):
                    with self.subTest(default=default, words=words):
                        done, ran = journal.run(*words)
                        self.assertEqual((done.returncode, ran), (1, []))
                        self.assertIn("UNEXPECTED", done.stderr)
            finally:
                journal.close()

    def test_a_transaction_as_default_plans_without_apply(self):
        """Proof 9."""
        journal = Journal(FixtureProgram(default="note.write"))
        try:
            done, ran = journal.run("--", "notes/today.txt")
            self.assertEqual((done.stdout, ran[0]["operands"], "--apply" in ran[0]["options"]),
                             ("note: plan\n", ["notes/today.txt"], False))
            done, ran = journal.run("--apply", "--", "notes/today.txt")
            self.assertEqual((done.stdout, ran[0]["options"]["--apply"]), ("note: apply\n", True))
        finally:
            journal.close()

    @unittest.skipUnless(os.name == "posix", "pseudo-terminals are POSIX")
    def test_a_stream_as_default_keeps_its_bytes_on_a_terminal(self):
        """Proof 10: the protocol's bytes and nothing else, the same as `serve`; a rendering option is refused."""
        env = {**os.environ, "CONFORMANT_DEFAULT": "serve", "NO_COLOR": "1"}
        argv = [sys.executable, str(FIXTURE)]
        with tempfile.TemporaryDirectory() as directory:
            implicit = run_on_terminal(argv, env, directory, 10)
            explicit = run_on_terminal(argv + ["serve"], env, directory, 10)
        self.assertEqual(implicit, (0, '{"jsonrpc":"2.0","method":"ready"}\n'))
        self.assertEqual(implicit, explicit)
        self.assertEqual(answer(FixtureProgram(default="serve").run("--json")), (1, "VALIDATION_FAILED", "serve"))


if __name__ == "__main__":
    unittest.main()
