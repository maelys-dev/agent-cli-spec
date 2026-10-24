# SPDX-License-Identifier: MPL-2.0
"""The `pattern` of a `string` or `path` value (spec section 3): its grammar, its budget and its reading.

A pattern is written in a subset that ECMA-262 (with the `u` flag) and POSIX ERE read the same way. This reader
refuses what is outside it, measures it, and translates it to Python's `re` with the reading of section 3: a
value is a sequence of code points, `.` matches any of them but the four line terminators of ECMA-262, `^` and
`$` hold at the two ends of the value only, and a value matches when some part of it does.

The budget is measured on the pattern expanded: a literal, `.`, a class and an anchor count 1, a sequence the sum
of its items, an alternation of k branches the sum and 2 x (k - 1), `e{m,n}` m x |e| + (n - m) x (|e| + 1),
`e{m,}` m x |e| + |e| + 2 (`*`, `+` and `?` being `{0,}`, `{1,}` and `{0,1}`), and the whole pattern that size
and 1: the states of the program a Thompson simulation runs.

The `pattern` members of an `outputSchema` are JSON Schema's, read by `validate.compile_pattern`, and not these.
"""
from __future__ import annotations

import re

METACHARACTERS = set("\\^$.[]()*+?{}|")
LINE_TERMINATORS = "\n\r  "
MAX_BOUND = 255
MAX_NESTING = 32
MAX_EXPANDED = 65536


class PatternError(ValueError):
    """A pattern outside the subset of section 3, with the reason."""


def printable(character: str) -> bool:
    return " " <= character <= "~"


