# SPDX-License-Identifier: MPL-2.0
"""The reference program against generated command lines: see invocations.py."""
import collections
import json
import pathlib
import random
import shutil
import tempfile
import unittest

from support import FixtureProgram
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
                for words in invocations.lines(command, rng, count):
                    if invocations.open_reading(words, default):
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


class GeneratedInvocationsTest(unittest.TestCase):
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
                                 ("unavailable-after-rendering", "unavailable-order")):
            with self.subTest(defect=defect):
                self.assertIn(expected, set(survey(FixtureProgram(defect), count=1)) - clean)

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
