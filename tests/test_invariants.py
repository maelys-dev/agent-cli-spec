# SPDX-License-Identifier: MPL-2.0
"""The reference program against generated command lines: see invocations.py."""
import collections
import contextlib
import io
import json
import pathlib
import random
import shutil
import sys
import tempfile
import unittest

from support import FIXTURE, FixtureProgram
import invocations

# What the reference program still does that the contract forbids, each with the reason it stands. A gap
# that closes fails the test until its line is removed, so the list cannot outlive what it records.
KNOWN_GAPS: dict[str, str] = {}


def survey(program, count: int, defaults=("text",)) -> dict[str, list[str]]:
    """Every generated line run in a home of its own; the lines found at fault, by what they break. `defaults`
    are the formats the environment selects in turn, CONFORMANT_FORMAT being the fixture's variable for it."""
    catalog = json.loads(program.run("describe", "--json").stdout)["data"]
    found: dict[str, list[str]] = collections.defaultdict(list)
    for words in invocations.unknown_lines():
        for violation in invocations.unknown_violations(words, program.run(*words)):
            found[violation.split(": ", 1)[0]].append(" ".join(words))
    with tempfile.TemporaryDirectory(prefix="agent cli lines ") as directory:
        home = pathlib.Path(directory) / "home"
        for default in defaults:
            rng = random.Random(2130)
            for command in catalog["commands"]:
                built = invocations.lines(command, rng, count)
                # a delegate starts a child for each line, and the catalog says nothing of what follows its pattern
                for words in built[:8] if command.get("external") else built:
                    if invocations.open_reading(invocations.given(command, catalog["globalOptions"], words), default):
                        continue
                    shutil.rmtree(home, ignore_errors=True)
                    home.mkdir()
                    env = {"HOME": str(home), "XDG_DATA_HOME": "", "XDG_CONFIG_HOME": "", "ZDOTDIR": "",
                           "CONFORMANT_FORMAT": default}
                    completed = program.run(*words, env=env)
                    written = sorted(str(path.relative_to(home)) for path in home.rglob("*") if path.is_file())
                    for violation in invocations.violations(command, catalog["globalOptions"], words, completed, written,
                                                            reference=True, default=default):
                        name, detail = violation.split(": ", 1)
                        found[f"accepts {detail}" if name == "accepts" else name].append(
                            " ".join(words) + ("" if default == "text" else f"  [default {default}]"))
    return found


def implicit_survey(default: str) -> dict[str, list[str]]:
    """Section 8: every line of the default command written without its pattern, against the line after it."""
    program = FixtureProgram(default=default)
    catalog = json.loads(program.run("describe", "--json").stdout)["data"]
    command = next(entry for entry in catalog["commands"] if entry["id"] == default)
    found: dict[str, list[str]] = collections.defaultdict(list)
    for implicit, explicit in invocations.implicit_lines(command, catalog["globalOptions"],
                                                         invocations.lines(command, random.Random(2130), 10)):
        done = program.run(*implicit)
        again = program.run(*explicit) if explicit is not None else None
        for violation in invocations.implicit_violations(default, implicit, done, again):
            found[violation.split(": ", 1)[0]].append(" ".join(implicit))
    return found


