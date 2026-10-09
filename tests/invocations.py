# SPDX-License-Identifier: MPL-2.0
"""Generated invocations and what every conformant program does with them.

The kit judges an example from the catalog alone (`example_issues`). Turned around, the same judge
says of any command line whether the catalog accepts it, so a few hundred lines can be generated from
a catalog and a program held to what the contract says of each: this finds what a program does that
the text forbids and no check looks at, before an implementer reports it.

It is a test of this repository's reference program, not a part of the kit: it runs `--apply`, in a
home it made, and lines a product may not survive.
"""
from __future__ import annotations

import json
import pathlib
import random
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "conformance"))
from run import example_issues, value_problem  # noqa: E402

CODES = {"INVALID_COMMAND", "VALIDATION_FAILED", "PRECONDITION_FAILED", "POLICY_FAILED", "ACCESS_DENIED", "NOT_FOUND",
         "IO_FAILED", "PROCESS_FAILED", "PROTOCOL_FAILED", "UNSUPPORTED", "UNEXPECTED"}
RENDERINGS = (["--format", "json"], ["--json"], ["--format", "text"], ["--format", "jsonl"], ["--json", "--compact"],
              ["--non-interactive"], ["--color", "never"], ["--pager", "never"], ["--verbose"], ["--progress", "never"],
              ["--verbose", "--json"],
              ["--field", "mode"], ["--field", "mode", "--format", "jsonl"], ["--field", "no-such-member"],
              ["--field", "mode", "--json"])