class Reader:
    """A recursive reader of the subset. Each node is (kind, value, size): `size` is its expanded size."""

    def __init__(self, pattern: str) -> None:
        self.text, self.place, self.depth, self.deepest = pattern, 0, 0, 0
        self.out: list[str] = []

    def peek(self) -> str:
        return self.text[self.place] if self.place < len(self.text) else ""

    def fail(self, reason: str) -> PatternError:
        return PatternError(f"{reason} at offset {self.place}")

    def alternation(self) -> int:
        sizes = [self.sequence()]
        while self.peek() == "|":
            self.out.append("|")
            self.place += 1
            sizes.append(self.sequence())
        return sum(sizes) + 2 * (len(sizes) - 1)

    def sequence(self) -> int:
        size = 0
        start = len(self.out)
        while self.peek() not in ("", "|", ")"):
            size += self.item()
        if len(self.out) == start:
            raise self.fail("an empty alternative or group")
        return size

    def item(self) -> int:
        character = self.peek()
        if character in ("^", "$"):
            self.out.append(r"\A" if character == "^" else r"\Z")
            self.place += 1
            if self.peek() in ("*", "+", "?", "{"):
                raise self.fail("a quantifier on an anchor")
            return 1
        size = self.atom()
        return self.quantifier(size)

    def atom(self) -> int:
        character = self.peek()
        if character == "(":
            self.place += 1
            if self.peek() == "?":
                raise self.fail("a group that is not plain, (?...)")
            self.depth += 1
            self.deepest = max(self.deepest, self.depth)
            self.out.append("(")
            size = self.alternation()
            if self.peek() != ")":
                raise self.fail("an unclosed group")
            self.place += 1
            self.depth -= 1
            self.out.append(")")
            return size
        if character == "[":
            return self.character_class()
        if character == ".":
            self.place += 1
            self.out.append("[^" + "".join(re.escape(item) for item in LINE_TERMINATORS) + "]")
            return 1
        if character == "\\":
            escaped = self.text[self.place + 1:self.place + 2]
            if escaped not in METACHARACTERS:
                raise self.fail(f"the escape \\{escaped}, which is not one of a metacharacter")
            self.place += 2
            self.out.append(re.escape(escaped))
            return 1
        if character in ("*", "+", "?", "{"):
            raise self.fail(f"a quantifier {character} with nothing to repeat")
        if character in ("]", "}"):
            raise self.fail(f"a bare {character}, written \\{character} outside a class")
        if not printable(character):
            raise self.fail(f"the character {character!r}, a pattern being printable ASCII")
        self.place += 1
        self.out.append(re.escape(character))
        return 1

    def character_class(self) -> int:
        self.place += 1
        negated = self.peek() == "^"
        if negated:
            self.place += 1
        members: list[str] = []
        while True:
            character = self.peek()
            if character == "":
                raise self.fail("an unclosed class")
            if character == "]":
                break
            if character in ("[", "\\"):
                raise self.fail(f"{character} inside a class")
            if not printable(character):
                raise self.fail(f"the character {character!r} in a class, a class being printable ASCII")
            members.append(character)
            self.place += 1
        self.place += 1
        if not members:
            raise self.fail("an empty class")
        parts, index = [], 0
        while index < len(members):
            low = members[index]
            if index + 2 < len(members) and members[index + 1] == "-":
                high = members[index + 2]
                if low > high:
                    raise self.fail(f"the inverted range {low}-{high}")
                parts.append(re.escape(low) + "-" + re.escape(high))
                index += 3
                continue
            if low == "-" and 0 < index < len(members) - 1:
                raise self.fail("a - inside a class that is neither first, last nor the end of a range")
            parts.append(re.escape(low))
            index += 1
        self.out.append("[" + ("^" if negated else "") + "".join(parts) + "]")
        return 1

    def bound(self) -> int:
        match = re.compile(r"0|[1-9][0-9]*").match(self.text, self.place)
        if match is not None and match.group() == "0" and self.text[match.end():match.end() + 1].isdigit():
            raise self.fail("a bound written with a leading zero")
        if match is None:
            raise self.fail("a bound that is not a decimal number without a leading zero")
        self.place = match.end()
        value = int(match.group())
        if value > MAX_BOUND:
            raise self.fail(f"the bound {value}, above {MAX_BOUND}")
        return value

    def quantifier(self, size: int) -> int:
        character = self.peek()
        if character in ("*", "+", "?"):
            self.place += 1
            self.out.append(character)
            least, most = {"*": (0, None), "+": (1, None), "?": (0, 1)}[character]
        elif character == "{":
            self.place += 1
            least = self.bound()
            most: int | None = least
            if self.peek() == ",":
                self.place += 1
                most = None if self.peek() == "}" else self.bound()
            if self.peek() != "}":
                raise self.fail("a bound that is not {m}, {m,} or {m,n}")
            self.place += 1
            if most is not None and least > most:
                raise self.fail(f"the bound {{{least},{most}}}, whose first number is the greater")
            self.out.append("{" + str(least) + ("" if most == least else "," + ("" if most is None else str(most))) + "}")
        else:
            return size
        if self.peek() in ("*", "+", "?", "{"):
            raise self.fail("two quantifiers in a row")
        if most is None:
            return least * size + size + 2
        return least * size + (most - least) * (size + 1)


def read(pattern: str) -> tuple[str, int, int]:
    """The Python translation of a pattern, its group nesting and its expanded size; PatternError when it is
    outside the subset."""
    if not isinstance(pattern, str) or pattern == "":
        raise PatternError("an empty pattern")
    reader = Reader(pattern)
    size = reader.alternation()
    if reader.place != len(pattern):
        raise reader.fail("a ) that closes no group")
    return "".join(reader.out), reader.deepest, size + 1


def problem(pattern: str) -> str:
    """Why a pattern is outside the subset of section 3, or ""."""
    try:
        read(pattern)
    except PatternError as error:
        return str(error)
    return ""


def over_budget(pattern: str) -> str:
    """Why a pattern of the subset is beyond the budget every implementation accepts, or ""."""
    _, nesting, size = read(pattern)
    if nesting > MAX_NESTING:
        return f"{nesting} nested groups, above {MAX_NESTING}"
    if size > MAX_EXPANDED:
        return f"an expanded size of {size}, above {MAX_EXPANDED}"
    return ""


def compile_value_pattern(pattern: str) -> "re.Pattern[str]":
    """A pattern of the subset compiled with the reading of section 3; `search` tells whether a value matches."""
    return re.compile(read(pattern)[0])