class GeneratedInvocationsTest(unittest.TestCase):
    def test_a_line_that_names_no_command_answers_as_the_default_command_does(self):
        """For a default that reads and one that plans: each implicit line answers as the same words after the
        pattern, and a bare word before `--` is refused in the default command's name. A stream is never run by
        the generated lines; test_default_command holds one on a terminal."""
        for default in ("limits", "note.write"):
            with self.subTest(default=default):
                self.assertEqual(dict(implicit_survey(default)), {})
        broken = FixtureProgram("default-bare-absorbed", default="limits")
        catalog = json.loads(broken.run("describe", "--json").stdout)["data"]
        command = next(entry for entry in catalog["commands"] if entry["id"] == "limits")
        pairs = invocations.implicit_lines(command, catalog["globalOptions"], invocations.lines(command, random.Random(2130), 2))
        absorbed = [implicit for implicit, explicit in pairs if explicit is None
                    and invocations.implicit_violations("limits", implicit, broken.run(*implicit), None)]
        self.assertTrue(absorbed, "the defect that takes a bare word for an operand is not seen")

    def test_a_word_an_option_takes_as_its_value_is_no_option(self):
        """`--report --help` gives --report the value `--help`: the line asks no help, and `--report --json` asks no
        JSON. The judge once read both words as options and found fault with right answers."""
        program = FixtureProgram()
        catalog = json.loads(program.run("describe", "--json").stdout)["data"]
        command = next(entry for entry in catalog["commands"] if entry["id"] == "limits")
        self.assertEqual(invocations.given(command, catalog["globalOptions"],
                                           ["limits", "near", "--report", "--help", "--json=true", "--", "--apply"]),
                         [("--report", "--help"), ("--json", "true")])
        for tail in (["--report", "--help", "--json"], ["--report", "--json"], ["--report", "--format", "--json"],
                     ["--depth", "--help"]):
            with self.subTest(tail=tail):
                words = ["limits", "near", "--sum=" + "ab" * 32, *tail]
                self.assertEqual(invocations.violations(command, catalog["globalOptions"], words,
                                                        program.run(*words), []), [])

    def test_a_spent_budget_is_an_incomplete_campaign_and_no_pass(self):
        """What ran is reported, the campaign is said incomplete, and the exit is 3, never 0."""
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            code = invocations.main(["--budget", "1", "--timeout", "5", sys.executable, str(FIXTURE)])
        self.assertEqual(code, 3, printed.getvalue())
        self.assertIn("campaign incomplete: the budget of 1 seconds ran out after", printed.getvalue())
        self.assertTrue(printed.getvalue().endswith("nothing found in what ran\n"), printed.getvalue())

    def test_a_bare_word_is_never_put_where_it_is_a_value(self):
        """`PROGRAM --label kit-bare-word` gives --label its value: the line is right, and is not one to refuse."""
        command = {"pattern": ["show"], "input": {"options": [{"long": "--label", "argument": {"kind": "string"}},
                                                             {"long": "--all"}]}}
        bare = {tuple(words): None for words, explicit in invocations.implicit_lines(
            command, [], [["show", "--label"], ["show", "--label", "x", "--all"], ["show", "--all", "--label", "y"]])
            if explicit is None}
        self.assertEqual(list(bare), [("--label", "x", "kit-bare-word", "--all"),
                                      ("--all", "kit-bare-word", "--label", "y")])

    def test_the_fixture_does_what_the_contract_says_of_every_generated_line(self):
        """Some nine hundred lines built from the fixture's own catalog. Two defects of the fixture were found by
        accident before this existed: it wrote before it refused --field, and it ran a command under --help."""
        found = survey(FixtureProgram(), count=40, defaults=("text", "json"))
        unexpected = {name: lines[:3] for name, lines in found.items() if name not in KNOWN_GAPS}
        self.assertEqual(unexpected, {})
        self.assertEqual([name for name in KNOWN_GAPS if name not in found], [], "a known gap is closed: remove it")

    def test_the_generated_lines_find_the_defects_they_are_for(self):
        """The invariants bite: each of these defects of the fixture shows as the violation named."""
        clean = set(survey(FixtureProgram(), count=1))
        for defect, expected in (("help-runs", "help-writes"), ("field-after-write", "failure-writes"),
                                 ("expect-after-write", "failure-writes"), ("install-plan-writes", "plan-writes"),
                                 ("text-on-stderr", "success-stderr"), ("empty-command", "envelope-command"),
                                 ("help-names-command", "envelope-command"), ("envelope-types", "envelope"),
                                 ("verbose-json", "success-stderr"),
                                 ("arity-unchecked", "accepts a wrong number of operands"),
                                 ("version-ignored", "accepts --version after a command"),
                                 ("help-checks-arity", "help-refused"), ("help-jsonl-silent", "help-jsonl"),
                                 ("unavailable-runs", "unavailable-runs"),
                                 ("unavailable-after-rendering", "unavailable-order"),
                                 ("kinds-unchecked", "accepts a value that is not of the declared kind"),
                                 ("whole-line-unchecked", "accepts a broken constraint")):
            with self.subTest(defect=defect):
                self.assertIn(expected, set(survey(FixtureProgram(defect), count=1)) - clean)

    def test_the_fixture_hands_a_delegate_its_line_and_keeps_a_stream_its_stdout(self):
        """Section 9. Until 2.14.0 the fixture's delegate parsed its line and answered with an envelope, and its
        stream command accepted every rendering option."""
        program = FixtureProgram()
        for words in (["--json", "--format", "bogus"], ["--help"], ["--version", "--no-such-option"], ["--", "ls", "-la"]):
            handed = program.run("tool", *words)
            self.assertEqual((handed.returncode, handed.stdout, handed.stderr), (0, " ".join(["child:", *words]) + "\n", ""))
        self.assertEqual(program.run("tool", "--fail").returncode, 7)
        self.assertEqual((program.run("serve").returncode, program.run("serve").stdout),
                         (0, '{"jsonrpc":"2.0","method":"ready"}\n'))
        for words in (["--format", "json"], ["--json"], ["--compact"], ["--pretty"], ["--pager", "never"], ["--field", "x"]):
            refused = program.run("serve", *words)
            self.assertEqual((refused.returncode, refused.stdout), (1, ""), words)
            self.assertIn("VALIDATION_FAILED", refused.stderr)
        for words in (["--verbose"], ["--progress", "never"], ["--color", "never"], ["--non-interactive"]):
            self.assertEqual(program.run("serve", *words).returncode, 0, words)
        self.assertIn("serve", program.run("serve", "--help").stdout)

    def test_a_line_is_judged_as_the_catalog_says(self):
        """The generator and the judge on one small command: what is built is valid, and each fault is seen."""
        command = {"id": "push", "pattern": ["push"], "external": False, "outputMode": "json-envelope", "effect": "read",
                   "outputSchema": {"type": "object"},
                   "input": {"passthrough": False, "constraints": [],
                             "operands": [{"name": "TARGET", "required": True, "variadic": False, "type": "choice",
                                           "choices": ["near", "far"]}],
                             "options": [{"long": "--depth", "required": False, "repeatable": False, "summary": "s",
                                          "requires": [], "conflictsWith": [],
                                          "argument": {"name": "N", "type": "unsigned", "maximum": 8}}]}}
        self.assertEqual(invocations.valid_value(command["input"]["operands"][0]), "near")
        wrong = invocations.invalid_value(command["input"]["options"][0]["argument"])
        self.assertEqual(wrong, "no-such-choice")
        built = invocations.lines(command, random.Random(1), count=20)
        self.assertEqual(built[0], ["push", "near"])
        self.assertIn(["push"], built)
        self.assertIn(["push", "near", "--depth", wrong], built)

        def run(words, code, out="", err=""):
            completed = type("Completed", (), {"returncode": code, "stdout": out, "stderr": err})()
            return [item.split(":")[0]
                    for item in invocations.violations(command, [], words, completed, [], reference=True)]
        refusal = "push: [VALIDATION_FAILED] no\n"
        self.assertEqual(run(["push", "near"], 0, out="ok\n"), [])
        self.assertEqual(run(["push"], 1, err=refusal), [])
        self.assertEqual(run(["push"], 0, out="ok\n"), ["accepts"])
        self.assertEqual(run(["push", "near", "--depth", wrong], 0, out="ok\n"), ["accepts"])
        self.assertEqual(run(["push", "near", "--depth", "9"], 0, out="ok\n"), ["accepts"])
        self.assertEqual(run(["push", "near", "--depth", "8"], 0, out="ok\n"), [])
        self.assertEqual(run(["push", "near"], 1, err=refusal), ["refuses"])
        self.assertEqual(run(["push", "near"], 1, out="half\n", err=refusal), ["failure-stdout", "refuses"])
        self.assertEqual(run(["push", "near"], 0), ["success-silent"])
        self.assertEqual(run(["push", "near"], 3, out="ok\n"), ["exit"])


if __name__ == "__main__":
    unittest.main()
