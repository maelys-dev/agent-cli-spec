# SPDX-License-Identifier: MPL-2.0
"""What a refusal names (section 8): the codes the kit cannot reach on built-in commands, on the fixture's `limits`."""
import json
import unittest

from support import FixtureProgram

SUM = "--sum=" + "ab" * 32


def issues(done):
    return json.loads(done.stderr)["error"].get("issues")


class RefusalIssuesTest(unittest.TestCase):
    def test_the_rules_of_several_options_and_the_values_of_an_operand(self):
        program = FixtureProgram()
        for words, code, path in ((["limits", "near", "--json"], "EXACTLY_ONE", "--digest,--sum"),
                                  # --lenient also conflicts with --strict, which the fixture judges first: within
                                  # step 4 the order is the implementation's
                                  (["limits", "near", SUM, "--lenient", "--strict", "--json"], "CONFLICTS", "--lenient"),
                                  (["limits", "near", SUM, "--paired-a", "--json"], "ALL_OR_NONE", "--paired-a,--paired-b"),
                                  (["limits", "near", SUM, "--report", "r", "--json"], "REQUIRES", "--report"),
                                  (["limits", "near", SUM, "--depth", "99", "--json"], "VALUE_RANGE", "--depth"),
                                  (["limits", "nowhere", SUM, "--json"], "VALUE_CHOICE", "TARGET"),
                                  (["limits", "--json"], "MISSING_OPERAND", "TARGET")):
            with self.subTest(words=words):
                done = program.run(*words)
                self.assertEqual(done.returncode, 1)
                entries = issues(done)
                self.assertEqual([(entry["code"], entry["path"]) for entry in entries], [(code, path)], entries)
                self.assertEqual(json.loads(done.stderr)["error"]["code"], "VALIDATION_FAILED")

    def test_a_path_never_carries_a_value_the_line_gave(self):
        """A word too many is `operands`, the secret it may be never written there."""
        done = FixtureProgram().run("version", "kit-secret-value", "--json")
        self.assertNotIn("kit-secret-value", json.dumps(issues(done)[0]["path"]))

    def test_the_text_rendering_shows_no_entry(self):
        done = FixtureProgram().run("version", "--kit-no-such-option")
        self.assertNotIn("UNKNOWN_OPTION", done.stderr)


if __name__ == "__main__":
    unittest.main()
