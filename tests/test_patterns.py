# SPDX-License-Identifier: MPL-2.0
"""The subset of section 3 in which a `pattern` is written, and its reading, as the kit holds them."""
import sys
import unittest

from support import ROOT

sys.path.insert(0, str(ROOT / "conformance"))
import patterns  # noqa: E402


class GrammarTest(unittest.TestCase):
    def test_the_patterns_of_the_contract_and_of_real_catalogs_are_in_the_subset(self):
        for pattern in (r"^[a-z][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)*$", r"^[a-z]([a-z0-9.-]*[a-z0-9-])?$",
                        r"^--[a-z][a-z0-9-]*$", r"^[A-Z][A-Z0-9_]*$", r"^sha256:[0-9a-f]{64}$", r"^v[0-9]+$",
                        r"^\]$", r"^a{0}$", r"^a{2,}b{0,255}$", r"[^a]", r"[-a]", r"[!--]", r"(ab|cd)?e", r"\\\^\$\.\|"):
            with self.subTest(pattern=pattern):
                self.assertEqual(patterns.problem(pattern), "")

    def test_what_engines_read_differently_is_outside_it(self):
        for pattern, reason in ((r"\d", "escape"), (r"\-", "escape"), (r"\/", "escape"), (r"(?:a)", "not plain"),
                                (r"[a-z-9]", "neither first, last"), (r"a{0,054}", "leading zero"),
                                (r"a{0,256}", "above 255"), (r"a{,3}", "bound"), (r"a{3,2}", "greater"),
                                (r"^]$", "bare ]"), (r"a}", "bare }"), (r"{", "nothing to repeat"),
                                (r"a**", "two quantifiers"), (r"a*?", "two quantifiers"), (r"a{2}{3}", "two quantifiers"),
                                (r"$*", "anchor"), (r"()", "empty"), (r"a|", "empty"), (r"[]", "empty class"),
                                (r"[z-a]", "inverted"), (r"[[:alpha:]]", "inside a class"), (r"[\]]", "inside a class"),
                                ("a\tb", "printable"), ("é", "printable"), (r"(a", "unclosed"), (r"a)", "closes no"),
                                ("", "empty pattern")):
            with self.subTest(pattern=pattern):
                self.assertIn(reason, patterns.problem(pattern))


class ReadingTest(unittest.TestCase):
    def matches(self, pattern, value):
        return patterns.compile_value_pattern(pattern).search(value) is not None

    def test_dot_matches_no_line_terminator_of_ecma_262(self):
        for value, expected in (("a", True), ("é", True), ("\udcff", True), ("\u0085", True),
                                ("\n", False), ("\r", False), (" ", False), (" ", False)):
            with self.subTest(value=value):
                self.assertEqual(self.matches(r"^.$", value), expected)

    def test_anchors_hold_at_the_ends_of_the_value_only(self):
        identifier = r"^[a-z][a-z0-9-]*(\.[a-z0-9][a-z0-9-]*)*$"
        self.assertTrue(self.matches(identifier, "note.write"))
        self.assertFalse(self.matches(identifier, "note.write\n"))
        self.assertFalse(self.matches(r"^(ab|cd$){1,3}e$", "abcdabe"))
        self.assertFalse(self.matches(r"a$", "a\nb"))

    def test_a_value_matches_when_some_part_of_it_does(self):
        self.assertTrue(self.matches(r"b", "abc"))
        self.assertFalse(self.matches(r"^b", "abc"))

    def test_a_negated_class_takes_what_the_class_lacks(self):
        for value in ("é", "\n", "\udcff"):
            with self.subTest(value=value):
                self.assertTrue(self.matches(r"^[^a]$", value))


class BudgetTest(unittest.TestCase):
    def test_nesting_and_expanded_size(self):
        self.assertEqual(patterns.over_budget(r"^[a-z]+$"), "")
        self.assertIn("nested groups", patterns.over_budget("(" * 33 + "a" + ")" * 33))
        self.assertEqual(patterns.over_budget("(" * 32 + "a" + ")" * 32), "")
        self.assertIn("expanded size", patterns.over_budget(r"(a{0,255}){0,255}"))
        self.assertEqual(patterns.read(r"a{2,3}")[2], 2 * 1 + 1 * 2 + 1)
        self.assertEqual(patterns.read(r"a|b")[2], 1 + 1 + 2 + 1)


if __name__ == "__main__":
    unittest.main()