def valid_value(declaration: dict) -> str | None:
    """A value of the declared kind, or None when none of the candidates is one."""
    kind = declaration.get("type", "string")
    widths = declaration.get("digits")
    width = (widths if isinstance(widths, int) else widths[0]) if widths else 64
    candidates = {"choice": declaration.get("choices", [])[:1], "boolean": ["true"],
                  "unsigned": [str(declaration.get("minimum", 1))], "integer": [str(declaration.get("minimum", 1))],
                  "absolute-path": ["/srv/kit"], "sha256": ["ab" * 32], "hex": ["ab" * (width // 2)],
                  "digest": [f"{declaration.get('algorithms', ['sha256'])[0]}:{'ab' * (width // 2)}"],
                  "size": ["1M"], "duration": ["5s"]}.get(kind, ["kit", "a", "note", "v1", "a-b", "1"])
    return next((value for value in candidates if not value_problem(declaration, value)), None)


def invalid_value(declaration: dict) -> str | None:
    """A value the declared kind refuses, or None when the kit's judge cannot tell one."""
    candidates = ["no-such-choice", "maybe", "-1", "x", "relative/path", "md5:00", "abc", "!", "99999999"]
    return next((value for value in candidates if value_problem(declaration, value)), None)


def opaque(command: dict) -> bool:
    """A command whose line the catalog does not own, or whose stdout it does not render."""
    return bool(command.get("external") or command["input"].get("passthrough")
                or command["outputMode"] == "protocol-stream")


def lines(command: dict, rng: random.Random, count: int) -> list[list[str]]:
    """Command lines for one command: the plain one, each rule broken once, and random mixtures."""
    operands = [valid_value(item) or "kit" for item in command["input"]["operands"] if item.get("required")]
    base = list(command["pattern"]) + operands
    options = command["input"]["options"]
    for item in options:
        if item.get("required"):
            base += [item["long"]] + ([valid_value(item["argument"]) or "kit"] if item.get("argument") else [])

    def spelled(item: dict, wrong: bool = False) -> list[str]:
        if not item.get("argument"):
            return [item["long"]]
        value = (invalid_value if wrong else valid_value)(item["argument"])
        return [item["long"], value] if value is not None else []

    found = [base, base + ["--no-such-option"], base + ["--", "kit"], base + ["kit-extra-operand"],
             base + ["--help"], base + ["--version"], base[:-1] if operands else base]
    found += [base + rendering for rendering in RENDERINGS] + [base + ["--help", "--json"]]
    for place, item in enumerate(options):
        found += [base + spelled(item), base + spelled(item) + spelled(item), base + spelled(item, wrong=True),
                  base + [item["long"]], base + spelled(item) + ["--help"], base + spelled(item) + ["--version"],
                  base + spelled(item) + ["--json"], base + ([] if item.get("argument") else [f"{item['long']}=false"]),
                  base + spelled(item) + ["--help", "--json"], base + spelled(item) + ["--field", "no-such-member"],
                  base + spelled(item) + ["--field", "mode", "--format", "jsonl"]]
        found += [base + spelled(item) + spelled(other) for other in options[place + 1:]]
    for _ in range(count):
        line = list(command["pattern"])
        line += operands[:rng.choice([len(operands)] * 4 + [max(0, len(operands) - 1)])]
        for item in rng.sample(options, k=rng.randint(0, len(options))):
            line += spelled(item, wrong=rng.random() < 0.15)
        line += rng.choice(RENDERINGS) if rng.random() < 0.6 else []
        line += rng.choice([[], [], [], ["--help"], ["--version"], ["--no-such-option"], ["kit-extra-operand"]])
        found.append(line)
    return [line for line in found if line]


def before_separator(words: list[str]) -> list[str]:
    return words[:words.index("--")] if "--" in words else words


def failure_code(stderr: str) -> str | None:
    """The error code of a failure, read from the envelope (json and jsonl) or from `PROGRAM: [CODE] message`."""
    if stderr.lstrip().startswith("{"):
        try:
            return json.loads(stderr)["error"]["code"]
        except (ValueError, KeyError, TypeError):
            return None
    match = re.search(r"\[([A-Z_]+)\]", stderr)
    return match.group(1) if match else None


def violations(command: dict, global_options: list[dict], words: list[str], completed, written: list[str],
               reference: bool = False) -> list[str]:
    """What this run does that the contract forbids, each as `invariant: detail`. An empty list is a pass.

    `reference` adds what holds of the reference program only: it refuses nothing the catalog accepts. A
    product may refuse a value for a reason of its own (a name that is not defined, a file that is not there),
    and VALIDATION_FAILED is the code for it."""
    found: list[str] = []
    before = before_separator(words)
    code, out, err = completed.returncode, completed.stdout, completed.stderr
    formats = [before[index + 1] for index, word in enumerate(before[:-1]) if word == "--format"]
    json_mode = "--json" in before or formats[-1:] == ["json"]
    asks = "--help" in before
    # ---- what holds for every line ----
    if code not in (0, 1, 2):
        found.append(f"exit: {code} is not 0, 1 or 2")
    if "Traceback" in err or "Traceback" in out:
        found.append("crash: a traceback instead of a failure")
    if code == 1 and out != "":
        found.append("failure-stdout: a failure leaves stdout empty (section 7)")
    if code == 1 and err == "":
        found.append("failure-silent: a failure says nothing on stderr")
    if code == 1 and written:
        found.append(f"failure-writes: a failure wrote {written[:3]}")
    if "--apply" not in before and written:
        found.append(f"plan-writes: without --apply the line wrote {written[:3]} (section 4)")
    if opaque(command):
        return found
    if "--help" in before and written:
        found.append(f"help-writes: --help ran the command, which wrote {written[:3]} (section 6)")
    body = None
    if json_mode:
        try:
            body = json.loads(out if code != 1 else err)
        except ValueError:
            found.append("envelope: the JSON rendering is not one JSON document")
    if body is not None:
        if body.get("exitCode") != code or body.get("ok") is not (code != 1) or isinstance(body.get("exitCode"), bool):
            found.append(f"envelope: ok {body.get('ok')!r} and exitCode {body.get('exitCode')!r} for exit {code}")
        named = "help" if asks and code != 1 else command["id"]  # section 6: the help a line gives is named help
        if body.get("command") != named:
            found.append(f"envelope-command: names {body.get('command')!r}, not {named!r}")
        if code == 1 and body.get("error", {}).get("code") not in CODES:
            found.append(f"error-code: {body.get('error', {}).get('code')!r} is not a code of section 8")
    records = command["outputMode"] == "json-records" or "--field" in before
    if code != 1 and out == "" and not records:
        found.append("success-silent: a success of a json-envelope command prints nothing")
    # an option of the command may ask for a diagnostic of its own; of the trunk, only --verbose in text mode does
    text_mode = not json_mode and formats[-1:] != ["jsonl"]
    own = {item["long"] for item in command["input"]["options"]}
    if code != 1 and err != "" and not (text_mode and "--verbose" in before) \
            and not any(word.partition("=")[0] in own for word in before):
        found.append("success-stderr: a success writes to stderr, which only --verbose in text mode allows here")
    if asks:
        return found  # where --help stands among the refusals of section 8 is not written yet
    # ---- what the catalog says of the line ----
    grammar = [issue for issue in example_issues(command, global_options, words) if not issue.endswith("is hidden")]
    failed = failure_code(err) if code == 1 else None
    if grammar and failed != "VALIDATION_FAILED":
        found += [f"accepts: {kind(issue)}" for issue in grammar]
    field = before[before.index("--field") + 1] if "--field" in before[:-1] else None
    schema = command.get("outputSchema", {})
    # a read decides on --field from its data, which the catalog does not hold; a command that may write, from
    # the `required` of its outputSchema (section 5)
    rendering = (formats[-1:] == ["jsonl"] and command["outputMode"] != "json-records" and field is None) \
        or (field is not None and (json_mode or command["effect"] == "read" or field not in schema.get("required", [])))
    if reference and not grammar and not rendering and failed == "VALIDATION_FAILED":
        found.append("refuses: a line the catalog accepts fails with VALIDATION_FAILED")
    return found


def kind(issue: str) -> str:
    """The rule an issue of `example_issues` is about, without the words of the line."""
    for needle, rule in (("--version is not an option", "--version after a command"),
                         ("operands where", "a wrong number of operands"), ("is not an option", "an undeclared option"),
                         ("is required", "a missing required option"), ("not repeatable", "a repeated option"),
                         ("has no value", "an option without its value"), ("requires", "an unmet requires"),
                         ("conflicts with", "a conflict"), ("does not hold", "a broken constraint"),
                         ("is a flag", "a flag with a value that is not true or false")):
        if needle in issue:
            return rule
    return "a value that is not of the declared kind"
